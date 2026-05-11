from __future__ import annotations

import json
import os
import subprocess
import sys
from datetime import datetime, time as dt_time
from pathlib import Path

import psutil
import requests
import streamlit as st
from dotenv import load_dotenv


BASE_DIR = Path(__file__).resolve().parent
PID_FILE = BASE_DIR / "server_ig.pid"
SESSION_FILE = BASE_DIR / "server_ig.session"
SCHEDULE_FILE = BASE_DIR / "schedule_config.json"
LEGACY_SCHEDULE_FILE = BASE_DIR / "scheduler_state.json"
LOG_FILE = BASE_DIR / "logs" / "instagram_pipeline.log"
PENDING_DIR = BASE_DIR / "pending_videos"
POSTED_DIR = BASE_DIR / "posted_videos"
FAILED_DIR = BASE_DIR / "failed_videos"


load_dotenv()


def _ensure_directories() -> None:
    for folder in (PENDING_DIR, POSTED_DIR, FAILED_DIR, LOG_FILE.parent):
        folder.mkdir(parents=True, exist_ok=True)


def _read_pid() -> int | None:
    if not PID_FILE.exists():
        return None
    try:
        return int(PID_FILE.read_text(encoding="utf-8").strip())
    except Exception:
        return None


def _process_is_running(pid: int | None) -> bool:
    if not pid:
        return False
    try:
        return psutil.pid_exists(pid) and psutil.Process(pid).is_running()
    except Exception:
        return False


def _default_slots(count: int = 10) -> list[dict[str, object]]:
    return [{"enabled": False, "time_hhmm": "09:00"} for _ in range(count)]


def _normalize_slots(payload: object) -> list[dict[str, object]]:
    raw_slots: list[object] = []
    if isinstance(payload, dict):
        raw_slots = list(payload.get("slots", []))  # type: ignore[arg-type]
    elif isinstance(payload, list):
        raw_slots = payload

    normalized: list[dict[str, object]] = []
    for index in range(10):
        slot = raw_slots[index] if index < len(raw_slots) else {}
        if not isinstance(slot, dict):
            slot = {}
        normalized.append(
            {
                "enabled": bool(slot.get("enabled", False)),
                "time_hhmm": str(slot.get("time_hhmm", "09:00"))[:5],
            }
        )
    return normalized


def _load_schedule_state() -> list[dict[str, object]]:
    schedule_file = SCHEDULE_FILE if SCHEDULE_FILE.exists() else LEGACY_SCHEDULE_FILE
    if not schedule_file.exists():
        return _default_slots()
    try:
        return _normalize_slots(json.loads(schedule_file.read_text(encoding="utf-8")))
    except Exception:
        return _default_slots()


def _save_schedule_state(slots: list[dict[str, object]]) -> None:
    payload = {"slots": slots[:10]}
    SCHEDULE_FILE.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _load_session_value() -> str:
    if SESSION_FILE.exists():
        try:
            return SESSION_FILE.read_text(encoding="utf-8").strip()
        except Exception:
            return ""
    return os.getenv("IG_SESSIONID", "").strip()


def _extract_sessionid_from_upload(uploaded_file) -> str:
    try:
        raw_text = uploaded_file.getvalue().decode("utf-8-sig", errors="ignore").strip()
    except Exception:
        return ""
    if not raw_text:
        return ""
    try:
        payload = json.loads(raw_text)
    except Exception:
        return raw_text

    def _search(node: object) -> str:
        if isinstance(node, dict):
            for key in ("sessionid", "session_id", "IG_SESSIONID", "value"):
                value = node.get(key)
                if isinstance(value, str) and value.strip():
                    return value.strip()
            if node.get("name") == "sessionid" and isinstance(node.get("value"), str):
                return str(node["value"]).strip()
            for value in node.values():
                found = _search(value)
                if found:
                    return found
        elif isinstance(node, list):
            for item in node:
                found = _search(item)
                if found:
                    return found
        return ""

    return _search(payload) or raw_text


def _save_sessionid(sessionid: str) -> None:
    sessionid = sessionid.strip()
    if not sessionid:
        raise ValueError("Session value cannot be empty")
    SESSION_FILE.write_text(sessionid, encoding="utf-8")
    os.environ["IG_SESSIONID"] = sessionid


def _start_engine(sessionid: str) -> str:
    _ensure_directories()
    _save_sessionid(sessionid)
    env = os.environ.copy()
    env["IG_SESSIONID"] = sessionid.strip()
    env.setdefault("PYTHONIOENCODING", "utf-8")
    script = BASE_DIR / "core_pipeline.py"
    creationflags = getattr(subprocess, "CREATE_NEW_CONSOLE", 0)
    with open(LOG_FILE, "a", encoding="utf-8") as log_handle:
        process = subprocess.Popen(
            [sys.executable, str(script), "run"],
            cwd=str(BASE_DIR),
            env=env,
            creationflags=creationflags,
            close_fds=False,
            stdout=log_handle,
            stderr=subprocess.STDOUT,
            text=True,
        )
    PID_FILE.write_text(str(process.pid), encoding="utf-8")
    return str(process.pid)


def _stop_engine() -> str:
    pid = _read_pid()
    if not pid:
        return "No engine PID found."
    if not psutil.pid_exists(pid):
        PID_FILE.unlink(missing_ok=True)
        return "Engine process is not running."
    process = psutil.Process(pid)
    process.terminate()
    try:
        process.wait(timeout=10)
    except psutil.TimeoutExpired:
        process.kill()
    PID_FILE.unlink(missing_ok=True)
    return f"Stopped process {pid}."


def _count_files(folder: Path, pattern: str = "*.mp4") -> int:
    return len(list(folder.glob(pattern))) if folder.exists() else 0


def _tail_log(path: Path, max_lines: int = 50) -> str:
    if not path.exists():
        return "Log file not created yet. Start the engine to generate logs."
    try:
        lines = path.read_text(encoding="utf-8", errors="ignore").splitlines()
        return "\n".join(lines[-max_lines:]) if lines else "Log file is empty."
    except Exception:
        return "Unable to read log file."


def _ollama_status() -> tuple[bool, str]:
    base_url = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434").rstrip("/")
    model = os.getenv("OLLAMA_MODEL", "llama3.2:1b").strip()
    try:
        response = requests.get(f"{base_url}/api/tags", timeout=1.5)
        if response.status_code != 200:
            return False, "OFFLINE"
        payload = response.json()
        models: list[str] = []
        if isinstance(payload, dict) and isinstance(payload.get("models"), list):
            for item in payload["models"]:
                if isinstance(item, dict) and isinstance(item.get("name"), str):
                    models.append(item["name"])
        elif isinstance(payload, list):
            for item in payload:
                if isinstance(item, dict) and isinstance(item.get("name"), str):
                    models.append(item["name"])
        return model in models, "ONLINE (Ollama)" if model in models else "OFFLINE"
    except Exception:
        return False, "OFFLINE"


def _render_live_log(auto_refresh: bool) -> None:
    if hasattr(st, "fragment") and auto_refresh:
        @st.fragment(run_every=3)
        def _log_fragment() -> None:
            st.code(_tail_log(LOG_FILE, max_lines=50), language="text")

        _log_fragment()
        return

    st.code(_tail_log(LOG_FILE, max_lines=50), language="text")


def _render_directory_expander(title: str, folder: Path) -> None:
    with st.expander(title, expanded=False):
        if not folder.exists():
            st.write("Folder not found.")
            return
        files = sorted(folder.glob("*"))
        if not files:
            st.write("No files yet.")
            return
        for file_path in files:
            try:
                size_kb = file_path.stat().st_size / 1024
                st.write(f"{file_path.name}  -  {size_kb:.1f} KB")
            except Exception:
                st.write(file_path.name)


def _inject_css() -> None:
    st.markdown(
        """
        <style>
            .block-container { padding-top: 1rem; }
            [data-testid="stSidebar"] { background: #171a24; }
            .brand-name {
                background: linear-gradient(90deg, #00e5ff 0%, #ff4fd8 45%, #ffd166 90%);
                -webkit-background-clip: text;
                color: transparent;
            }
            .command-subtitle { color: rgba(255,255,255,0.72); margin-bottom: 1rem; }
            .section-card {
                background: rgba(255,255,255,0.03);
                border: 1px solid rgba(255,255,255,0.08);
                border-radius: 16px;
                padding: 1rem;
                margin-bottom: 1rem;
            }
            .log-panel {
                background: #11141d;
                border: 1px solid rgba(255,255,255,0.08);
                border-radius: 16px;
                padding: 1rem;
            }
        </style>
        """,
        unsafe_allow_html=True,
    )


def main() -> None:
    _ensure_directories()
    st.set_page_config(page_title="NeonReel Scheduler", layout="wide")
    _inject_css()

    current_pid = _read_pid()
    is_running = _process_is_running(current_pid)
    ollama_online, ollama_label = _ollama_status()
    pending_count = _count_files(PENDING_DIR)
    posted_count = _count_files(POSTED_DIR)
    failed_count = _count_files(FAILED_DIR)

    st.title("NeonReel Scheduler")
    st.markdown(
        "<style>h1 span { background: linear-gradient(90deg, #00e5ff 0%, #ff4fd8 45%, #ffd166 90%); -webkit-background-clip: text; color: transparent; }</style>",
        unsafe_allow_html=True,
    )
    st.markdown(
        '<div class="command-subtitle">Local control plane for queue scanning, uploads, and live log monitoring.</div>',
        unsafe_allow_html=True,
    )

    pending_col, posted_col, failed_col = st.columns(3)
    pending_col.metric("Pending Videos", pending_count)
    posted_col.metric("Posted Videos", posted_count)
    failed_col.metric("Failed Videos", failed_count)

    with st.sidebar:
        st.header("Server Control")
        st.success("Server is running" if is_running else "Server is stopped")
        st.write(f"PID: {current_pid if current_pid else 'None'}")

        if is_running:
            if st.button("Stop Server", use_container_width=True):
                st.info(_stop_engine())
                st.rerun()
        else:
            st.caption("Use the saved session file or upload a new one, then start the engine.")

        st.divider()
        st.subheader("Configure Schedule")
        slots = _load_schedule_state()
        slot_count = st.number_input(
            "Number of Time Slots (Max 10)",
            min_value=1,
            max_value=10,
            value=max(1, min(10, sum(1 for slot in slots if slot.get("enabled")) or 1)),
            step=1,
        )
        updated_slots: list[dict[str, object]] = []
        for index in range(int(slot_count)):
            slot = slots[index] if index < len(slots) else {"enabled": True, "time_hhmm": "09:00"}
            st.markdown(f"**Slot {index + 1}**")
            time_value = st.time_input(
                "Time (HH:MM)",
                value=dt_time.fromisoformat(f"{str(slot.get('time_hhmm', '09:00'))[:5]}:00"),
                key=f"slot_time_{index}",
            )
            enabled_value = st.toggle("Enabled", value=bool(slot.get("enabled", False)), key=f"slot_enabled_{index}")
            updated_slots.append({"enabled": enabled_value, "time_hhmm": time_value.strftime("%H:%M")})

        if st.button("Save Times", use_container_width=True):
            _save_schedule_state(updated_slots)
            st.success("Schedule saved. Background pipeline will auto-reload changes.")

        st.divider()
        st.subheader("Local LLM")
        st.metric("Local LLM", ollama_label)
        if not ollama_online:
            st.caption(f"Pull the model if needed: ollama pull {os.getenv('OLLAMA_MODEL', 'llama3.2:1b')}")

    st.markdown('<div class="section-card">', unsafe_allow_html=True)
    st.subheader("Session ID Authentication")
    st.caption("Paste your Instagram sessionid value, save it, then start the server.")
    saved_session = _load_session_value()
    session_input = st.text_area(
        "Instagram sessionid",
        value=saved_session,
        height=120,
        placeholder="Paste your Instagram sessionid here",
    )
    save_session_col, save_start_col = st.columns([1, 2])
    with save_session_col:
        if st.button("Save Session ID"):
            if session_input.strip():
                _save_sessionid(session_input)
                st.success("Session ID saved.")
            else:
                st.error("Session ID cannot be empty.")
    with save_start_col:
        if st.button("Save Session ID and Start Server"):
            if not session_input.strip():
                st.error("Paste a session ID first.")
            elif is_running:
                st.info("Server is already running.")
            else:
                pid = _start_engine(session_input)
                st.success(f"Server started in a new console. PID {pid}.")
                st.rerun()
    st.markdown('</div>', unsafe_allow_html=True)

    st.markdown('<div class="section-card">', unsafe_allow_html=True)
    st.subheader("Directory Overview")
    _render_directory_expander("Show Pending Files", PENDING_DIR)
    _render_directory_expander("Show Posted Files", POSTED_DIR)
    _render_directory_expander("Show Failed Files", FAILED_DIR)
    st.markdown('</div>', unsafe_allow_html=True)

    st.markdown('<div class="section-card">', unsafe_allow_html=True)
    st.subheader("Terminal Output (Live Log)")
    auto_refresh = st.checkbox("Auto-Refresh Logs (every 3 seconds)", value=True)
    _render_live_log(auto_refresh)
    st.markdown('</div>', unsafe_allow_html=True)

    st.markdown('<div class="section-card">', unsafe_allow_html=True)
    st.subheader("Operational Notes")
    st.write("The Streamlit UI only controls the local engine. Save Times updates schedule_config.json and the engine rereads it on the next loop.")
    st.write(f"Last refresh: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    st.markdown('</div>', unsafe_allow_html=True)


if __name__ == "__main__":
    main()
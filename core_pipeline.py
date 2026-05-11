from __future__ import annotations

import argparse
import gc
import json
import logging
import os
import shutil
import sys
import time
import traceback
from dataclasses import dataclass, asdict
from datetime import datetime, time as dt_time
from pathlib import Path
from typing import Iterable

from dotenv import load_dotenv
from instagrapi import Client

from caption_agent import generate_caption


BASE_DIR = Path(__file__).resolve().parent
PENDING_DIR = BASE_DIR / "pending_videos"
POSTED_DIR = BASE_DIR / "posted_videos"
FAILED_DIR = BASE_DIR / "failed_videos"
LOG_DIR = BASE_DIR / "logs"
LOG_FILE = LOG_DIR / "instagram_pipeline.log"
PID_FILE = BASE_DIR / "server_ig.pid"
SESSION_FILE = BASE_DIR / "server_ig.session"
SCHEDULER_FILE = BASE_DIR / "schedule_config.json"
LEGACY_SCHEDULER_FILE = BASE_DIR / "scheduler_state.json"

_LAST_SCHEDULE_SIGNATURE: tuple[tuple[bool, str], ...] | None = None
_LAST_POST_MINUTE: str | None = None


@dataclass
class SchedulerSlot:
    enabled: bool = False
    time_hhmm: str = "09:00"
    label: str = ""


def ensure_directories() -> None:
    for folder in (PENDING_DIR, POSTED_DIR, FAILED_DIR, LOG_DIR):
        folder.mkdir(parents=True, exist_ok=True)


def load_scheduler_slots() -> list[SchedulerSlot]:
    schedule_file = SCHEDULER_FILE if SCHEDULER_FILE.exists() else LEGACY_SCHEDULER_FILE
    if not schedule_file.exists():
        return [SchedulerSlot() for _ in range(10)]
    try:
        raw = json.loads(schedule_file.read_text(encoding="utf-8"))
        slots = raw.get("slots", [])
        result: list[SchedulerSlot] = []
        for index in range(10):
            slot = slots[index] if index < len(slots) else {}
            result.append(
                SchedulerSlot(
                    enabled=bool(slot.get("enabled", False)),
                    time_hhmm=str(slot.get("time_hhmm", "09:00"))[:5],
                    label=str(slot.get("label", f"Slot {index + 1}")),
                )
            )
        return result
    except Exception:
        return [SchedulerSlot() for _ in range(10)]


def save_scheduler_slots(slots: list[SchedulerSlot]) -> None:
    payload = {"slots": [asdict(slot) for slot in slots]}
    SCHEDULER_FILE.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def configure_logging() -> logging.Logger:
    ensure_directories()
    logger = logging.getLogger("instagram_pipeline")
    logger.setLevel(logging.INFO)
    logger.propagate = False
    if not logger.handlers:
        handler = logging.FileHandler(LOG_FILE, encoding="utf-8")
        handler.setFormatter(
            logging.Formatter("%(asctime)s | %(levelname)s | %(message)s")
        )
        logger.addHandler(handler)
    return logger


def _read_sessionid() -> str:
    load_dotenv()
    sessionid = os.getenv("IG_SESSIONID", "").strip()
    if sessionid:
        return sessionid
    if SESSION_FILE.exists():
        return SESSION_FILE.read_text(encoding="utf-8").strip()
    return ""


def _parse_hhmm(value: str) -> dt_time:
    hour, minute = value.split(":", 1)
    return dt_time(hour=int(hour), minute=int(minute))


def _slot_minutes(slot_time: dt_time) -> int:
    return slot_time.hour * 60 + slot_time.minute


def _enabled_slot_times(slots: Iterable[SchedulerSlot]) -> list[str]:
    times: list[str] = []
    for slot in slots:
        if not slot.enabled:
            continue
        try:
            slot_time = _parse_hhmm(slot.time_hhmm)
            times.append(slot_time.strftime("%H:%M"))
        except Exception:
            continue
    return times


def _enabled_slots(slots: Iterable[SchedulerSlot]) -> list[SchedulerSlot]:
    return [slot for slot in slots if slot.enabled]


def _next_slot_in_minutes(slots: Iterable[SchedulerSlot], now: datetime) -> int | None:
    enabled_times: list[int] = []
    for slot in slots:
        if not slot.enabled:
            continue
        try:
            slot_time = _parse_hhmm(slot.time_hhmm)
            enabled_times.append(_slot_minutes(slot_time))
        except Exception:
            continue
    if not enabled_times:
        return None
    current_minutes = now.hour * 60 + now.minute
    future = [t for t in enabled_times if t > current_minutes]
    if future:
        return min(future) - current_minutes
    # Wrap to next day
    return (24 * 60 - current_minutes) + min(enabled_times)


def _safe_move(source: Path, destination_dir: Path, logger: logging.Logger) -> Path:
    destination_dir.mkdir(parents=True, exist_ok=True)
    gc.collect()
    time.sleep(5)
    target = destination_dir / source.name
    if target.exists():
        stem = source.stem
        suffix = source.suffix
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        target = destination_dir / f"{stem}_{timestamp}{suffix}"
    shutil.move(str(source), str(target))
    gc.collect()
    time.sleep(5)
    logger.info("Moved %s -> %s", source.name, target)
    return target


class InstagramPoster:
    def __init__(self, logger: logging.Logger) -> None:
        self.logger = logger
        self.client = Client()
        self.sessionid = _read_sessionid()
        if not self.sessionid:
            raise RuntimeError("IG_SESSIONID is missing")
        self._login_with_sessionid()

    def _login_with_sessionid(self) -> None:
        self.client.login_by_sessionid(self.sessionid)

    def _upload_reel(self, video_path: Path, caption: str) -> None:
        try:
            self.client.clip_upload(str(video_path), caption)
        except KeyError as exc:
            if "pinned_channels_info" in str(exc):
                self.logger.warning("Recovering from pinned_channels_info KeyError")
                self.client = Client()
                self._login_with_sessionid()
                self.client.clip_upload(str(video_path), caption)
                return
            raise

    def post_file(self, video_path: Path) -> None:
        caption_result = generate_caption(video_path.name)
        self.logger.info("Caption provider=%s file=%s", caption_result.provider, video_path.name)
        self._upload_reel(video_path, caption_result.caption)


def process_pending_videos(logger: logging.Logger, max_files: int = 0) -> int:
    ensure_directories()
    poster = InstagramPoster(logger)
    posted = 0
    for video_path in sorted(PENDING_DIR.glob("*.mp4")):
        try:
            logger.info("Processing %s", video_path.name)
            poster.post_file(video_path)
            _safe_move(video_path, POSTED_DIR, logger)
            posted += 1
            gc.collect()
            time.sleep(5)
            if max_files and posted >= max_files:
                logger.info("Slot limit reached. Posted %s file(s).", posted)
                break
        except Exception:
            logger.exception("Failed to post %s", video_path.name)
            try:
                _safe_move(video_path, FAILED_DIR, logger)
            except Exception:
                logger.error("Failed to move %s to failed_videos\n%s", video_path.name, traceback.format_exc())
    return posted


def run_loop(logger: logging.Logger) -> None:
    global _LAST_SCHEDULE_SIGNATURE
    global _LAST_POST_MINUTE
    interval_seconds = int(os.getenv("QUEUE_SCAN_INTERVAL_SECONDS", "30"))
    logger.info("Engine started interval_seconds=%s", interval_seconds)
    while True:
        try:
            slots = load_scheduler_slots()
            signature = tuple((slot.enabled, slot.time_hhmm) for slot in slots)
            if signature != _LAST_SCHEDULE_SIGNATURE:
                enabled_times = _enabled_slot_times(slots)
                if enabled_times:
                    logger.info("Schedule loaded: %s", ", ".join(enabled_times))
                else:
                    logger.warning("Schedule loaded with no enabled slots.")
                _LAST_SCHEDULE_SIGNATURE = signature

            now = datetime.now()
            current_hhmm = now.strftime("%H:%M")
            enabled_slots = _enabled_slots(slots)

            if not enabled_slots:
                logger.info("No enabled slots. Waiting for schedule.")
            elif any(slot.time_hhmm == current_hhmm for slot in enabled_slots):
                if _LAST_POST_MINUTE == current_hhmm:
                    logger.info("Cooldown active. Already posted at %s.", current_hhmm)
                else:
                    logger.info("Schedule matched at %s. Starting upload cycle.", current_hhmm)
                    posted = process_pending_videos(logger, max_files=1)
                    _LAST_POST_MINUTE = current_hhmm
                    logger.info("Cycle complete posted=%s", posted)
            else:
                enabled_times = _enabled_slot_times(slots)
                minutes_until = _next_slot_in_minutes(enabled_slots, now)
                if minutes_until is None:
                    logger.info("No enabled slot matched current time.")
                else:
                    logger.info(
                        "No enabled slot matched current time. Next slots: %s. Next post in %s minute(s).",
                        ", ".join(enabled_times),
                        minutes_until,
                    )
        except Exception:
            logger.exception("Unhandled engine error")
        finally:
            gc.collect()
            time.sleep(max(5, interval_seconds))


def run_once(logger: logging.Logger) -> None:
    posted = process_pending_videos(logger)
    logger.info("Run once complete posted=%s", posted)


def write_pid_file() -> None:
    PID_FILE.write_text(str(os.getpid()), encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    load_dotenv()
    ensure_directories()
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    if hasattr(sys.stderr, "reconfigure"):
        sys.stderr.reconfigure(encoding="utf-8")
    logger = configure_logging()
    parser = argparse.ArgumentParser(description="Instagram Reel conveyor belt engine")
    parser.add_argument("mode", nargs="?", choices=("run", "once"), default="run")
    args = parser.parse_args(argv)
    write_pid_file()
    if args.mode == "once":
        run_once(logger)
    else:
        run_loop(logger)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
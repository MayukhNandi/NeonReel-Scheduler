███╗   ██╗███████╗ ██████╗ ███╗   ██╗██████╗ ███████╗███████╗██╗     
████╗  ██║██╔════╝██╔═══██╗████╗  ██║██╔══██╗██╔════╝██╔════╝██║     
██╔██╗ ██║█████╗  ██║   ██║██╔██╗ ██║██████╔╝█████╗  █████╗  ██║     
██║╚██╗██║██╔══╝  ██║   ██║██║╚██╗██║██╔══██╗██╔══╝  ██╔══╝  ██║     
██║ ╚████║███████╗╚██████╔╝██║ ╚████║██║  ██║███████╗███████╗███████╗
╚═╝  ╚═══╝╚══════╝ ╚═════╝ ╚═╝  ╚═══╝╚═╝  ╚═╝╚══════╝╚══════╝╚══════╝

███████╗ ██████╗██╗  ██╗███████╗██████╗ ██╗   ██╗██╗     ███████╗██████╗ 
██╔════╝██╔════╝██║  ██║██╔════╝██╔══██╗██║   ██║██║     ██╔════╝██╔══██╗
███████╗██║     ███████║█████╗  ██║  ██║██║   ██║██║     █████╗  ██████╔╝
╚════██║██║     ██╔══██║██╔══╝  ██║  ██║██║   ██║██║     ██╔══╝  ██╔══██╗
███████║╚██████╗██║  ██║███████╗██████╔╝╚██████╔╝███████╗███████╗██║  ██║
╚══════╝ ╚═════╝╚═╝  ╚═╝╚══════╝╚═════╝  ╚═════╝ ╚══════╝╚══════╝╚═╝  ╚═╝
			 
			 
			 NeonReel Scheduler — Automated Reels, Scheduled

# NeonReel Scheduler

> A Windows-first Instagram Reel automation pipeline with a command-center dashboard. Schedule posts, generate unique SEO captions with local Ollama, and keep your queue clean and self-healing.

![Python](https://img.shields.io/badge/Python-3.14+-blue.svg)
![Streamlit](https://img.shields.io/badge/Streamlit-1.36+-ff4b4b.svg)
![Ollama](https://img.shields.io/badge/LLM-Ollama-00e5ff.svg)
![License](https://img.shields.io/badge/License-MIT-green.svg)

---

## 📖 Table of Contents

- [✨ Features](#-features)
- [🏗️ Architecture](#️-architecture)
- [⚙️ Installation](#️-installation)
- [🚀 Quick Start](#-quick-start)
- [🧭 Usage Guide](#-usage-guide)
- [🔧 Configuration](#-configuration)
- [📂 Project Structure](#-project-structure)
- [🧾 Scheduler Rules](#-scheduler-rules)
- [🧠 Caption Engine](#-caption-engine)
- [🧯 Troubleshooting](#-troubleshooting)
- [📄 License](#-license)

---

## ✨ Features

- **One slot = one post** — each schedule time posts exactly one video.
- **Local LLM captions** — Ollama runs entirely on your machine.
- **Command-center dashboard** — live queue stats, session control, and log tailing.
- **Self-healing queue** — failed uploads move to `failed_videos` with full tracebacks.
- **Windows-safe file handling** — extra guards prevent file lock errors.

---

## 🏗️ Architecture

```
┌──────────────────────────────────────────────────────────────────┐
│                    Streamlit Command Center                      │
├──────────────────────────────────────────────────────────────────┤
│  Schedule Slots  |  Session ID  |  Live Log Tail  |  Stats        │
└───────────┬──────────────────────┬────────────────┬───────────────┘
		│                      │                │
		▼                      │                ▼
    schedule_config.json           │        pending/posted/failed
		│                      │
		▼                      ▼
	 core_pipeline.py  ──>  caption_agent.py  ──>  Ollama (local)
		│
		▼
	instagrapi upload
```

---

## ⚙️ Installation

### Prerequisites
- **Python 3.14+**
- **Ollama** installed and running locally (https://ollama.ai)
- **Instagram sessionid** cookie

### Setup

```powershell
python -m venv .venv
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.venv\Scripts\Activate.ps1
```

If PowerShell activation is blocked:

```powershell
.venv\Scripts\activate.bat
```

Install dependencies:

```powershell
pip install -r requirements.txt
```

Create `.env`:

```powershell
copy .env.example .env
```

---

## 🚀 Quick Start

**One-step launcher:**

```powershell
start_dashboard.bat
```

**Manual start:**

```powershell
streamlit run app.py
```

Open the dashboard and paste your `sessionid`, then set your schedule.

---

## 🧭 Usage Guide

1. **Paste Session ID** in the dashboard and click **Save Session ID**.
2. **Set schedule slots** (HH:MM) and click **Save Times**.
3. Drop `.mp4` files into `pending_videos/`.
4. When the time matches, **one video** is uploaded and moved to `posted_videos/`.

---

## 🔧 Configuration

`.env` keys:

```
IG_SESSIONID=your_instagram_sessionid_here
OLLAMA_MODEL=llama3.2:1b
OLLAMA_BASE_URL=http://localhost:11434
QUEUE_SCAN_INTERVAL_SECONDS=30
POST_TOLERANCE_MINUTES=1
POST_DELAY_SECONDS=5
```

---

## 📂 Project Structure

```
neonreel-scheduler/
├── app.py                 # Streamlit dashboard
├── core_pipeline.py       # Scheduler + upload engine
├── caption_agent.py       # Local Ollama captioner
├── start_dashboard.bat    # One-step launcher (Windows)
├── requirements.txt       # Python dependencies
├── .env.example           # Config template
├── schedule_config.json   # Scheduler state
├── pending_videos/        # Drop MP4s here
├── posted_videos/         # Uploaded files move here
├── failed_videos/         # Failed files move here
└── logs/                  # Engine logs
```

---

## 🧾 Scheduler Rules

- The engine **only posts when the clock exactly matches** a slot.
- **Cooldown** prevents multiple uploads in the same minute.
- If no slot matches, the engine logs: **“Next post in X minute(s)”**.

---

## 🧠 Caption Engine

- Sanitizes filenames before prompting the LLM.
- Uses `ollama.chat` with temperature/top_p for unique outputs.
- Strips prompt bleed like “Hook:” or “Caption:”.
- Falls back to randomized captions if Ollama is offline.

---

## 🧯 Troubleshooting

**Port already in use**
- Run with a different port: `streamlit run app.py --server.port 8502`

**Ollama offline**
- Start Ollama and pull the model: `ollama pull llama3.2:1b`

**Login required**
- Refresh your Instagram sessionid and save it again.

---

## 📄 License

MIT

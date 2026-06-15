# Telegram Podcast Digest

Local automation for turning Telegram channel audio into NotebookLM podcast digests.

## Setup

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -e .
```

Install ffmpeg and make sure `ffmpeg -version` works.

Copy `.env.example` to `.env` and fill in Telegram, NotebookLM, and bot values.

Authenticate NotebookLM with the unofficial `notebooklm-py` CLI:

```powershell
notebooklm --storage data/notebooklm_storage_state.json login
notebooklm --storage data/notebooklm_storage_state.json auth check --test
```

Authenticate Telegram user access:

```powershell
tg-podcast-digest setup-telegram
```

## Run

```powershell
tg-podcast-digest doctor
tg-podcast-digest run-once --dry-run
tg-podcast-digest run-once
tg-podcast-digest cleanup
```

Use Windows Task Scheduler to run `tg-podcast-digest run-once` daily from this project directory.


# Telegram Podcast Digest Design

## Summary

Build a local Windows-friendly Python CLI that checks a Telegram channel through a user account, downloads new audio, converts it to MP3, creates one NotebookLM notebook per audio file, asks NotebookLM for a Russian text summary, generates a NotebookLM audio overview, downloads the resulting MP3, and sends the finished podcast plus summary to a Telegram bot chat.

The first version is a local automation tool, not a hosted service. It is meant to run manually with `run-once` and later daily through Windows Task Scheduler.

## Architecture

The application is a Python package named `tg_podcast_digest` with a small CLI and explicit adapters around external systems. The orchestration layer depends on simple ports so most behavior can be tested without Telegram, ffmpeg, NotebookLM, or Telegram Bot API credentials.

SQLite is the source of truth for idempotency. Each source message is keyed by `(chat_id, message_id)` and moves through claimed, downloaded, converted, summarized, podcast-ready, sent, processed, or failed states.

## External Integrations

- Telegram input uses Telethon as a user API client. This avoids Telegram Bot API download limits for larger source files.
- Audio conversion uses an installed `ffmpeg` executable and `libmp3lame`.
- NotebookLM uses `notebooklm-py` with a saved `storage_state.json`. The library is unofficial and may break if Google changes internal APIs.
- Telegram output uses Bot API `sendAudio` with a short caption.

## Public CLI

- `tg-podcast-digest doctor`: validates configuration, local paths, dependency imports, ffmpeg availability, and NotebookLM storage presence.
- `tg-podcast-digest setup-telegram`: starts Telethon login and saves a session file.
- `tg-podcast-digest run-once --dry-run --max-messages N`: lists or processes recent source-channel audio once.
- `tg-podcast-digest cleanup`: removes old local media files according to retention settings.

## Configuration

Configuration is read from `.env` and environment variables. Environment variables override `.env` values.

Required values:

- `TG_API_ID`
- `TG_API_HASH`
- `TG_SOURCE_CHAT`
- `TELEGRAM_BOT_TOKEN`
- `TELEGRAM_OUTPUT_CHAT_ID`
- `NOTEBOOKLM_STORAGE_PATH`

Default paths:

- `DATABASE_PATH=data/podcast_digest.sqlite3`
- `TG_SESSION_PATH=data/telegram.session`
- `DOWNLOAD_DIR=downloads`
- `CONVERTED_DIR=output/converted`
- `EXPORT_DIR=output/exports`
- `FFMPEG_PATH=ffmpeg`

## Pipeline

For each recent Telegram message with supported audio media:

1. Claim the message in SQLite. Already processed messages are skipped.
2. Download the source audio to `downloads/`.
3. Convert it to MP3 with `ffmpeg -y -i INPUT -vn -codec:a libmp3lame -b:a 96k -ar 44100 OUTPUT.mp3`.
4. Create a NotebookLM notebook with a deterministic title based on message date, id, and filename.
5. Upload the converted MP3 as the notebook source.
6. Ask for a Russian structured summary.
7. Generate a Russian NotebookLM audio overview with instructions requesting an approximately 20-minute deep-dive podcast.
8. Download the generated audio overview to `output/exports/`.
9. Send the podcast MP3 to the configured Telegram bot chat and send the full summary as split text messages.
10. Mark the message processed only after Telegram delivery succeeds.

## Failure Behavior

Failures are recorded in SQLite with the message id and error text. Failed messages can be claimed again on a later run. Processed messages are never processed twice unless their state is manually changed.

If NotebookLM or Telegram output fails after local files are created, local files remain for debugging. Partial NotebookLM notebooks may remain as well; `cleanup` only removes local files in v1.

## Testing Strategy

Unit tests cover:

- `.env` parsing and defaults.
- audio-media filtering and deterministic filenames.
- SQLite state transitions and idempotent claiming.
- ffmpeg command construction and conversion failure handling.
- Telegram Bot API message splitting and 50 MB audio guard.
- pipeline success, dry-run, skip, and failure/retry behavior.

Manual acceptance requires one real `doctor`, one `run-once --dry-run`, and one real source-channel audio message producing a NotebookLM notebook, summary, generated MP3, and Telegram delivery.

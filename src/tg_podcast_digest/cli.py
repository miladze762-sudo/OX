from __future__ import annotations

import argparse
import asyncio
import importlib.util
import subprocess
from pathlib import Path

from .audio import FfmpegConverter
from .cleanup import cleanup_old_files
from .config import Settings, load_settings
from .notebooklm_client import NotebookLMProcessor
from .pipeline import PodcastPipeline
from .state import StateStore
from .telegram_bot import TelegramBotClient
from .telegram_source import TelegramSourceClient


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
    try:
        settings = load_settings(args.env)
        if args.command == "doctor":
            return _doctor(settings)
        if args.command == "setup-telegram":
            asyncio.run(_build_source(settings).setup_login())
            print(f"Telegram session saved to {settings.tg_session_path}")
            return 0
        if args.command == "run-once":
            pipeline = _build_pipeline(settings)
            max_messages = args.max_messages or settings.max_messages_per_run
            result = asyncio.run(pipeline.run_once(dry_run=args.dry_run, max_messages=max_messages))
            if args.dry_run:
                for item in result.dry_run_items:
                    print(f"DRY RUN: {item.chat_id}/{item.message_id} | {item.title}")
                print(f"dry_run_count={len(result.dry_run_items)}")
            else:
                print(
                    f"processed={result.processed_count} "
                    f"skipped={result.skipped_count} errors={len(result.errors)}"
                )
                for error in result.errors:
                    print(f"ERROR: {error}")
            return 1 if result.errors else 0
        if args.command == "cleanup":
            deleted = cleanup_old_files(
                [settings.download_dir, settings.converted_dir, settings.export_dir],
                settings.local_retention_days,
            )
            print(f"deleted_files={deleted}")
            return 0
    except Exception as exc:  # noqa: BLE001 - top-level CLI diagnostic.
        print(f"ERROR: {exc}")
        return 1
    parser.print_help()
    return 1


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="tg-podcast-digest")
    parser.add_argument("--env", default=".env", help="Path to .env file")
    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser("doctor", help="Check config and local dependencies")
    subparsers.add_parser("setup-telegram", help="Authorize Telegram user access")
    run_once = subparsers.add_parser("run-once", help="Process new Telegram audio once")
    run_once.add_argument("--dry-run", action="store_true")
    run_once.add_argument("--max-messages", type=int, default=None)
    subparsers.add_parser("cleanup", help="Delete old local generated files")
    return parser


def _build_pipeline(settings: Settings) -> PodcastPipeline:
    return PodcastPipeline(
        source=_build_source(settings),
        converter=FfmpegConverter(settings.ffmpeg_path),
        notebook=NotebookLMProcessor(settings.notebooklm_storage_path),
        sender=TelegramBotClient(settings.telegram_bot_token, settings.telegram_output_chat_id),
        state=StateStore(settings.database_path),
        download_dir=settings.download_dir,
        converted_dir=settings.converted_dir,
        export_dir=settings.export_dir,
    )


def _build_source(settings: Settings) -> TelegramSourceClient:
    return TelegramSourceClient(
        settings.tg_api_id,
        settings.tg_api_hash,
        settings.tg_source_chat,
        settings.tg_session_path,
    )


def _doctor(settings: Settings) -> int:
    checks = {
        "telethon_import": importlib.util.find_spec("telethon") is not None,
        "notebooklm_import": importlib.util.find_spec("notebooklm") is not None,
        "requests_import": importlib.util.find_spec("requests") is not None,
        "notebooklm_storage_path": settings.notebooklm_storage_path.exists(),
        "telegram_session_parent": settings.tg_session_path.parent.exists() or _can_create(settings.tg_session_path.parent),
        "database_parent": settings.database_path.parent.exists() or _can_create(settings.database_path.parent),
        "ffmpeg": _ffmpeg_available(settings.ffmpeg_path),
    }
    for name, ok in checks.items():
        print(f"{name}: {'OK' if ok else 'MISSING'}")
    return 0 if all(checks.values()) else 1


def _ffmpeg_available(ffmpeg_path: str) -> bool:
    try:
        result = subprocess.run(
            [ffmpeg_path, "-version"],
            capture_output=True,
            text=True,
            timeout=10,
        )
    except (OSError, subprocess.TimeoutExpired):
        return False
    return result.returncode == 0


def _can_create(path: Path) -> bool:
    try:
        path.mkdir(parents=True, exist_ok=True)
    except OSError:
        return False
    return True


if __name__ == "__main__":
    raise SystemExit(main())


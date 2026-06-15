import os
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from tg_podcast_digest.config import load_settings


class ConfigTests(unittest.TestCase):
    def test_load_settings_reads_env_file_and_defaults(self):
        with tempfile.TemporaryDirectory() as tmp:
            env_path = Path(tmp) / ".env"
            env_path.write_text(
                "\n".join(
                    [
                        "TG_API_ID=12345",
                        "TG_API_HASH=hash-value",
                        "TG_SOURCE_CHAT=@source_channel",
                        "TELEGRAM_BOT_TOKEN=bot-token",
                        "TELEGRAM_OUTPUT_CHAT_ID=-100987",
                        "NOTEBOOKLM_STORAGE_PATH=data/notebooklm.json",
                    ]
                ),
                encoding="utf-8",
            )

            settings = load_settings(env_path)

        self.assertEqual(12345, settings.tg_api_id)
        self.assertEqual("hash-value", settings.tg_api_hash)
        self.assertEqual("@source_channel", settings.tg_source_chat)
        self.assertEqual(Path("data/telegram.session"), settings.tg_session_path)
        self.assertEqual(Path("downloads"), settings.download_dir)
        self.assertEqual(Path("output/converted"), settings.converted_dir)
        self.assertEqual(Path("output/exports"), settings.export_dir)
        self.assertEqual("ffmpeg", settings.ffmpeg_path)

    def test_environment_variables_override_env_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            env_path = Path(tmp) / ".env"
            env_path.write_text(
                "\n".join(
                    [
                        "TG_API_ID=1",
                        "TG_API_HASH=file-hash",
                        "TG_SOURCE_CHAT=file-chat",
                        "TELEGRAM_BOT_TOKEN=file-token",
                        "TELEGRAM_OUTPUT_CHAT_ID=file-output",
                        "NOTEBOOKLM_STORAGE_PATH=file-storage.json",
                    ]
                ),
                encoding="utf-8",
            )
            old_value = os.environ.get("TG_API_HASH")
            os.environ["TG_API_HASH"] = "env-hash"
            try:
                settings = load_settings(env_path)
            finally:
                if old_value is None:
                    os.environ.pop("TG_API_HASH", None)
                else:
                    os.environ["TG_API_HASH"] = old_value

        self.assertEqual("env-hash", settings.tg_api_hash)

    def test_missing_required_values_are_reported_together(self):
        with tempfile.TemporaryDirectory() as tmp:
            env_path = Path(tmp) / ".env"
            env_path.write_text("TG_API_ID=123\n", encoding="utf-8")

            with self.assertRaisesRegex(ValueError, "TG_API_HASH"):
                load_settings(env_path)


if __name__ == "__main__":
    unittest.main()


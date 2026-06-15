import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from tg_podcast_digest.telegram_source import build_download_path, is_supported_audio


class TelegramSourceTests(unittest.TestCase):
    def test_is_supported_audio_accepts_audio_mime_types_and_extensions(self):
        self.assertTrue(is_supported_audio("episode.opus", None))
        self.assertTrue(is_supported_audio("episode.bin", "audio/mpeg"))
        self.assertTrue(is_supported_audio(None, "audio/ogg"))

    def test_is_supported_audio_rejects_non_audio_media(self):
        self.assertFalse(is_supported_audio("image.jpg", "image/jpeg"))
        self.assertFalse(is_supported_audio("notes.txt", "text/plain"))
        self.assertFalse(is_supported_audio(None, None))

    def test_build_download_path_is_deterministic_and_sanitized(self):
        path = build_download_path(
            Path("downloads"),
            chat_id="-1001",
            message_id=42,
            original_name='My: "Great" Episode?.ogg',
        )

        self.assertEqual(Path("downloads") / "-1001_42_My_Great_Episode.ogg", path)


if __name__ == "__main__":
    unittest.main()


import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from tg_podcast_digest.telegram_bot import TELEGRAM_UPLOAD_LIMIT, TelegramBotClient, split_text


class FakeResponse:
    def __init__(self, payload):
        self._payload = payload

    def raise_for_status(self):
        return None

    def json(self):
        return self._payload


class FakeSession:
    def __init__(self):
        self.calls = []

    def post(self, url, **kwargs):
        self.calls.append((url, kwargs))
        return FakeResponse({"ok": True, "result": {"message_id": len(self.calls)}})


class TelegramBotTests(unittest.TestCase):
    def test_split_text_respects_limit_without_losing_content(self):
        chunks = split_text("alpha\nbeta\ngamma", limit=8)

        self.assertEqual(["alpha\n", "beta\n", "gamma"], chunks)
        self.assertEqual("alpha\nbeta\ngamma", "".join(chunks))

    def test_send_podcast_sends_audio_then_summary_chunks(self):
        with tempfile.TemporaryDirectory() as tmp:
            audio = Path(tmp) / "podcast.mp3"
            audio.write_bytes(b"mp3")
            session = FakeSession()
            client = TelegramBotClient("token", "chat", session=session)

            sent = client.send_podcast("Title", "summary text", audio, "https://notebook")

        self.assertEqual([1, 2], sent)
        self.assertIn("/sendAudio", session.calls[0][0])
        self.assertIn("/sendMessage", session.calls[1][0])
        self.assertEqual("summary text\n\nNotebookLM: https://notebook", session.calls[1][1]["data"]["text"])

    def test_send_podcast_rejects_files_over_bot_api_limit(self):
        with tempfile.TemporaryDirectory() as tmp:
            audio = Path(tmp) / "podcast.mp3"
            with audio.open("wb") as handle:
                handle.truncate(TELEGRAM_UPLOAD_LIMIT + 1)
            client = TelegramBotClient("token", "chat", session=FakeSession())

            with self.assertRaisesRegex(ValueError, "50 MB"):
                client.send_podcast("Title", "summary", audio)


if __name__ == "__main__":
    unittest.main()


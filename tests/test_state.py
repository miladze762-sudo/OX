import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from tg_podcast_digest.state import StateStore


class StateStoreTests(unittest.TestCase):
    def test_claim_message_is_idempotent_after_processed(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = StateStore(Path(tmp) / "state.sqlite3")
            store.initialize()

            self.assertTrue(store.claim_message("chat", 10, "Episode", "2026-06-15"))
            store.mark_sent("chat", 10, [111, 112])

            self.assertFalse(store.claim_message("chat", 10, "Episode", "2026-06-15"))
            record = store.get_message("chat", 10)

        self.assertEqual("processed", record.status)
        self.assertEqual([111, 112], record.telegram_message_ids)

    def test_failed_message_can_be_claimed_again(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = StateStore(Path(tmp) / "state.sqlite3")
            store.initialize()

            self.assertTrue(store.claim_message("chat", 11, "Episode", None))
            store.mark_failed("chat", 11, "network failed")
            self.assertTrue(store.claim_message("chat", 11, "Episode", None))
            record = store.get_message("chat", 11)

        self.assertEqual("processing", record.status)
        self.assertIsNone(record.error)

    def test_records_pipeline_artifacts(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = StateStore(Path(tmp) / "state.sqlite3")
            store.initialize()
            store.claim_message("chat", 12, "Episode", "2026-06-15")
            store.mark_downloaded("chat", 12, Path("downloads/source.ogg"))
            store.mark_converted("chat", 12, Path("output/converted/source.mp3"))
            store.mark_notebook_ready("chat", 12, "nb-123", "https://notebooklm.google.com/notebook/nb-123")
            store.mark_summary_ready("chat", 12, "summary text")
            store.mark_podcast_ready("chat", 12, Path("output/exports/podcast.mp3"))
            record = store.get_message("chat", 12)

        self.assertEqual(Path("downloads/source.ogg"), record.source_path)
        self.assertEqual(Path("output/converted/source.mp3"), record.converted_path)
        self.assertEqual("nb-123", record.notebook_id)
        self.assertEqual("summary text", record.summary)
        self.assertEqual(Path("output/exports/podcast.mp3"), record.podcast_path)


if __name__ == "__main__":
    unittest.main()


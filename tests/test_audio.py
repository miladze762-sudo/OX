import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from tg_podcast_digest.audio import FfmpegConverter, build_ffmpeg_command


class AudioTests(unittest.TestCase):
    def test_build_ffmpeg_command_uses_mp3_lame_settings(self):
        command = build_ffmpeg_command(
            "ffmpeg",
            Path("input/source.ogg"),
            Path("output/source.mp3"),
        )

        self.assertEqual(
            [
                "ffmpeg",
                "-y",
                "-i",
                "input/source.ogg",
                "-vn",
                "-codec:a",
                "libmp3lame",
                "-b:a",
                "96k",
                "-ar",
                "44100",
                "output/source.mp3",
            ],
            command,
        )

    def test_converter_creates_output_path_and_runs_ffmpeg(self):
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / "source.ogg"
            source.write_bytes(b"fake audio")
            converted_dir = Path(tmp) / "converted"
            expected = converted_dir / "source.mp3"

            def fake_run(command, capture_output, text):
                expected.write_bytes(b"mp3")
                return subprocess.CompletedProcess(command, 0, "", "")

            with patch("subprocess.run", side_effect=fake_run) as run:
                result = FfmpegConverter("ffmpeg").convert_to_mp3(source, converted_dir)

        self.assertEqual(expected, result)
        self.assertEqual(1, run.call_count)

    def test_converter_raises_with_stderr_when_ffmpeg_fails(self):
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / "source.ogg"
            source.write_bytes(b"fake audio")

            with patch(
                "subprocess.run",
                return_value=subprocess.CompletedProcess(["ffmpeg"], 1, "", "bad input"),
            ):
                with self.assertRaisesRegex(RuntimeError, "bad input"):
                    FfmpegConverter("ffmpeg").convert_to_mp3(source, Path(tmp) / "converted")


if __name__ == "__main__":
    unittest.main()


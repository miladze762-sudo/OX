from __future__ import annotations

import subprocess
from pathlib import Path


def build_ffmpeg_command(ffmpeg_path: str, source_path: Path, output_path: Path) -> list[str]:
    return [
        ffmpeg_path,
        "-y",
        "-i",
        source_path.as_posix(),
        "-vn",
        "-codec:a",
        "libmp3lame",
        "-b:a",
        "96k",
        "-ar",
        "44100",
        output_path.as_posix(),
    ]


class FfmpegConverter:
    def __init__(self, ffmpeg_path: str = "ffmpeg") -> None:
        self._ffmpeg_path = ffmpeg_path

    def convert_to_mp3(self, source_path: Path, converted_dir: Path) -> Path:
        converted_dir.mkdir(parents=True, exist_ok=True)
        output_path = converted_dir / f"{source_path.stem}.mp3"
        command = build_ffmpeg_command(self._ffmpeg_path, source_path, output_path)
        result = subprocess.run(command, capture_output=True, text=True)
        if result.returncode != 0:
            error = result.stderr.strip() or result.stdout.strip() or "ffmpeg failed"
            raise RuntimeError(error)
        if not output_path.exists():
            raise RuntimeError(f"ffmpeg completed but output was not created: {output_path}")
        return output_path

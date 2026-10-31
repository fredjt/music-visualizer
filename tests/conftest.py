"""Pytest configuration."""

import os
import subprocess

import pytest


def pytest_configure(config):
    """Set base temp directory outside the repo to avoid test artifacts."""
    config.option.basetemp = os.path.join(
        os.environ.get("TMPDIR", "/tmp"), "audio-visualizer-pytest-tmp"
    )


def _make_tone(path: str, seconds: float) -> None:
    """Render a stereo 44.1 kHz sine tone to a WAV file via ffmpeg."""
    subprocess.run(
        [
            "ffmpeg",
            "-y",
            "-hide_banner",
            "-loglevel",
            "error",
            "-f",
            "lavfi",
            "-i",
            f"sine=frequency=440:duration={seconds}",
            "-ar",
            "44100",
            "-ac",
            "2",
            "-c:a",
            "pcm_s16le",
            path,
        ],
        check=True,
        capture_output=True,
        timeout=30,
    )


@pytest.fixture(scope="session")
def smoke_audio(tmp_path_factory) -> dict:
    """Short generated clips for the smoke subset (v2.2.0 sec.4.1/4.2).

    Returns {"1s": path, "2s": path}: a 1 s and a 2 s 440 Hz stereo tone.
    The 2 s clip exists so the slow tap-chain encodes (peak-hold /
    oscilloscope) get their full hold+decay window while staying capped.
    """
    d = tmp_path_factory.mktemp("smoke_audio")
    clips = {}
    for key, seconds in (("1s", 1.0), ("2s", 2.0)):
        path = str(d / f"smoke_{key}.wav")
        _make_tone(path, seconds)
        clips[key] = path
    return clips

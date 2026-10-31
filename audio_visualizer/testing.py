"""
Public testing helpers for audio-visualizer plugin authors (v2.2.0 sec.6.3).

A small public module so third-party plugin distributions can test
against the same contracts the core's own test suite uses, instead of
copy-pasting the repository's test regexes:

- ``make_tone_wav`` / ``make_silence_wav``: generate small (default 1 s)
  WAV fixtures with ffmpeg - deterministic, no audio assets to ship
- ``assert_label_discipline``: the named-pad rules every plugin graph
  must follow for multi-mode compositing to work

Example (a plugin's own test suite)::

    import pytest

    from audio_visualizer.testing import (
        assert_label_discipline,
        make_silence_wav,
        make_tone_wav,
    )

    def test_labels():
        graph = MyPlugin().build_filter(640, 360, 30, {}, audio_index=0)
        assert_label_discipline(graph, "myplugin", main="viz")

    @pytest.fixture(scope="module")
    def tone(tmp_path_factory):
        return make_tone_wav(str(tmp_path_factory.mktemp("a") / "tone.wav"))

See docs/PLUGIN_DEVELOPMENT.md ("Testing a plugin").
"""

from __future__ import annotations

import os
import re
import subprocess

__all__ = [
    "assert_label_discipline",
    "ffmpeg_available",
    "make_silence_wav",
    "make_tone_wav",
]

# ffmpeg pad labels may contain alphanumerics, underscores and hyphens
# (stream specifiers like [0:a] contain ':' and are therefore excluded)
_LABEL_RE = re.compile(r"\[([A-Za-z0-9_-]+)\]")
_LEADING_LABEL_RE = re.compile(r"\[([A-Za-z0-9_-]+)\]\s*")
_TRAILING_LABEL_RE = re.compile(r"\[([A-Za-z0-9_-]+)\]\s*$")


def ffmpeg_available() -> bool:
    """True when the ffmpeg binary is on PATH (fixture generation needs it)."""
    from shutil import which

    return which("ffmpeg") is not None


def _make_wav(path: str, lavfi_source: str, sample_rate: int) -> str:
    if not ffmpeg_available():
        raise RuntimeError(f"ffmpeg is required to generate {path!r} but was not found on PATH")
    result = subprocess.run(
        [
            "ffmpeg",
            "-y",
            "-hide_banner",
            "-loglevel",
            "error",
            "-f",
            "lavfi",
            "-i",
            lavfi_source,
            "-ar",
            str(sample_rate),
            path,
        ],
        capture_output=True,
        text=True,
        timeout=30,
    )
    if result.returncode != 0 or not os.path.exists(path):
        raise RuntimeError(f"ffmpeg failed to write {path!r}: {result.stderr.strip()}")
    return path


def make_tone_wav(
    path: str,
    frequency: float = 440.0,
    duration: float = 1.0,
    sample_rate: int = 44100,
) -> str:
    """Generate a mono sine-tone WAV fixture at *path* and return *path*."""
    return _make_wav(
        path,
        f"sine=frequency={frequency}:duration={duration}",
        sample_rate,
    )


def make_silence_wav(
    path: str,
    duration: float = 1.0,
    sample_rate: int = 44100,
) -> str:
    """Generate a mono silence WAV fixture at *path* and return *path*."""
    return _make_wav(
        path,
        f"anullsrc=r={sample_rate}:cl=mono,atrim=duration={duration}",
        sample_rate,
    )


def assert_label_discipline(graph: str, source: str, main: str = "viz") -> None:
    """Assert a plugin's filter graph follows ffmpeg's named-pad rules.

    Public form of the contract the core's own suite enforces (so
    third-party plugins test against it instead of re-implementing the
    regexes). *source* names the plugin in failure messages; *main* is
    the pad the graph must end with - 'viz' for a raw ``build_filter``
    return, 'out' for a fully composed graph.

    Rules, evaluated in graph order (ffmpeg processes the graph
    sequentially, and a label may be redefined after its last use):

    * every named pad is defined exactly once before it is consumed
    * no named pad is consumed more than once
    * nothing but filters/options sits between the input and output
      pads of a chain
    * the only pad still defined at the end of the graph is [*main*]

    Stream specifiers such as [0:a] are not named pads and are ignored.

    Raises:
        AssertionError: with the offending labels when a rule is broken.
    """
    # Quoted option values may contain brackets; neutralize them
    stripped = re.sub(r"'[^']*'", "''", graph)
    stripped = re.sub(r'"[^"]*"', '""', stripped)

    pending: set[str] = set()
    for chain_index, chain in enumerate(stripped.split(";")):
        c = chain.strip()
        if not c:
            continue

        # Input pads: leading [label] tokens of the chain
        inputs = []
        while True:
            m = _LEADING_LABEL_RE.match(c)
            if not m:
                break
            inputs.append(m.group(1))
            c = c[m.end() :]

        # Output pads: trailing [label] tokens of the chain (fan-out allowed)
        outputs = []
        while True:
            m = _TRAILING_LABEL_RE.search(c)
            if not m:
                break
            outputs.append(m.group(1))
            c = c[: m.start()]

        middle = _LABEL_RE.findall(c)
        assert not middle, (
            f"{source}: unexpected mid-chain labels {middle} in chain "
            f"{chain_index!r} — split the chain with ';'"
        )

        for label in inputs:
            assert label in pending, (
                f"{source}: pad [{label}] consumed in chain {chain_index!r} "
                f"but was never defined (or already consumed)"
            )
            pending.discard(label)
        for label in outputs:
            assert label not in pending, (
                f"{source}: pad [{label}] defined in chain {chain_index!r} "
                f"but is still pending from an earlier chain"
            )
            pending.add(label)

    assert pending == {main}, (
        f"{source}: graph must end with exactly one defined pad [{main}]; "
        f"pending pads: {sorted(pending)}"
    )

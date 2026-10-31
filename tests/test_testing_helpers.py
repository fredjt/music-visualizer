"""
Tests for the public audio_visualizer.testing helpers (v2.2.0 sec.6.3).
"""

from __future__ import annotations

import pytest

from audio_visualizer import testing as th


class TestLabelDiscipline:
    def test_valid_graph_passes(self):
        th.assert_label_discipline(
            "[0:a] showfreqs[s_viz]; [1:v] format=rgba[s_bg]; [s_bg][s_viz]overlay[out]",
            "demo",
            main="out",
        )

    def test_main_parameter_respected(self):
        th.assert_label_discipline(
            "[0:a] showfreqs[s_viz]; [s_viz]format=yuv420p[s_viz2]",
            "demo",
            main="s_viz2",
        )

    def test_undefined_pad_fails(self):
        with pytest.raises(AssertionError, match="never defined"):
            th.assert_label_discipline("[nope] testfilter[out]", "demo")

    def test_double_consume_fails(self):
        with pytest.raises(AssertionError, match="already consumed|never defined"):
            th.assert_label_discipline("testfilter[a]; [a] foo[b]; [a] bar[out]", "demo")

    def test_duplicate_definition_fails(self):
        with pytest.raises(AssertionError, match="still pending"):
            th.assert_label_discipline("testfilter[a]; testfilter[a]; [a] foo[out]", "demo")

    def test_leftover_pad_fails(self):
        with pytest.raises(AssertionError, match="exactly one defined pad"):
            th.assert_label_discipline("testfilter[a]; [a] foo[out]; [out] bar[extra]", "demo")

    def test_mid_chain_label_fails(self):
        with pytest.raises(AssertionError, match="mid-chain"):
            th.assert_label_discipline("[0:a] foo[a] bar[out]", "demo")

    def test_stream_specifiers_ignored(self):
        # [0:a] is a stream specifier, not a named pad; the graph ends in [viz]
        th.assert_label_discipline("[0:a] testfilter[viz]", "demo")


class TestWavFixtures:
    def test_make_tone_wav(self, tmp_path):
        if not th.ffmpeg_available():
            pytest.skip("ffmpeg not available")
        p = str(tmp_path / "tone.wav")
        out = th.make_tone_wav(p, frequency=440, duration=1)
        assert out == p
        import os

        assert os.path.getsize(p) > 1000

    def test_make_silence_wav(self, tmp_path):
        if not th.ffmpeg_available():
            pytest.skip("ffmpeg not available")
        p = str(tmp_path / "silence.wav")
        th.make_silence_wav(p, duration=1)
        import os

        assert os.path.getsize(p) > 1000

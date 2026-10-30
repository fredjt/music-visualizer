"""Unit tests for the multi-mode composite visualizer (--mode a b ...)."""

from argparse import Namespace
from unittest.mock import patch

import pytest

from audio_visualizer.visualizers._composite import CompositeVisualizer
from audio_visualizer.visualizers.albumart import AlbumArtPlugin
from audio_visualizer.visualizers.circular_spectrum import CircularSpectrumPlugin
from audio_visualizer.visualizers.radial import RadialPlugin
from audio_visualizer.visualizers.spectrum import SpectrumPlugin
from audio_visualizer.visualizers.vectorscope import VectorscopePlugin
from audio_visualizer.visualizers.waveform import WaveformPlugin


def _args(width=1280, height=720, **overrides):
    """Build a minimal full args dict for the composite pipeline."""
    base = {
        "input": "song.mp3",
        "output": "song_viz.mp4",
        "width": width,
        "height": height,
        "fps": 30,
        "format": "mp4",
        "preset": "medium",
        "crf": 23,
        "accel": "disabled",
        "verbose": False,
        "colors": None,
        "bg_color": None,
        "border": False,
        "no_metadata": False,
    }
    base.update(overrides)
    return base


class TestCompositeGraph:
    """Filter-graph construction for multi-mode composites."""

    def test_hstack_two_modes(self):
        args = _args(mode_classes=[SpectrumPlugin, WaveformPlugin])
        graph = CompositeVisualizer().build_filter_complex(args)

        assert "hstack=inputs=2" in graph
        assert graph.rstrip().rstrip(";").endswith("[out]")
        # Each sub-mode is namespaced
        assert "[s0_viz]" in graph
        assert "[s1_viz]" in graph
        # No un-namespaced labels that could collide across sub-modes
        assert "[viz]" not in graph
        assert "[bg]" not in graph

    def test_cell_widths_tile_frame_exactly(self):
        # 1000 // 3 = 333; last cell takes the remainder (334)
        args = _args(
            width=1000,
            height=720,
            mode_classes=[SpectrumPlugin, WaveformPlugin, VectorscopePlugin],
        )
        graph = CompositeVisualizer().build_filter_complex(args)

        assert "hstack=inputs=3" in graph
        assert "size=333x720" in graph
        assert graph.count("size=333x720") == 2
        assert "size=334x720" in graph

    def test_each_bg_mode_gets_own_input(self):
        args = _args(mode_classes=[SpectrumPlugin, WaveformPlugin])
        comp = CompositeVisualizer()
        inputs = comp.get_inputs(args)

        # audio + one background source per mode
        assert len(inputs) == 3
        assert inputs[0] == ["-i", "song.mp3"]
        assert all(len(i) >= 2 and i[0] == "-f" and i[1] == "lavfi" for i in inputs[1:])

    def test_no_bg_modes_share_audio_only(self):
        args = _args(mode_classes=[CircularSpectrumPlugin, RadialPlugin])
        inputs = CompositeVisualizer().get_inputs(args)
        assert inputs == [["-i", "song.mp3"]]

        graph = CompositeVisualizer().build_filter_complex(args)
        assert "hstack=inputs=2" in graph
        assert graph.rstrip().rstrip(";").endswith("[out]")

    def test_mixed_bg_and_no_bg_modes(self):
        args = _args(mode_classes=[WaveformPlugin, VectorscopePlugin])
        comp = CompositeVisualizer()
        # audio + waveform's background only
        assert len(comp.get_inputs(args)) == 2
        graph = comp.build_filter_complex(args)
        # waveform (sub 0) references input 1; vectorscope builds no background
        assert "[1:v]" in graph
        assert "[2:v]" not in graph

    def test_sub_options_are_extracted(self):
        args = _args(
            mode_classes=[SpectrumPlugin, WaveformPlugin],
            spectrum_mode="fire",
        )
        graph = CompositeVisualizer().build_filter_complex(args)
        assert "color=fire" in graph

    def test_shared_bg_color_reaches_all_cells(self):
        args = _args(
            mode_classes=[SpectrumPlugin, WaveformPlugin],
            bg_color="112233",
        )
        inputs = CompositeVisualizer().get_inputs(args)
        assert all("c=112233" in " ".join(i) for i in inputs[1:])

    def test_vstack_layout(self):
        args = _args(
            mode_classes=[SpectrumPlugin, WaveformPlugin],
            compose="vstack",
        )
        graph = CompositeVisualizer().build_filter_complex(args)
        assert "vstack=inputs=2" in graph
        # vstack splits the height, keeps the full width
        assert "size=1280x360" in graph
        assert graph.count("size=1280x360") == 2

    def test_tile_layout_pads_missing_cell(self):
        args = _args(
            mode_classes=[SpectrumPlugin, WaveformPlugin, VectorscopePlugin],
            compose="tile",
        )
        graph = CompositeVisualizer().build_filter_complex(args)
        # 3 modes -> 2x2 grid, one black pad fills the corner cell
        assert "[pad3]" in graph
        assert "hstack=inputs=2[row0]" in graph
        assert "hstack=inputs=2[row1]" in graph
        assert "[row0][row1]vstack=inputs=2[out]" in graph
        # 1280/2 x 720/2 cells (with remainders)
        assert "size=640x360" in graph

    def test_tile_even_grid(self):
        args = _args(
            mode_classes=[SpectrumPlugin, WaveformPlugin, VectorscopePlugin, RadialPlugin],
            compose="tile",
        )
        graph = CompositeVisualizer().build_filter_complex(args)
        # 4 modes -> exact 2x2 grid, no pad cells
        assert "[pad" not in graph
        assert "[row0][row1]vstack=inputs=2[out]" in graph

    def test_overlay_layout(self):
        args = _args(
            mode_classes=[SpectrumPlugin, WaveformPlugin, VectorscopePlugin],
            compose="overlay",
        )
        graph = CompositeVisualizer().build_filter_complex(args)
        # every sub renders at full frame size, stacked in order (last on top)
        assert "size=1280x720" in graph
        assert graph.count("size=1280x720") == 3
        assert "[s0_fmt][s1_fmt]overlay=shortest=1:format=auto[ov1]" in graph
        assert "[ov1][s2_fmt]overlay=shortest=1:format=auto[ov2]" in graph
        assert graph.rstrip().rstrip(";").endswith("[out]")

    def test_fit_scale_pads_into_cell(self):
        args = _args(
            mode_classes=[SpectrumPlugin, WaveformPlugin],
            compose="vstack",
            compose_scale="fit",
        )
        comp = CompositeVisualizer()
        # fit renders at full size first
        assert "size=1280x720" in comp.build_filter_complex(args)
        graph = comp.build_filter_complex(args)
        assert "force_original_aspect_ratio=decrease" in graph
        assert "pad=1280:360" in graph
        assert "color=black" in graph

    def test_fit_honors_bg_color_pad(self):
        args = _args(
            mode_classes=[SpectrumPlugin, WaveformPlugin],
            compose="hstack",
            compose_scale="fit",
            bg_color="112233",
        )
        graph = CompositeVisualizer().build_filter_complex(args)
        assert "pad=640:720:(ow-iw)/2:(oh-ih)/2:color=112233" in graph

    def test_unknown_layout_rejected(self):
        args = _args(mode_classes=[SpectrumPlugin, WaveformPlugin], compose="diagonal")
        with pytest.raises(ValueError, match="Unknown compose layout"):
            CompositeVisualizer().build_filter_complex(args)

    def test_albumart_rejected(self):
        args = _args(mode_classes=[SpectrumPlugin, AlbumArtPlugin])
        with pytest.raises(ValueError, match="dedicated video inputs"):
            CompositeVisualizer().build_filter_complex(args)

    def test_too_few_modes(self):
        args = _args(mode_classes=[SpectrumPlugin])
        with pytest.raises(ValueError, match="at least two"):
            CompositeVisualizer().build_filter_complex(args)

    def test_legacy_plugin_with_out_label(self):
        class LegacyPlugin(SpectrumPlugin):
            def build_filter(self, width, height, fps, options, **kwargs):
                return f"[0:a] showvolume=w={width}:h={height},format=yuv420p[out]"

        args = _args(mode_classes=[LegacyPlugin, WaveformPlugin])
        graph = CompositeVisualizer().build_filter_complex(args)
        # Legacy [out] is namespaced and stacked like any other cell
        assert "[s0_out]format=yuv420p" in graph
        assert "hstack=inputs=2" in graph


class TestResolveModes:
    """CLI-level resolution of --mode values."""

    @pytest.fixture()
    def registry(self):
        from audio_visualizer.visualizers.registry import PluginRegistry

        reg = PluginRegistry()
        reg.load_all()
        return reg

    def test_str_normalized_to_list(self, registry):
        from audio_visualizer.core import resolve_mode_classes

        args = Namespace(mode="spectrum")
        classes = resolve_mode_classes(args, registry)
        assert args.mode == ["spectrum"]
        assert classes == [SpectrumPlugin]

    def test_multiple_modes_resolved(self, registry):
        from audio_visualizer.core import mode_label, resolve_mode_classes

        args = Namespace(mode=["spectrum", "waveform"])
        classes = resolve_mode_classes(args, registry)
        assert classes == [SpectrumPlugin, WaveformPlugin]
        assert mode_label(args) == "spectrum+waveform"

    def test_unknown_mode_exits(self, registry):
        from audio_visualizer.core import resolve_mode_classes

        args = Namespace(mode=["spectrum", "does-not-exist"])
        with pytest.raises(SystemExit):
            resolve_mode_classes(args, registry)

    def test_duplicate_mode_exits(self, registry):
        from audio_visualizer.core import resolve_mode_classes

        args = Namespace(mode=["spectrum", "spectrum"])
        with pytest.raises(SystemExit):
            resolve_mode_classes(args, registry)


class TestCompositeCLI:
    """End-to-end CLI wiring for multi-mode (dry run, no encoding)."""

    def test_dry_run_multi_mode(self, capsys):
        from audio_visualizer.__main__ import main

        with patch(
            "sys.argv",
            [
                "audio-visualizer",
                "tests/assets/test.mp3",
                "--mode",
                "spectrum",
                "waveform",
                "--dry-run",
                "--json",
                "--accel",
                "disabled",
            ],
        ):
            main()
        import json

        payload = json.loads(capsys.readouterr().out)
        assert payload["mode"] == "spectrum+waveform"
        cmd = payload["command"]
        filter_complex = cmd[cmd.index("-filter_complex") + 1]
        assert "hstack=inputs=2" in filter_complex

    def test_single_mode_unaffected(self, capsys):
        from audio_visualizer.__main__ import main

        with patch(
            "sys.argv",
            [
                "audio-visualizer",
                "tests/assets/test.mp3",
                "--mode",
                "waveform",
                "--dry-run",
                "--json",
                "--accel",
                "disabled",
            ],
        ):
            main()
        import json

        payload = json.loads(capsys.readouterr().out)
        assert payload["mode"] == "waveform"
        cmd = payload["command"]
        filter_complex = cmd[cmd.index("-filter_complex") + 1]
        assert "hstack" not in filter_complex

    def test_dry_run_multi_mode_unknown(self):
        from audio_visualizer.__main__ import main

        with patch(
            "sys.argv",
            [
                "audio-visualizer",
                "tests/assets/test.mp3",
                "--mode",
                "spectrum",
                "nope",
                "--dry-run",
                "--accel",
                "disabled",
            ],
        ):
            with pytest.raises(SystemExit):
                main()

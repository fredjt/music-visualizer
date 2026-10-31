"""Unit tests for the multi-mode composite visualizer (--mode a b ...)."""

from argparse import Namespace
from unittest.mock import patch

import pytest

from audio_visualizer.visualizers._composite import CompositeVisualizer, find_option_conflicts
from audio_visualizer.visualizers.albumart import AlbumArtPlugin
from audio_visualizer.visualizers.base import PluginMetadata, PluginOption, VisualizerPlugin
from audio_visualizer.visualizers.circular_spectrum import CircularSpectrumPlugin
from audio_visualizer.visualizers.radial import RadialPlugin
from audio_visualizer.visualizers.spectrum import SpectrumPlugin
from audio_visualizer.visualizers.vectorscope import VectorscopePlugin
from audio_visualizer.visualizers.waveform import WaveformPlugin


class _SharedA(VisualizerPlugin):
    """Dummy mode whose shared option allows red/blue."""

    metadata = PluginMetadata(name="shared_a", display_name="Shared A", description="")
    options = [PluginOption("shared-opt", str, "red", "shared option", choices=["red", "blue"])]

    def build_filter(self, width, height, fps, options, **kwargs):
        return f"[0:a] showvolume=w={width}:h={height}:colors={options['shared-opt']},format=yuv420p[viz]"


class _SharedB(VisualizerPlugin):
    """Dummy mode whose shared option only allows green (conflicts with A)."""

    metadata = PluginMetadata(name="shared_b", display_name="Shared B", description="")
    options = [PluginOption("shared-opt", str, "green", "shared option", choices=["green"])]

    def build_filter(self, width, height, fps, options, **kwargs):
        return f"[0:a] showvolume=w={width}:h={height}:mode=line:colors={options['shared-opt']},format=yuv420p[viz]"


class TestOptionScoping:
    """sec.2.3: shared options resolve once, first mode wins on conflicts."""

    @pytest.fixture(autouse=True)
    def _reset_conflict_warnings(self):
        from audio_visualizer.visualizers import _composite

        _composite._warned_conflicts.clear()
        yield
        _composite._warned_conflicts.clear()

    def test_conflicting_option_uses_first_mode_value(self):
        # 'red' is valid for A but not for B; without first-mode-wins
        # pass-through, B's schema validation would raise
        args = _args(mode_classes=[_SharedA, _SharedB], shared_opt="red")
        graph = CompositeVisualizer().build_filter_complex(args)
        # both cells got the first mode's value
        assert graph.count("colors=red") == 2

    def test_conflicting_option_first_mode_default_wins(self):
        args = _args(mode_classes=[_SharedA, _SharedB])
        graph = CompositeVisualizer().build_filter_complex(args)
        assert graph.count("colors=red") == 2  # A's default, not B's 'green'

    def test_no_conflict_when_options_differ(self):
        args = _args(mode_classes=[SpectrumPlugin, WaveformPlugin])
        assert find_option_conflicts([SpectrumPlugin, WaveformPlugin]) == {}
        CompositeVisualizer().build_filter_complex(args)  # no warning path

    def test_conflict_warning_logged(self, caplog):
        args = _args(mode_classes=[_SharedA, _SharedB], shared_opt="blue")
        with caplog.at_level("WARNING"):
            CompositeVisualizer().build_filter_complex(args)
        assert "--shared-opt" in caplog.text
        assert "first mode" in caplog.text
        assert "shared_a" in caplog.text
        assert "shared_b" in caplog.text

    def test_find_option_conflicts_reports_owners(self):
        conflicts = find_option_conflicts([_SharedA, _SharedB, SpectrumPlugin])
        assert set(conflicts) == {"shared-opt"}
        first, others = conflicts["shared-opt"]
        assert first is _SharedA
        assert others == [_SharedB]


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
        class LegacyPlugin(VisualizerPlugin):
            metadata = PluginMetadata(
                name="legacy",
                display_name="Legacy",
                description="Emits the final [out] from build_filter (v1.x style)",
            )

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

    def test_plus_sugar_expands(self, registry):
        from audio_visualizer.core import resolve_mode_classes

        args = Namespace(mode=["spectrum+waveform"])
        classes = resolve_mode_classes(args, registry)
        assert args.mode == ["spectrum", "waveform"]
        assert classes == [SpectrumPlugin, WaveformPlugin]

    def test_mixed_sugar_and_separate(self, registry):
        from audio_visualizer.core import resolve_mode_classes

        args = Namespace(mode=["spectrum+waveform", "vectorscope"])
        classes = resolve_mode_classes(args, registry)
        assert args.mode == ["spectrum", "waveform", "vectorscope"]
        assert classes == [SpectrumPlugin, WaveformPlugin, VectorscopePlugin]

    def test_plus_sugar_empty_element_exits(self, registry):
        from audio_visualizer.core import resolve_mode_classes

        for bad in ("spectrum+", "+waveform", "a+b+"):
            args = Namespace(mode=[bad])
            with pytest.raises(SystemExit):
                resolve_mode_classes(args, registry)


class TestComboPresets:
    """sec.2.4: named combos shown by --list-plugins."""

    @pytest.fixture()
    def registry(self):
        from audio_visualizer.visualizers.registry import PluginRegistry

        reg = PluginRegistry()
        reg.load_all()
        return reg

    def test_list_plugins_shows_combos(self, registry, caplog):
        from audio_visualizer.core import list_plugins

        with caplog.at_level("INFO"):
            list_plugins(registry)
        assert "[combos]" in caplog.text
        assert "spectrum+waveform" in caplog.text
        assert "spectrum+vectorscope" in caplog.text

    def test_category_filter_hides_combos(self, registry, caplog):
        from audio_visualizer.core import list_plugins

        with caplog.at_level("INFO"):
            list_plugins(registry, category="spectrum")
        assert "[combos]" not in caplog.text

    def test_dry_run_plus_sugar(self, capsys):
        from audio_visualizer.__main__ import main

        with patch(
            "sys.argv",
            [
                "audio-visualizer",
                "tests/assets/test.mp3",
                "--mode",
                "spectrum+waveform",
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


class TestPerModeSyntax:
    """v2.2.0 sec.2.1: --mode "name:key=value" per-mode option pairs."""

    @pytest.fixture()
    def registry(self):
        from audio_visualizer.visualizers.registry import PluginRegistry

        reg = PluginRegistry()
        reg.load_all()
        return reg

    # --- parse_mode_spec ---

    def test_bare_name(self):
        from audio_visualizer.core import parse_mode_spec

        assert parse_mode_spec("spectrum") == ("spectrum", {})

    def test_single_pair(self):
        from audio_visualizer.core import parse_mode_spec

        assert parse_mode_spec("spectrum:bg_color=navy") == (
            "spectrum",
            {"bg_color": "navy"},
        )

    def test_multiple_pairs(self):
        from audio_visualizer.core import parse_mode_spec

        assert parse_mode_spec("spectrum:bg_color=navy,opacity=0.5") == (
            "spectrum",
            {"bg_color": "navy", "opacity": "0.5"},
        )

    def test_value_containing_comma(self):
        # colors=red,blue is one value, not two keys
        from audio_visualizer.core import parse_mode_spec

        assert parse_mode_spec("spectrum:colors=red,blue,bg_color=navy") == (
            "spectrum",
            {"colors": "red,blue", "bg_color": "navy"},
        )

    def test_missing_value_exits(self):
        from audio_visualizer.core import parse_mode_spec

        with pytest.raises(SystemExit):
            parse_mode_spec("spectrum:bg_color")

    def test_empty_name_exits(self):
        from audio_visualizer.core import parse_mode_spec

        with pytest.raises(SystemExit):
            parse_mode_spec(":bg_color=navy")

    def test_garbage_exits(self):
        from audio_visualizer.core import parse_mode_spec

        with pytest.raises(SystemExit):
            parse_mode_spec("spectrum:novalue")

    # --- key resolution + validation ---

    def test_prefix_stripped_key_resolved(self, registry):
        from audio_visualizer.core import resolve_mode_classes

        args = Namespace(mode=[["vectorscope:zoom=1.5"]])
        resolve_mode_classes(args, registry)
        assert args.mode_specs == [("vectorscope", {"vectorscope-zoom": "1.5"})]

    def test_full_schema_name_accepted(self, registry):
        from audio_visualizer.core import resolve_mode_classes

        args = Namespace(mode=[["vectorscope:vectorscope-zoom=2.0"]])
        resolve_mode_classes(args, registry)
        assert args.mode_specs == [("vectorscope", {"vectorscope-zoom": "2.0"})]

    def test_global_bg_color_accepted(self, registry):
        from audio_visualizer.core import resolve_mode_classes

        args = Namespace(mode=[["spectrum:bg_color=navy", "vectorscope"]])
        resolve_mode_classes(args, registry)
        assert args.mode_specs == [("spectrum", {"bg_color": "navy"}), ("vectorscope", {})]

    def test_opacity_accepted(self, registry):
        from audio_visualizer.core import resolve_mode_classes

        args = Namespace(mode=[["spectrum", "vectorscope:opacity=0.5"]])
        resolve_mode_classes(args, registry)
        assert args.mode_specs == [("spectrum", {}), ("vectorscope", {"opacity": "0.5"})]

    def test_unknown_option_exits(self, registry):
        from audio_visualizer.core import resolve_mode_classes

        args = Namespace(mode=[["spectrum:bogus=1"]])
        with pytest.raises(SystemExit):
            resolve_mode_classes(args, registry)

    def test_bad_value_exits(self, registry):
        from audio_visualizer.core import resolve_mode_classes

        args = Namespace(mode=[["vectorscope:zoom=abc"]])
        with pytest.raises(SystemExit):
            resolve_mode_classes(args, registry)

    def test_bad_color_exits(self, registry):
        from audio_visualizer.core import resolve_mode_classes

        args = Namespace(mode=[["spectrum:bg_color=notacolor"]])
        with pytest.raises(SystemExit):
            resolve_mode_classes(args, registry)

    def test_opacity_range_exits(self, registry):
        from audio_visualizer.core import resolve_mode_classes

        for bad in ("1.5", "-0.1"):
            args = Namespace(mode=[["spectrum", "vectorscope:opacity=" + bad]])
            with pytest.raises(SystemExit):
                resolve_mode_classes(args, registry)

    def test_single_mode_applies_pair_to_args(self, registry):
        from audio_visualizer.core import resolve_mode_classes

        args = Namespace(mode=[["spectrum:bg_color=navy"]], bg_color="black")
        resolve_mode_classes(args, registry)
        assert args.bg_color == "navy"

    # --- composite graph ---

    def test_per_mode_bg_color_sets_only_that_sub_input(self, registry):
        from audio_visualizer.core import build_args_dict, resolve_mode_classes

        args = Namespace(
            input="x.mp3",
            output="o.mp4",
            resolution="640x360",
            fps=10,
            preset="ultrafast",
            crf=23,
            format="mp4",
            accel="disabled",
            bg_color=None,
            colors=None,
            verbose=False,
            mode=[["spectrum:bg_color=navy", "vectorscope"]],
        )
        classes = resolve_mode_classes(args, registry)
        ad = build_args_dict(args, width=640, height=360, mode_classes=classes)
        inputs = CompositeVisualizer().get_inputs(ad)
        joined = " ".join(str(x) for grp in inputs for x in grp)
        # the paired sub-mode's background source is navy
        assert "c=navy" in joined
        # the global bg (None) is not navy, so only one navy source exists
        assert joined.count("c=navy") == 1

    def test_global_bg_still_applies_to_unpaired_mode(self, registry):
        from audio_visualizer.core import build_args_dict, resolve_mode_classes

        args = Namespace(
            input="x.mp3",
            output="o.mp4",
            resolution="640x360",
            fps=10,
            preset="ultrafast",
            crf=23,
            format="mp4",
            accel="disabled",
            bg_color="teal",
            colors=None,
            verbose=False,
            mode=[["spectrum:bg_color=navy", "bars"]],
        )
        classes = resolve_mode_classes(args, registry)
        ad = build_args_dict(args, width=640, height=360, mode_classes=classes)
        inputs = CompositeVisualizer().get_inputs(ad)
        joined = " ".join(str(x) for grp in inputs for x in grp)
        # per-mode navy wins for spectrum; the global teal still applies
        # to the unpaired mode (precedence: pair > global > config > default)
        assert "c=navy" in joined
        assert "c=teal" in joined


class TestComposeGrid:
    """v2.2.0 sec.2.2: --compose-grid ROWSxCOLS tile placement."""

    @pytest.fixture()
    def registry(self):
        from audio_visualizer.visualizers.registry import PluginRegistry

        reg = PluginRegistry()
        reg.load_all()
        return reg

    def _build(self, registry, modes, grid=None, bg=None, layout="tile"):
        from audio_visualizer.core import build_args_dict, resolve_mode_classes

        args = Namespace(
            input="x.mp3",
            output="o.mp4",
            resolution="640x360",
            fps=10,
            preset="ultrafast",
            crf=23,
            format="mp4",
            accel="disabled",
            bg_color=bg,
            colors=None,
            verbose=False,
            mode=[list(modes)],
            compose=layout,
            compose_scale="fill",
            compose_grid=grid,
        )
        classes = resolve_mode_classes(args, registry)
        ad = build_args_dict(args, width=640, height=360, mode_classes=classes)
        return CompositeVisualizer().build_filter(640, 360, 10, {}, args=ad)

    def test_default_grid_unchanged(self, registry):
        # 5 modes -> ceil(sqrt(5))=3 cols, ceil(5/3)=2 rows -> 6 cells, 1 pad
        graph = self._build(registry, ["spectrum", "waveform", "bars", "peakbars", "cqt"])
        assert graph.count("hstack=inputs=3") == 2
        assert "vstack=inputs=2" in graph
        assert "pad5" in graph

    def test_explicit_grid_places_cells(self, registry):
        # 4 modes in a single row
        graph = self._build(registry, ["spectrum", "waveform", "bars", "peakbars"], "1x4")
        assert "hstack=inputs=4" in graph
        assert "vstack" not in graph
        assert "pad" not in graph

    def test_grid_larger_than_modes_pads(self, registry):
        # 5 modes in a 3x3 grid -> 4 background pads
        graph = self._build(registry, ["spectrum", "waveform", "bars", "peakbars", "cqt"], "3x3")
        assert graph.count("hstack=inputs=3") == 3
        assert "vstack=inputs=3" in graph
        assert sum(f"pad{k}" in graph for k in range(5, 9)) == 4

    def test_pad_uses_bg_color(self, registry):
        graph = self._build(registry, ["spectrum", "waveform"], "2x2", bg="teal")
        assert "color=c=teal" in graph

    def test_grid_too_small_raises(self, registry):
        with pytest.raises(ValueError):
            self._build(registry, ["spectrum", "waveform", "bars"], "1x2")

    def test_bad_grid_format_raises(self, registry):
        for bad in ("2", "xx2", "2x", "-1x2"):
            with pytest.raises(ValueError):
                self._build(registry, ["spectrum", "waveform"], bad)

    def test_grid_with_non_tile_layout_raises(self, registry):
        with pytest.raises(ValueError):
            self._build(registry, ["spectrum", "waveform"], "2x2", layout="hstack")


class TestOverlayOpacity:
    """v2.2.0 sec.2.3: per-mode opacity on --compose overlay."""

    @pytest.fixture()
    def registry(self):
        from audio_visualizer.visualizers.registry import PluginRegistry

        reg = PluginRegistry()
        reg.load_all()
        return reg

    def _overlay_graph(self, registry, modes):
        from audio_visualizer.core import build_args_dict, resolve_mode_classes

        args = Namespace(
            input="x.mp3",
            output="o.mp4",
            resolution="640x360",
            fps=10,
            preset="ultrafast",
            crf=23,
            format="mp4",
            accel="disabled",
            bg_color=None,
            colors=None,
            verbose=False,
            mode=[list(modes)],
            compose="overlay",
            compose_scale="fill",
            compose_grid=None,
        )
        classes = resolve_mode_classes(args, registry)
        ad = build_args_dict(args, width=640, height=360, mode_classes=classes)
        return CompositeVisualizer().build_filter(640, 360, 10, {}, args=ad)

    def test_mid_layer_blends(self, registry):
        graph = self._overlay_graph(registry, ["spectrum", "vectorscope:opacity=0.5", "bars"])
        assert "colorchannelmixer=aa=0.50" in graph
        assert "[s1_op]" in graph
        # the last mode is always opaque: no blend step for s2
        assert "s2_op" not in graph

    def test_last_mode_ignores_opacity(self, registry):
        graph = self._overlay_graph(registry, ["spectrum", "vectorscope:opacity=0.4"])
        # the last mode is always opaque: the overlay chain is unblended
        assert "s1_op" not in graph
        assert "[s0_fmt][s1_fmt]overlay=shortest=1:format=auto[ov1]" in graph

    def test_no_pairs_unchained(self, registry):
        graph = self._overlay_graph(registry, ["spectrum", "vectorscope"])
        assert "s1_op" not in graph
        assert "[s0_fmt][s1_fmt]overlay=shortest=1:format=auto[ov1]" in graph

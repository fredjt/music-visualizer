"""Contract tests for the plugin system (v2.1.0 goal 6.1).

Three pillars, all parametrized across every loaded plugin:

1. Schema contracts   — metadata and option schemas are well-formed
2. Filter contracts   — build_filter_complex() output is a structurally
                        valid ffmpeg filter graph (named-pad rules),
                        replacing brittle exact-string matching
3. CLI flag contracts — auto-generated flags match the option schemas
"""

import argparse
import re
from pathlib import Path

import pytest

from audio_visualizer.__main__ import build_parser
from audio_visualizer.visualizers.base import PluginOption
from audio_visualizer.visualizers.registry import PluginRegistry

# ---------------------------------------------------------------------------
# Module-level fixtures: one registry + one parser for the whole module
# ---------------------------------------------------------------------------


def _make_registry() -> PluginRegistry:
    registry = PluginRegistry()
    registry.load_all()
    return registry


_REGISTRY = _make_registry()
PLUGIN_NAMES = sorted(_REGISTRY.get_all())
ALL_PLUGINS = pytest.mark.parametrize("plugin_name", PLUGIN_NAMES)
_PARSER = build_parser(_REGISTRY)


def _globals_only_parser() -> argparse.ArgumentParser:
    """Parser with the global flags but no plugin flags (empty registry)."""
    registry = PluginRegistry()
    registry.load_all()
    registry._plugins.clear()  # noqa: SLF001 - test-only access
    return build_parser(registry)


# ---------------------------------------------------------------------------
# Pillar 1: schema contracts
# ---------------------------------------------------------------------------


class TestSchemaContracts:
    """Metadata and option schemas must be well-formed for every plugin."""

    @ALL_PLUGINS
    def test_metadata_contract(self, plugin_name):
        cls = _REGISTRY.get(plugin_name)
        assert cls is not None
        meta = cls.get_metadata()

        # name is the --mode value: lowercase, hyphens, no surprises
        assert meta.name == plugin_name
        assert re.fullmatch(r"[a-z][a-z0-9-]*", meta.name), (
            f"metadata name {meta.name!r} is not a valid --mode value"
        )
        assert meta.display_name, "display_name is required"
        assert meta.description, "description is required"
        assert re.fullmatch(r"\d+\.\d+\.\d+", meta.version), (
            f"version {meta.version!r} must be X.Y.Z"
        )
        assert isinstance(meta.category, str) and meta.category
        if meta.icon is not None:
            assert isinstance(meta.icon, str)
        if meta.requires_ffmpeg_version is not None:
            assert re.fullmatch(r"\d+\.\d+", meta.requires_ffmpeg_version)
        assert isinstance(meta.input_types, list)
        assert all(isinstance(t, str) and t for t in meta.input_types)

    @ALL_PLUGINS
    def test_options_contract(self, plugin_name):
        cls = _REGISTRY.get(plugin_name)
        assert cls is not None
        options = cls.options

        assert isinstance(options, list)
        names = [opt.name for opt in options]
        assert len(names) == len(set(names)), f"duplicate option names: {names}"

        for opt in options:
            assert isinstance(opt, PluginOption)
            assert opt.name and re.fullmatch(r"[a-z][a-z0-9_-]*", opt.name), (
                f"invalid option name {opt.name!r}"
            )
            assert opt.type in (str, int, float, bool), (
                f"option {opt.name!r}: unsupported type {opt.type!r}"
            )
            assert opt.default is not None, f"option {opt.name!r}: default is None"

            # Default must be typed correctly (bool is an int subclass)
            if opt.type is int:
                assert type(opt.default) is int, f"option {opt.name!r}: int default"
            elif opt.type is float:
                assert isinstance(opt.default, (int, float)) and not isinstance(
                    opt.default, bool
                ), f"option {opt.name!r}: float default"
            elif opt.type is bool:
                assert isinstance(opt.default, bool), f"option {opt.name!r}: bool default"
            else:
                assert isinstance(opt.default, str), f"option {opt.name!r}: str default"

            # Default must survive its own validation (type/choices/range)
            assert opt.validate(opt.default) == opt.default, (
                f"option {opt.name!r}: default {opt.default!r} fails validation"
            )
            if opt.choices is not None:
                assert isinstance(opt.choices, (list, tuple)) and opt.choices
                for choice in opt.choices:
                    assert opt.validate(choice) == choice, (
                        f"option {opt.name!r}: choice {choice!r} fails validation"
                    )
            if opt.range is not None:
                assert len(opt.range) == 2
                for bound in opt.range:
                    assert bound is None or (
                        isinstance(bound, (int, float)) and not isinstance(bound, bool)
                    ), f"option {opt.name!r}: invalid range {opt.range!r}"

        # get_options() must agree with the options list
        assert cls.get_options() == {opt.name: opt for opt in options}

    @ALL_PLUGINS
    def test_build_filter_implemented(self, plugin_name):
        """Every plugin implements build_filter() itself (registry contract)."""
        cls = _REGISTRY.get(plugin_name)
        assert cls is not None
        assert "build_filter" in cls.__dict__


# ---------------------------------------------------------------------------
# Pillar 2: filter graph contracts
# ---------------------------------------------------------------------------

# ffmpeg pad labels may contain alphanumerics, underscores and hyphens
# (stream specifiers like [0:a] contain ':' and are therefore excluded)
_LABEL_RE = re.compile(r"\[([A-Za-z0-9_-]+)\]")
_LEADING_LABEL_RE = re.compile(r"\[([A-Za-z0-9_-]+)\]\s*")
_TRAILING_LABEL_RE = re.compile(r"\[([A-Za-z0-9_-]+)\]\s*$")


def _assert_valid_graph(graph: str, context: str) -> None:
    """Assert the filter graph follows ffmpeg's named-pad rules.

    Rules, evaluated in graph order (ffmpeg processes the graph sequentially,
    and a label may be redefined after its last use — e.g. border
    post-processing consumes and re-emits [out]):
      * every named pad is defined exactly once before it is consumed
      * no named pad is consumed more than once
      * the only pad still defined at the end of the graph is [out]

    Stream specifiers such as [0:a] are not named pads and are ignored.
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

        # Nothing but filters/options may sit between the input and output
        # pads of a chain
        middle = _LABEL_RE.findall(c)
        assert not middle, (
            f"{context}: unexpected mid-chain labels {middle} in chain "
            f"{chain_index!r} — split the chain with ';'"
        )

        for label in inputs:
            assert label in pending, (
                f"{context}: pad [{label}] consumed in chain {chain_index!r} "
                f"but was never defined (or already consumed)"
            )
            pending.discard(label)
        for label in outputs:
            assert label not in pending, (
                f"{context}: pad [{label}] defined in chain {chain_index!r} "
                f"but is still pending from an earlier chain"
            )
            pending.add(label)

    assert pending == {"out"}, (
        f"{context}: graph must end with exactly one defined pad [out]; "
        f"pending pads: {sorted(pending)}"
    )


BASE_ARGS = {
    "input": "tests/assets/test.mp3",
    "output": "out.mp4",
    "width": 1280,
    "height": 720,
    "fps": 30,
    "format": "mp4",
    "accel": "sw",
    "preset": "medium",
    "crf": 23,
    "image": str(Path(__file__).parent / "assets" / "album.jpg"),
}

# Scenarios that exercise different code paths of the pipeline (defaults,
# custom colors, explicit background, and border post-processing)
SCENARIOS = {
    "defaults": {},
    "colors": {"colors": "red,blue,white"},
    "bg_color": {"bg_color": "navy"},
    "border": {"border": True, "border_color": "ff0000", "border_width": 4},
}


class TestFilterGraphContracts:
    """build_filter_complex() output must be a structurally valid graph."""

    @ALL_PLUGINS
    @pytest.mark.parametrize("scenario", list(SCENARIOS), ids=list(SCENARIOS))
    def test_filter_graph_structure(self, plugin_name, scenario):
        cls = _REGISTRY.get(plugin_name)
        assert cls is not None
        args = {**BASE_ARGS, **SCENARIOS[scenario]}
        graph = cls().build_filter_complex(args)
        assert isinstance(graph, str) and graph.strip()
        _assert_valid_graph(graph, context=f"{plugin_name}/{scenario}")

    @ALL_PLUGINS
    def test_build_filter_returns_graph(self, plugin_name):
        """The raw build_filter() return must define its main output label."""
        cls = _REGISTRY.get(plugin_name)
        assert cls is not None
        plugin = cls()
        options = cls.validate_options({})
        raw = plugin.build_filter(1280, 720, 30, options=options)

        if isinstance(raw, dict):
            # Multi-output: first key is the main output
            assert raw, "multi-output dict must not be empty"
            for label, segment in raw.items():
                assert re.fullmatch(r"[A-Za-z0-9_-]+", label), f"bad label {label!r}"
                assert segment.strip(), f"{label}: empty segment"
        else:
            assert isinstance(raw, str) and raw.strip()
            main_label = plugin.get_output_label(options)
            assert f"[{main_label}]" in raw, (
                f"build_filter() must define the main output label [{main_label}]"
            )


class TestGraphCheckerNegatives:
    """The structure checker itself must reject invalid graphs."""

    def test_undefined_label_rejected(self):
        with pytest.raises(AssertionError, match="never defined"):
            _assert_valid_graph("[a]format=yuv420p[b]; [b][c]overlay[out]", "test")

    def test_double_consumption_rejected(self):
        with pytest.raises(AssertionError, match="never defined"):
            _assert_valid_graph(
                "color=s=100x100[bg]; [bg]scale=50:50[x]; [bg]scale=50:50[y]; [x][y]hstack[out]",
                "test",
            )

    def test_double_definition_rejected(self):
        with pytest.raises(AssertionError, match="still pending"):
            _assert_valid_graph(
                "color=s=100x100[x]; color=s=100x100[x]; [x]scale=10:10[out]", "test"
            )

    def test_missing_final_out_rejected(self):
        with pytest.raises(AssertionError, match="exactly one defined pad \\[out\\]"):
            _assert_valid_graph("color=s=100x100[final]", "test")

    def test_mid_chain_label_rejected(self):
        with pytest.raises(AssertionError, match="mid-chain"):
            _assert_valid_graph("[a]scale=10:10[m]format=yuv420p[out]", "test")

    def test_label_redefined_after_use_accepted(self):
        """Border post-processing consumes and re-emits [out]; legal in ffmpeg."""
        _assert_valid_graph(
            "color=s=100x100[out]; [out]format=rgba[out_viz]; "
            "color=s=200x200[border]; [border][out_viz]overlay=5:5[out]",
            "test",
        )


# ---------------------------------------------------------------------------
# Pillar 3: CLI flag contracts
# ---------------------------------------------------------------------------


class TestCLIFlagContracts:
    """Auto-generated flags must match the option schemas exactly."""

    @ALL_PLUGINS
    def test_plugin_flags_match_schema(self, plugin_name):
        cls = _REGISTRY.get(plugin_name)
        assert cls is not None
        for opt in cls.options:
            flag = f"--{opt.name.replace('_', '-')}"
            actions = [a for a in _PARSER._actions if flag in a.option_strings]
            assert len(actions) == 1, (
                f"{plugin_name}: {flag} must be generated exactly once (found {len(actions)})"
            )
            action = actions[0]
            assert action.default == opt.default, (
                f"{flag}: CLI default {action.default!r} != schema {opt.default!r}"
            )
            if opt.type is bool:
                assert action.const is True, f"{flag}: bool options must be store_true"
            else:
                assert action.type is opt.type, (
                    f"{flag}: CLI type {action.type!r} != schema {opt.type!r}"
                )
            if opt.choices is not None:
                assert list(action.choices or []) == list(opt.choices), f"{flag}: choices mismatch"
            expected_help = opt.help or f"Default: {opt.default}"
            assert action.help == expected_help, f"{flag}: help text mismatch"

    def test_plugin_flags_unique_across_plugins(self):
        flags = [
            f"--{opt.name.replace('_', '-')}"
            for cls in _REGISTRY.get_all().values()
            for opt in cls.options
        ]
        dupes = {f for f in flags if flags.count(f) > 1}
        assert not dupes, f"duplicate plugin flags: {dupes}"

    def test_plugin_flags_do_not_collide_with_global_flags(self):
        """A schema option must never shadow a built-in global flag."""
        global_flags = {
            s
            for a in _globals_only_parser()._actions
            for s in a.option_strings  # noqa: SLF001
        }
        plugin_flags = {
            f"--{opt.name.replace('_', '-')}"
            for cls in _REGISTRY.get_all().values()
            for opt in cls.options
        }
        collisions = global_flags & plugin_flags
        assert not collisions, (
            f"plugin options collide with global flags: {collisions} "
            f"— rename the option or the global flag"
        )

    def test_all_schema_options_generate_flags(self):
        """No option is silently dropped by the flag generator."""
        for name, cls in _REGISTRY.get_all().items():
            for opt in cls.options:
                flag = f"--{opt.name.replace('_', '-')}"
                assert any(flag in a.option_strings for a in _PARSER._actions), (
                    f"{name}: option {opt.name!r} generated no CLI flag"
                )

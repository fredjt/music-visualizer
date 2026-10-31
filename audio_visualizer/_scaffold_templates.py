"""Template text for `audio-visualizer new-plugin` (v2.2.0 sec.6.1).

Plain-text templates with {{NAME}}, {{PKG}}, {{CLS}}, {{DISPLAY}}
placeholders; scaffold_plugin() substitutes them. The plugin.py
template doubles as the canonical minimal plugin example.
"""

PYPROJECT_TMPL = """[build-system]
requires = ["setuptools>=61"]
build-backend = "setuptools.build_meta"

[project]
name = "{{NAME}}-plugin"
version = "0.1.0"
description = "The {{DISPLAY}} audio-visualizer plugin"
requires-python = ">=3.9"
dependencies = [
    "musicvisualizer>=2.2",
]

[project.entry-points."audio-visualizer.plugins"]
{{NAME}} = "{{PKG}}.plugin:{{CLS}}"

[tool.setuptools.packages.find]
include = ["{{PKG}}*"]
"""

PLUGIN_TMPL = '''"""The {{NAME}} visualizer - canonical minimal plugin (v2.2.0 sec.6.1).

Edit this file, then `pip install -e .` and check with:
    audio-visualizer --list-plugins
"""

from audio_visualizer.visualizers.base import (
    PluginMetadata, PluginOption, VisualizerPlugin,
)


class {{CLS}}(VisualizerPlugin):
    metadata = PluginMetadata(
        name="{{NAME}}",
        display_name="{{DISPLAY}}",
        description="A minimal example visualizer (template)",
        version="0.1.0",
        category="other",
        # Uncomment when the graph needs newer ffmpeg / core features:
        # requires_ffmpeg_version="7.0",
        # requires_core_version="2.2",
    )

    options = [
        PluginOption(
            "{{NAME}}-intensity", float, 1.0,
            "Intensity multiplier", range=(0.1, 4.0),
        ),
    ]
'''

PLUGIN_TMPL += """
    def build_filter(self, width, height, fps, options, audio_index=0,
                     video_index=1, colors=None, bg_color=None, args=None,
                     **kwargs):
        # Label discipline: every intermediate pad is defined once and
        # consumed once; the main output is [viz] - the core composes
        # the background and [out] for you.
        return (
            f"[{audio_index}:a] showspectrum=size={width}x{height}"
            f":mode=combined:color=intensity:scale=log:overlap=0.8,"
            f"format=yuv420p[viz]"
        )
"""

INIT_TMPL = '''"""The {{NAME}} plugin package."""
from .plugin import {{CLS}}

__all__ = ["{{CLS}}"]
'''

TEST_TMPL = '''"""Label-discipline test for the {{NAME}} plugin (template)."""
from audio_visualizer.testing import assert_label_discipline

from {{PKG}}.plugin import {{CLS}}


def test_labels():
    plugin = {{CLS}}()
    graph = plugin.build_filter(640, 360, 30, {}, audio_index=0)
    assert_label_discipline(graph, "{{NAME}}")


def test_schema():
    meta = {{CLS}}.get_metadata()
    assert meta.name == "{{NAME}}"
    names = [o.name for o in {{CLS}}.get_options().values()]
    assert "{{NAME}}-intensity" in names
'''

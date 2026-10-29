"""
Shared filter-graph utilities for visualizer plugins.

Provides helper functions to build common filter segments (background
sources) so plugins don't duplicate the same boilerplate.

Note: final [out] composition is handled by the base class (see
VisualizerPlugin.compose_final_filter), not by plugins.

Usage:
    from audio_visualizer.visualizers.utils import build_background

    bg = build_background(video_index, bg_color)  # e.g. for custom composition
"""


def build_background(video_index: int, bg_color: str | None = None, opacity: float = 0.3) -> str:
    """
    Build the background filter segment.

    Takes the background video input (typically a solid-color lavfi source)
    and prepares it for overlay. If bg_color is provided the background is
    fully opaque; otherwise it is semi-transparent.

    Args:
        video_index: Index of the background video input in the ffmpeg command.
        bg_color: If provided, the background is fully opaque (aa=1.0).
                  If None, the background uses the given opacity.
        opacity: Alpha for the background when bg_color is None (default 0.3).

    Returns:
        Filter segment: "[{video_index}:v] format=rgba,colorchannelmixer=aa={alpha}[bg]; "
    """
    alpha = 1.0 if bg_color else opacity
    return f"[{video_index}:v] format=rgba,colorchannelmixer=aa={alpha}[bg]; "


def build_color_background(color: str | None, width: int, height: int, opacity: float = 0.3) -> str:
    """
    Build a self-contained color/nullsrc background filter segment.

    Used when a plugin needs a background of a specific size that is not
    the standard video input (e.g. radial uses 2× height for mirroring).

    Args:
        color: Background color as hex string. If None, uses nullsrc with opacity.
        width: Background width in pixels.
        height: Background height in pixels.
        opacity: Alpha for nullsrc when color is None (default 0.3).

    Returns:
        Filter segment ending with [bg] (no trailing semicolon).
    """
    if color:
        return f"color=c={color}:s={width}x{height},format=yuv420p[bg]"
    return f"nullsrc=size={width}x{height},format=yuv420p,colorchannelmixer=aa={opacity}[bg]"

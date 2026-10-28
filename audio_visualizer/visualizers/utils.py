"""
Shared filter-graph utilities for visualizer plugins.

Provides helper functions to build common filter segments (background,
output composition) so plugins don't duplicate the same boilerplate.

Usage:
    from audio_visualizer.visualizers.utils import build_background, compose_output

    bg = build_background(video_index, bg_color)
    viz = f"[{audio_index}:a] showspectrum=...[viz]; "
    return compose_output(viz, bg)
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


def compose_output(viz_filter: str, bg_filter: str, output_label: str = "out") -> str:
    """
    Compose the final output by overlaying the visualization on the background.

    Args:
        viz_filter: The visualization filter segment. Must end with a
                    "[viz]; " label so the overlay can reference it.
        bg_filter: The background filter segment (from build_background).
        output_label: The final output label (default "out").

    Returns:
        Complete filter_complex string with the final output label.

    Example:
        >>> viz = "[0:a] showspectrum=size=1280x720[viz]; "
        >>> bg = build_background(1, "black")
        >>> compose_output(viz, bg)
        '[0:a] showspectrum=size=1280x720[viz]; [1:v] format=rgba,colorchannelmixer=aa=1.0[bg]; [bg][viz] overlay=shortest=1:format=auto [out]'
    """
    return f"{viz_filter}{bg_filter}[bg][viz] overlay=shortest=1:format=auto [{output_label}]"


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

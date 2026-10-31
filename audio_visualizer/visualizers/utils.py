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


# Upper bound on the number of delay taps for peak-hold chains. Each tap
# adds a few filter instances and a small buffer; 60 taps (2 s at 30 fps)
# keeps the graph size and memory in check. hold+decay requests beyond the
# budget are scaled down proportionally.
PEAK_HOLD_MAX_TAPS = 60

# A tap whose weight falls below 1/255 of the original amplitude is
# invisible in 8-bit video, so the decay lambda is chosen to reach it at
# the end of the decay window.
PEAK_HOLD_FLOOR = 1.0 / 255.0


def build_peak_hold_chain(
    src_label: str,
    fps: int,
    hold_seconds: float,
    decay_seconds: float,
    prefix: str,
    max_taps: int = PEAK_HOLD_MAX_TAPS,
) -> tuple[str | None, str]:
    """
    Build a filter-graph segment implementing peak-hold with decay.

    The output at time t is the per-pixel maximum over the last N frames,
    each attenuated by a weight:

        out_t = max over i in 0..N-1 of ( w_i * frame_{t-i} )

        w_i = 1.0                        for i < hold_frames  (flat hold)
        w_i = lambda ** (i - hold_frames) for i >= hold_frames (decay)

    with lambda chosen so the weight reaches PEAK_HOLD_FLOOR (1/255) at
    the end of the decay window.

    Mechanics (pure filter chain, no per-frame processing):
      * one ``split`` fans the source out to N taps
      * tap i >= 1 is delayed i frames with ``tmix`` (``frames=i+1`` with
        weight 1 on the oldest frame — tmix's delay equals frames - 1)
      * every tap is attenuated with ``colorchannelmixer``
      * a pairwise ``blend=all_mode=lighten`` tree (per-pixel max) folds
        the taps into the result

    Args:
        src_label: Label of the animated source to hold (e.g. a
                   showfreqs output).
        fps: Source frame rate (used to convert seconds to frames).
        hold_seconds: Seconds each peak is held at full amplitude.
        decay_seconds: Seconds the held peak takes to decay to ~0.
        prefix: Unique prefix for intermediate labels (keeps the graph
                safe to splice into a larger filter_complex).
        max_taps: Maximum number of delay taps (hold+decay frame budget).

    Returns:
        (graph, out_label). If both hold and decay round to zero frames the
        chain is unnecessary and (None, src_label) is returned.

        When graph is not None it is a ';'-joined chain that consumes
        ``[src_label]`` exactly once and defines ``[out_label]`` exactly
        once; every other intermediate label is defined and consumed
        exactly once as well.
    """
    if fps <= 0:
        fps = 30

    hold_f = int(round(hold_seconds * fps))
    decay_f = int(round(decay_seconds * fps))
    if hold_f + decay_f < 1:
        return None, src_label

    # Clamp to the tap budget, scaling hold and decay proportionally
    if hold_f + decay_f > max_taps:
        scale = max_taps / (hold_f + decay_f)
        hold_f = int(round(hold_f * scale))
        decay_f = max_taps - hold_f

    n = hold_f + decay_f
    lam = PEAK_HOLD_FLOOR ** (1.0 / decay_f) if decay_f > 0 else 0.0

    def weight(i: int) -> float:
        if i < hold_f:
            return 1.0
        return lam ** (i - hold_f) if decay_f > 0 else 0.0

    chains: list[str] = []
    # Fan the source out to one stream per tap
    chains.append(f"[{src_label}] split={n}" + " ".join(f"[{prefix}s{i}]" for i in range(n)))
    for i in range(n):
        w = weight(i)
        if i == 0:
            # Identity tap (tmix with a single frame); keeps the pipeline uniform
            chains.append(f"[{prefix}s0] tmix=frames=1:weights='1'[{prefix}t0]")
        else:
            ws = " ".join(["1"] + ["0"] * i)
            chains.append(f"[{prefix}s{i}] tmix=frames={i + 1}:weights='{ws}'[{prefix}t{i}]")
        chains.append(
            f"[{prefix}t{i}] colorchannelmixer=rr={w:.6f}:gg={w:.6f}:bb={w:.6f}[{prefix}d{i}]"
        )
    # Pairwise max tree
    prev = f"{prefix}d0"
    for i in range(1, n):
        out = f"{prefix}m{i}" if i < n - 1 else f"{prefix}peak"
        chains.append(f"[{prev}][{prefix}d{i}] blend=all_mode=lighten[{out}]")
        prev = out
    return "; ".join(chains), f"{prefix}peak"


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

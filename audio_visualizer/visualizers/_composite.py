"""
Composite visualizer — composes several visualizer plugins into one frame.

This is an internal building block, not a standalone plugin: the CLI
instantiates it directly when ``--mode`` is given two or more values.
The module name starts with an underscore so the registry's built-in
scan skips it (see ``PluginRegistry._load_from_package``).

Each selected mode renders its own cell through its full pipeline
(filter graph + background composition), with every intermediate label
namespaced per mode so the sub-graphs can coexist in one filter_complex.
The cells are then combined into the final ``[out]`` pad according to
the layout (``--compose``: hstack, vstack, tile, overlay) and the cell
scaling policy (``--compose-scale``: fill stretches to the cell, fit
preserves aspect ratio and pads).
"""

import math
import re
from typing import Any

from audio_visualizer.logging_config import logger

from .base import PluginMetadata, VisualizerPlugin

# Matches intermediate filter labels such as [viz] or [transposed].
# Input stream references ([0:a], [1:v]) contain a colon and never match.
_LABEL_RE = re.compile(r"\[([A-Za-z0-9_]+)\]")

COMPOSE_LAYOUTS = ("hstack", "vstack", "tile", "overlay")
COMPOSE_SCALES = ("fill", "fit")


def _prefix_labels(graph: str, prefix: str) -> str:
    """Rename every intermediate label in *graph* to ``prefix + label``."""
    return _LABEL_RE.sub(lambda m: f"[{prefix}{m.group(1)}]", graph)


def _extract_plugin_options(
    plugin_cls: type[VisualizerPlugin], args: dict, canonical: dict[str, Any] | None = None
) -> dict:
    """Extract and validate a plugin's options from a full args dict.

    Mirrors the schema-driven extraction the base class performs in
    ``build_filter_complex()``: schema option names use hyphens (CLI
    form) while the args dict uses underscores. *canonical* (optional)
    holds first-mode-wins values for option names shared with earlier
    modes in a composite; they replace this mode's own resolution.
    """
    schema = plugin_cls.get_options()
    options: dict[str, Any] = {}
    for opt in schema.values():
        if canonical is not None and opt.name in canonical:
            # Shared with an earlier mode: the first mode already validated
            # the canonical value; this mode's schema may not accept it
            continue
        val = args.get(opt.name.replace("-", "_"))
        if val is not None:
            options[opt.name] = val
    options = plugin_cls.validate_options(options)
    if canonical:
        options.update(canonical)
    return options


def find_option_conflicts(
    sub_classes: list[type[VisualizerPlugin]],
) -> dict[str, tuple[type[VisualizerPlugin], list[type[VisualizerPlugin]]]]:
    """Find option names declared by more than one selected mode.

    Returns ``{option_name: (first_class, other_classes)}`` — the first
    mode in selection order is canonical for the shared option (sec.2.3).
    """
    first_owner: dict[str, int] = {}
    for i, cls in enumerate(sub_classes):
        for name in cls.get_options():
            first_owner.setdefault(name, i)

    conflicts: dict[str, tuple[type[VisualizerPlugin], list[type[VisualizerPlugin]]]] = {}
    for i, cls in enumerate(sub_classes):
        for name in cls.get_options():
            first_i = first_owner[name]
            if first_i == i:
                continue
            entry = conflicts.setdefault(name, (sub_classes[first_i], []))
            entry[1].append(cls)
    return conflicts


_warned_conflicts: set[tuple[str, ...]] = set()


def warn_option_conflicts(sub_classes: list[type[VisualizerPlugin]]) -> None:
    """Warn (once per process) about option names shared by selected modes."""
    conflicts = find_option_conflicts(sub_classes)
    if not conflicts:
        return
    key = tuple(c.get_metadata().name for c in sub_classes)
    if key in _warned_conflicts:
        return
    _warned_conflicts.add(key)
    for name, (first_cls, others) in conflicts.items():
        logger.warning(
            f"Option '--{name.replace('_', '-')}' is shared by modes "
            f"'{first_cls.get_metadata().name}' and "
            f"{', '.join(repr(c.get_metadata().name) for c in others)}; "
            f"the first mode's value wins"
        )


def _per_mode_overrides(args: dict, i: int) -> dict:
    """Per-mode option pairs for sub-mode i (v2.2.0 sec.2.1)."""
    specs = args.get("mode_specs") or []
    if i < len(specs):
        return specs[i][1]
    return {}


def _sub_args_for(args: dict, i: int, width: int, height: int) -> dict:
    """Sub-mode args: shared args + render size + that mode's pairs.

    The per-mode pairs win over the shared values (precedence: per-mode
    pair > global CLI flag > config file > default).
    """
    sub_args = dict(args)
    sub_args["width"] = width
    sub_args["height"] = height
    for key, val in _per_mode_overrides(args, i).items():
        sub_args[key.replace("-", "_")] = val
    return sub_args


class CompositeVisualizer(VisualizerPlugin):
    """Renders two or more visualizer plugins side by side (hstack)."""

    metadata = PluginMetadata(
        name="composite",
        display_name="Composite (multi-mode)",
        description="Composes several visualizer plugins into a single frame",
        icon="\U0001f39e\ufe0f",
        category="composite",
    )

    options: list = []  # No options of its own; sub-modes keep their schemas

    # ------------------------------------------------------------------
    #  Planning: geometry, per-sub input assignment
    # ------------------------------------------------------------------

    def _plan(
        self, args: dict
    ) -> tuple[
        list[tuple[int, int]], list[tuple[int, int]], list[list[str]], list[int | None], str, str
    ]:
        """Compute render/cell sizes, the ffmpeg input list, and bg assignment.

        Returns ``(render_sizes, cells, inputs, bg_indices, layout, scale)``:
        ``render_sizes[i]`` is the (width, height) sub-mode i is rendered
        at, ``cells[i]`` the (width, height) of its slot in the final
        frame, ``inputs`` the full ffmpeg input argument list (audio
        first), ``bg_indices[i]`` the global input index of sub i's
        background source (``None`` when the sub builds its own), and
        the resolved layout / scale policy.

        Layouts:
        - hstack: a row; width split across modes (last cell absorbs
          the rounding remainder), full height
        - vstack: a column; height split, full width
        - tile: row-major grid, cols = ceil(sqrt(N)); the missing
          corner cells (rows*cols - N) are black pads
        - overlay: every mode renders at full frame size, stacked in
          the order given (last mode on top)

        Scale policies:
        - fill: the sub is rendered directly at cell size (stretch)
        - fit: the sub is rendered at full frame size, then scaled into
          the cell preserving aspect ratio and padded to fill it
        (overlay is full-size either way, so the policy is a no-op)
        """
        sub_classes: list[type[VisualizerPlugin]] = args["mode_classes"]
        n = len(sub_classes)
        if n < 2:
            raise ValueError("CompositeVisualizer needs at least two modes")

        width = args["width"]
        height = args["height"]
        layout = args.get("compose", "hstack")
        scale = args.get("compose_scale", "fill")
        if layout not in COMPOSE_LAYOUTS:
            raise ValueError(
                f"Unknown compose layout '{layout}' (choose from {', '.join(COMPOSE_LAYOUTS)})"
            )
        if scale not in COMPOSE_SCALES:
            raise ValueError(
                f"Unknown compose scale '{scale}' (choose from {', '.join(COMPOSE_SCALES)})"
            )

        if layout == "overlay":
            cells = [(width, height)] * n
        elif layout == "hstack":
            base_w = width // n
            cells = [(base_w, height)] * (n - 1) + [(width - base_w * (n - 1), height)]
        elif layout == "vstack":
            base_h = height // n
            cells = [(width, base_h)] * (n - 1) + [(width, height - base_h * (n - 1))]
        else:  # tile
            cols = math.ceil(math.sqrt(n))
            rows = math.ceil(n / cols)
            base_w = width // cols
            base_h = height // rows
            col_w = [base_w] * cols
            col_w[-1] = width - base_w * (cols - 1)
            row_h = [base_h] * rows
            row_h[-1] = height - base_h * (rows - 1)
            cells = [(col_w[j], row_h[i // cols]) for i in range(rows * cols) for j in range(cols)]

        # Render size: fit and overlay render at full frame size (the
        # cell transform happens afterwards); fill renders in the cell
        if layout == "overlay" or scale == "fit":
            render_sizes = [(width, height)] * n
        else:
            render_sizes = cells[:n]

        inputs: list[list[str]] = [["-i", args["input"]]]
        bg_indices: list[int | None] = []
        for i, sub_cls in enumerate(sub_classes):
            sub = sub_cls()
            sub_args = _sub_args_for(args, i, render_sizes[i][0], render_sizes[i][1])
            try:
                sub_inputs = sub.get_inputs(sub_args)
            except FileNotFoundError:
                # e.g. albumart without --image: it needs dedicated
                # non-background inputs, which compositing can't allocate
                raise ValueError(
                    f"Mode '{sub_cls.get_metadata().name}' requires dedicated video inputs "
                    f"and cannot be part of a multi-mode composite yet"
                ) from None
            if len(sub_inputs) <= 1:
                # Sub builds its own background (nullsrc/color) in-graph
                bg_indices.append(None)
                continue
            second = sub_inputs[1]
            if len(second) >= 2 and second[0] == "-f" and second[1] == "lavfi":
                # Background color source — allocate a dedicated input so
                # each sub's compose hook can reference its own index
                sub_args["bg_index"] = len(inputs)
                inputs.append(second)
                bg_indices.append(len(inputs) - 1)
            else:
                raise ValueError(
                    f"Mode '{sub_cls.get_metadata().name}' requires dedicated video inputs "
                    f"and cannot be part of a multi-mode composite yet"
                )
        return render_sizes, cells, inputs, bg_indices, layout, scale

    def get_inputs(self, args: dict[str, Any]) -> list[list[str]]:
        """Audio input plus one background source per sub-mode that needs one."""
        _, _, inputs, _, _, _ = self._plan(args)
        return inputs

    # ------------------------------------------------------------------
    #  Filter graph construction
    # ------------------------------------------------------------------

    def _build_sub_pipeline(
        self,
        sub_cls: type[VisualizerPlugin],
        sub_args: dict,
        fps: int,
        canonical: dict[str, Any] | None = None,
    ) -> str:
        """Build one sub-mode's pipeline through ``[s{i}_out]`` (no cell transform).

        Returns filter chains producing ``[s{i}_out]`` at the render size
        carried in *sub_args*; *sub_args* also holds ``_comp_index`` (i).
        """
        i = sub_args["_comp_index"]
        sub = sub_cls()
        sub_options = _extract_plugin_options(sub_cls, sub_args, canonical)
        # Per-mode pairs beat the first-mode-wins canonical value (sec.2.1)
        for key, val in _per_mode_overrides(sub_args, i).items():
            if key in sub_cls.get_options():
                sub_options[key] = val
        raw = sub.build_filter(
            width=sub_args["width"],
            height=sub_args["height"],
            fps=fps,
            options=sub_options,
            colors=sub_args.get("colors"),
            bg_color=sub_args.get("bg_color"),
            args=sub_args,
        )

        # Normalize dict (multi-output) returns, like the base class does
        if isinstance(raw, dict):
            if not raw:
                raise ValueError(
                    f"Plugin '{sub_cls.get_metadata().name}': build_filter() returned an empty dict"
                )
            main_label = next(iter(raw))
            graph = "; ".join(seg.strip().rstrip(";") for seg in raw.values())
        else:
            main_label = sub.get_output_label(sub_options)
            graph = raw

        legacy = graph.strip().rstrip(";").strip().endswith("[out]")
        prefixed = _prefix_labels(graph, f"s{i}_")
        if not prefixed.endswith(";"):
            prefixed += ";"

        if legacy:
            # Legacy v1.x plugin: the graph already produced [out]
            # (now namespaced to [s{i}_out]); skip background composition
            composed = prefixed
        else:
            composed = sub.compose_final_filter(prefixed, f"s{i}_{main_label}", sub_args)
            # Namespace labels the compose hook introduced ([bg], [out],
            # border labels, ...) so they don't collide across sub-modes
            own_labels = set(_LABEL_RE.findall(prefixed))
            for label in set(_LABEL_RE.findall(composed)) - own_labels:
                composed = composed.replace(f"[{label}]", f"[s{i}_{label}]")

        return composed.strip().rstrip(";")

    def build_filter(
        self,
        width: int,
        height: int,
        fps: int,
        options: dict[str, Any],
        **kwargs: Any,
    ) -> str:
        """Build every sub-mode's cell and combine them into [out]."""
        args: dict = kwargs.get("args", {})
        render_sizes, cells, _, bg_indices, layout, scale = self._plan(args)
        sub_classes: list[type[VisualizerPlugin]] = args["mode_classes"]

        # sec.2.3 option scoping: options declared by more than one
        # selected mode resolve once — the first mode's value (schema,
        # default, and validation) is canonical for all later modes
        warn_option_conflicts(sub_classes)
        canonical: dict[str, Any] = {}
        for name, (first_cls, _) in find_option_conflicts(sub_classes).items():
            raw = args.get(name.replace("-", "_"))
            canonical[name] = first_cls.validate_options({name: raw})[name]

        segments: list[str] = []
        for i, sub_cls in enumerate(sub_classes):
            rw, rh = render_sizes[i]
            sub_args = _sub_args_for(args, i, rw, rh)
            sub_args["_comp_index"] = i
            if bg_indices[i] is not None:
                sub_args["bg_index"] = bg_indices[i]

            pipeline = self._build_sub_pipeline(sub_cls, sub_args, fps, canonical)

            # Cell transform: fit scales (aspect-preserving) + pads the
            # full-size render into the cell; fill renders in the cell
            cw, ch = cells[i]
            if layout != "overlay" and scale == "fit":
                pad_color = args.get("bg_color") or "black"
                segments.append(
                    f"{pipeline}; [s{i}_out]scale={cw}:{ch}:flags=bicubic:"
                    f"force_original_aspect_ratio=decrease,"
                    f"pad={cw}:{ch}:(ow-iw)/2:(oh-ih)/2:color={pad_color},"
                    f"format=yuv420p[s{i}_fmt]"
                )
            else:
                segments.append(f"{pipeline}; [s{i}_out]format=yuv420p[s{i}_fmt]")

        graph = "; ".join(seg.strip() for seg in segments)
        return f"{graph}; {self._compose_step(args, layout, cells, fps)}"

    def _compose_step(self, args: dict, layout: str, cells: list[tuple[int, int]], fps: int) -> str:
        """The final combining chain(s) from the [sN_fmt] pads to [out]."""
        n = len(args["mode_classes"])
        if layout == "overlay":
            step = "[s0_fmt][s1_fmt]overlay=shortest=1:format=auto[ov1]"
            for i in range(2, n):
                step += f"; [ov{i - 1}][s{i}_fmt]overlay=shortest=1:format=auto[ov{i}]"
            return f"{step}; [ov{n - 1}]format=yuv420p[out]"

        if layout in ("hstack", "vstack"):
            pads = "".join(f"[s{i}_fmt]" for i in range(n))
            return f"{pads}{layout}=inputs={n}[out]"

        # tile: hstack each row (missing corner cells become black pads),
        # then vstack the rows
        cols = math.ceil(math.sqrt(n))
        rows = math.ceil(n / cols)
        pad_segments = []
        for k in range(n, rows * cols):
            pw, ph = cells[k]
            pad_segments.append(f"color=c=black:s={pw}x{ph}:r={fps},format=yuv420p[pad{k}]")
        row_chains = []
        for r in range(rows):
            pads = ""
            for j in range(cols):
                idx = r * cols + j
                pads += f"[s{idx}_fmt]" if idx < n else f"[pad{idx}]"
            row_chains.append(f"{pads}hstack=inputs={cols}[row{r}]")
        rows_chain = "".join(f"[row{r}]" for r in range(rows))
        return "; ".join(pad_segments + row_chains) + f"; {rows_chain}vstack=inputs={rows}[out]"

"""
Composite visualizer — composes several visualizer plugins into one frame.

This is an internal building block, not a standalone plugin: the CLI
instantiates it directly when ``--mode`` is given two or more values.
The module name starts with an underscore so the registry's built-in
scan skips it (see ``PluginRegistry._load_from_package``).

Each selected mode renders its own cell through its full pipeline
(filter graph + background composition), with every intermediate label
namespaced per mode so the sub-graphs can coexist in one filter_complex.
The cells are then combined with ``hstack`` into the final ``[out]`` pad.
"""

import re
from typing import Any

from .base import PluginMetadata, VisualizerPlugin

# Matches intermediate filter labels such as [viz] or [transposed].
# Input stream references ([0:a], [1:v]) contain a colon and never match.
_LABEL_RE = re.compile(r"\[([A-Za-z0-9_]+)\]")


def _prefix_labels(graph: str, prefix: str) -> str:
    """Rename every intermediate label in *graph* to ``prefix + label``."""
    return _LABEL_RE.sub(lambda m: f"[{prefix}{m.group(1)}]", graph)


def _extract_plugin_options(plugin_cls: type[VisualizerPlugin], args: dict) -> dict:
    """Extract and validate a plugin's options from a full args dict.

    Mirrors the schema-driven extraction the base class performs in
    ``build_filter_complex()``: schema option names use hyphens (CLI
    form) while the args dict uses underscores.
    """
    schema = plugin_cls.get_options()
    options: dict[str, Any] = {}
    for opt in schema.values():
        val = args.get(opt.name.replace("-", "_"))
        if val is not None:
            options[opt.name] = val
    return plugin_cls.validate_options(options)


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
    #  Planning: cell geometry and per-sub input assignment
    # ------------------------------------------------------------------

    def _plan(self, args: dict) -> tuple[list[tuple[int, int]], list[list[str]], list[int | None]]:
        """Compute cell sizes, the ffmpeg input list, and bg assignment.

        Returns ``(cells, inputs, bg_indices)`` where ``cells[i]`` is the
        ``(width, height)`` of sub-mode i's cell, ``inputs`` is the full
        ffmpeg input argument list (audio first), and ``bg_indices[i]``
        is the global input index of sub i's background source (``None``
        when the sub builds its own background inside the filter graph).

        Layout (v2.1): hstack — the frame width is split across the
        modes (the last cell absorbs the rounding remainder so the cells
        tile the frame exactly) and each cell keeps the full height.
        """
        sub_classes: list[type[VisualizerPlugin]] = args["mode_classes"]
        n = len(sub_classes)
        if n < 2:
            raise ValueError("CompositeVisualizer needs at least two modes")

        width = args["width"]
        height = args["height"]
        base_w = width // n
        cells = [(base_w, height)] * (n - 1) + [(width - base_w * (n - 1), height)]

        inputs: list[list[str]] = [["-i", args["input"]]]
        bg_indices: list[int | None] = []
        for i, sub_cls in enumerate(sub_classes):
            sub = sub_cls()
            sub_args = dict(args)
            sub_args["width"] = cells[i][0]
            sub_args["height"] = cells[i][1]
            try:
                sub_inputs = sub.get_inputs(sub_args)
            except FileNotFoundError:
                # e.g. albumart without --image: it needs dedicated
                # non-background inputs, which compositing can't allocate
                raise ValueError(
                    f"Mode '{sub_cls.metadata.name}' requires dedicated video inputs "
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
                    f"Mode '{sub_cls.metadata.name}' requires dedicated video inputs "
                    f"and cannot be part of a multi-mode composite yet"
                )
        return cells, inputs, bg_indices

    def get_inputs(self, args: dict[str, Any]) -> list[list[str]]:
        """Audio input plus one background source per sub-mode that needs one."""
        _, inputs, _ = self._plan(args)
        return inputs

    # ------------------------------------------------------------------
    #  Filter graph construction
    # ------------------------------------------------------------------

    def build_filter(
        self,
        width: int,
        height: int,
        fps: int,
        options: dict[str, Any],
        **kwargs: Any,
    ) -> str:
        """Build every sub-mode's cell and hstack them into [out]."""
        args: dict = kwargs.get("args", {})
        cells, _, bg_indices = self._plan(args)
        sub_classes: list[type[VisualizerPlugin]] = args["mode_classes"]
        n = len(sub_classes)

        segments: list[str] = []
        for i, sub_cls in enumerate(sub_classes):
            sub = sub_cls()
            cw, ch = cells[i]
            sub_args = dict(args)
            sub_args["width"] = cw
            sub_args["height"] = ch
            if bg_indices[i] is not None:
                sub_args["bg_index"] = bg_indices[i]

            sub_options = _extract_plugin_options(sub_cls, args)
            raw = sub.build_filter(
                width=cw,
                height=ch,
                fps=fps,
                options=sub_options,
                colors=args.get("colors"),
                bg_color=args.get("bg_color"),
                args=sub_args,
            )

            # Normalize dict (multi-output) returns, like the base class does
            if isinstance(raw, dict):
                if not raw:
                    raise ValueError(
                        f"Plugin '{sub_cls.metadata.name}': build_filter() returned an empty dict"
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

            pipeline = composed.strip().rstrip(";")
            segments.append(f"{pipeline}; [s{i}_out]format=yuv420p[s{i}_fmt]")

        graph = "; ".join(seg.strip() for seg in segments)
        pads = "".join(f"[s{i}_fmt]" for i in range(n))
        return f"{graph}; {pads}hstack=inputs={n}[out]"

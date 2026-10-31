# Plugin Development Guide

A visualizer plugin is a Python class that subclasses
`audio_visualizer.visualizers.base.VisualizerPlugin`. The core takes care of
everything around it:

- **CLI flags** are generated from your `options` schema — you never touch
  argparse
- **Validation**: values are coerced to the declared type, checked against
  `choices`/`range`, and filled in from `default` before your code runs
- **I/O**: audio input, the background-color video input, codec settings,
  and the final `[out]` composition (overlay + border)
- **Discovery**: built-ins, installed packages (entry points), user-installed
  plugins, and explicit `--plugin-path` files — all validated identically

You provide exactly two things: a `metadata` description and a
`build_filter()` method that emits an ffmpeg filter graph.

---

## 1. Anatomy of a plugin

### 1.1 `metadata` — a `PluginMetadata` instance

| Field | Meaning |
| --- | --- |
| `name` | Unique id; the value users pass to `--mode`. Lowercase, no spaces. |
| `display_name` | Human-readable name shown in listings. |
| `description` | One line, shown in `--list-plugins`. |
| `author` | Optional author string. |
| `version` | Plugin version, shown by `--list-plugins --verbose`. Bump it when the filter graph or options change. |
| `icon` | Optional emoji for listings. |
| `category` | Grouping: `spectrum`, `waveform`, `meter`, `composite`, `other`. |
| `requires_ffmpeg_version` | Minimum ffmpeg (e.g. `"7.0"`) if you use newer filters. |
| `input_types` | Required inputs, e.g. `["audio"]`. |

### 1.2 `options` — a list of `PluginOption` schemas

```python
PluginOption(
    name="peakbars-hold",  # CLI flag: --peakbars-hold (_ -> -)
    type=float,  # str, int, float, or bool
    default=0.1,  # used when the flag is absent
    help="Seconds each peak is held",  # shown in --help
    choices=[...],  # optional allow-list
    range=(0.0, 2.0),  # optional numeric bounds (None = unbounded)
    group="peakbars",  # optional --help section
)
```

Inside `build_filter()` you read validated values from the `options` dict:

```python
hold = float(options.get("peakbars-hold", 0.1))
```

The CLI flag, `--help` entry, config-file key, and validation all come from
this one declaration.

### 1.3 `build_filter()` — the required method

```python
def build_filter(
    self, width: int, height: int, fps: int, options: dict, **kwargs
) -> str | dict[str, str]: ...
```

**Label discipline** — the core composes the final `[out]` stream from your
main output (default label `[viz]`, change via `get_output_label()`), so:

- Produce your main output exactly once, labeled `[viz]` (or your
  overridden label).
- **Do not produce `[out]`** — the base class consumes your label to overlay
  it on the background input and to apply post-processing (border).
- Every intermediate label is defined exactly once and consumed exactly once.
- Reference input streams with the `audio_index`/`video_index` kwargs
  (typically `[0:a]` and `[1:v]`), never hardcoded.

Example (single output):

```python
return f"[{audio_index}:a] showfreqs=size={width}x{height}:rate={fps}:mode=1[viz]"
```

**Multi-output**: return a `dict[str, str]` mapping output names to filter
segments. Segments are joined with `; ` and the first key names the main
output label:

```python
return {
    "viz": "[0:a] showfreqs=size=...[viz]",
    "scope": "[0:a] showwaves=size=...[scope]",
}
```

### 1.4 Hooks (optional)

Override only what you need:

- `get_inputs(args)` — default is audio + a background-color video input.
  Override for image inputs (see `albumart`) or to drop the background
  (see `vectorscope`).
- `get_codec_settings(fmt, args, accel)` — custom encoding.
- `post_process_filter(filter_str, args)` — modify the completed graph
  (the default adds the border).
- `get_output_label(options)` — main output label other than `viz`.

Most visualizers get away with schema + `build_filter` alone — the built-in
`peakbars` and `oscilloscope` plugins (v2.1.0) override nothing else, which
is the style this repo asks new plugins to follow.

---

## 2. A worked example: `peakbars`

Reference implementation: `audio_visualizer/visualizers/peakbars.py`.
Spectrum bars whose peaks hold, then decay — `showfreqs` alone can't do
that, so the plugin chains a delay-tap peak-hold network on top:

```python
from .base import PluginMetadata, PluginOption, VisualizerPlugin


class PeakbarsPlugin(VisualizerPlugin):
    metadata = PluginMetadata(
        name="peakbars",
        display_name="Peak-Hold Bars",
        description="Vertical spectrum bars with persistent peaks that hold, then decay",
        author="Audio Visualizer",
        version="1.0.0",
        icon="📶",
        category="spectrum",
    )

    options = [
        PluginOption(
            "peakbars-hold",
            float,
            0.1,
            "Seconds each peak is held at full height (0.0-2.0)",
            range=(0.0, 2.0),
        ),
        PluginOption(
            "peakbars-decay",
            float,
            0.6,
            "Seconds the held peak takes to decay away (0.0-2.0)",
            range=(0.0, 2.0),
        ),
    ]

    def build_filter(self, width, height, fps, options, audio_index=0, **kwargs) -> str:
        hold = float(options.get("peakbars-hold", 0.1))
        decay = float(options.get("peakbars-decay", 0.6))
        bars = (
            f"[{audio_index}:a] showfreqs=size={width}x{height}"
            f":rate={fps}:mode=1:colors={self._colors(kwargs)}"
        )
        graph, out_label = build_peak_hold_chain("pb_src", fps, hold, decay, "pb")
        if graph is None:  # no hold requested
            return f"{bars},format=yuv420p[viz]"
        return f"{bars}[pb_src]; {graph}; [{out_label}]format=yuv420p[viz]"
```

Notes:

- The `--peakbars-hold` / `--peakbars-decay` flags exist only because of the
  `options` list — there is no argparse code anywhere.
- The chain builder in `utils.py` (`build_peak_hold_chain`) returns
  `(None, "pb_src")` when nothing is requested, so the plugin degrades to a
  plain graph with the same label discipline.
- The final `,format=yuv420p` keeps the encoder input in a supported
  pixel format.

---

## 3. Developing locally: `--plugin-path`

No installation needed. Point the CLI at a file or a directory of `.py`
files (repeatable), or set the `AUDIO_VISUALIZER_PLUGIN_PATH` environment
variable (paths separated by `os.pathsep`):

```bash
audio-visualizer song.mp3 --plugin-path ~/dev/mypack/ --mode peakbars
AUDIO_VISUALIZER_PLUGIN_PATH=~/dev/mypack audio-visualizer song.mp3 --mode peakbars
```

`--list-plugins --verbose` shows each plugin's origin, version, minimum
ffmpeg version, and options. Discovery precedence (later shadows earlier,
with a warning):

```
builtin  <  entrypoint  <  installed  <  path
```

So a local file named after a built-in shadows the built-in during
development, and the shadowing is announced rather than silent.

---

## 4. Packaging a plugin as an entry-point distribution

Ship plugins in your own package. The registry scans the
`audio-visualizer.plugins` entry-point group at startup; each entry maps a
plugin id to an importable `module:Class`:

```toml
# pyproject.toml
[project]
name = "my-visualizer-pack"
version = "0.1.0"
description = "Extra visualizers for audio-visualizer"
dependencies = ["musicvisualizer>=2.1"]

[project.entry-points."audio-visualizer.plugins"]
my_viz = "my_viz:MyVizPlugin"
scope_grid = "scope_grid:ScopeGridPlugin"   # one package, many plugins
```

```
mypack/
├── pyproject.toml
└── my_viz.py          # defines MyVizPlugin(VisualizerPlugin)
```

After `pip install my-visualizer-pack` the plugins appear in
`--list-plugins` with origin `entrypoint`, go through exactly the same
schema validation as built-ins, and can be selected with `--mode my_viz`.

Package tips:

- Import the base classes as
  `from audio_visualizer.visualizers.base import PluginMetadata,
  PluginOption, VisualizerPlugin` — that path is the stable public API.
- Declare `musicvisualizer>=2.1` (the PyPI distribution name) so users get
  the v2 plugin API.
- Keep `metadata.name` globally unique — if you collide with a built-in you
  shadow it and the user sees a warning, not an error.

---

## 5. Testing a plugin

The core ships public test helpers in `audio_visualizer.testing` so you
don't need to copy-paste the repo's test regexes:

```python
from audio_visualizer.testing import (
    assert_label_discipline, make_silence_wav, make_tone_wav,
)

def test_my_labels():
    graph = MyPlugin().build_filter(640, 360, 30, {}, audio_index=0)
    assert_label_discipline(graph, "myplugin")  # main='viz' by default
```

`make_tone_wav()` / `make_silence_wav()` generate deterministic 1 s WAV
fixtures with ffmpeg (skip if ffmpeg is missing), and
`assert_label_discipline(graph, source, main="viz")` checks the named-pad
rules every plugin graph must follow for compositing to work.

Two layers, both quick:

**1. Unit — schema and filter structure.** Assert the schema is sane and
that `build_filter()` honors the label discipline (each intermediate label
defined once, consumed once; source consumed once; main output defined
once):

```python
import re
from collections import Counter


def test_peakbars_labels():
    plugin = PeakbarsPlugin()
    graph = plugin.build_filter(
        1280, 720, 30, {"peakbars-hold": 0.1, "peakbars-decay": 0.2}, audio_index=0
    )
    labels = Counter(re.findall(r"\[([A-Za-z0-9_-]+)\]", graph))
    assert labels["0:a"] == 1
    assert labels["viz"] == 1
    assert graph.count("[out]") == 0
    for label, n in labels.items():
        if label not in ("0:a", "viz"):
            assert n == 2, f"[{label}] must appear exactly twice"
```

**2. E2E — actually encode.** `--dry-run` prints the resolved ffmpeg
command (add `--json` for machine-readable output) without encoding, then
encode a short clip for real:

```bash
audio-visualizer tests/fixtures/short.mp3 \
    --plugin-path my_viz.py --mode my_viz \
    --width 320 --height 180 --fps 10 --dry-run      # inspect the graph
audio-visualizer tests/fixtures/short.mp3 \
    --plugin-path my_viz.py --mode my_viz \
    --width 320 --height 180 --fps 10 -o /tmp/my_viz_test.mp4
```

This repo's `tests/test_visualizers.py` (plugin tests) and
`tests/test_e2e.py` (encode tests) are the house style to copy.

---

## 6. Checklist before shipping

- [ ] `metadata.name` is unique, lowercase; `version` bumped from before
- [ ] `options` cover every knob; `range`/`choices` make bad input fail
      loudly at the CLI
- [ ] `build_filter()` respects label discipline (see §1.3); no `[out]`
- [ ] `requires_ffmpeg_version` set if the graph uses new filters
- [ ] `requires_core_version` set if the plugin needs core features newer
      than the oldest version you still support
- [ ] `--list-plugins --verbose` shows sensible version + ffmpeg floor
- [ ] Unit tests for schema + labels, one e2e encode in CI

## 7. Security model

A plugin is arbitrary Python code: `build_filter()` runs with your
interpreter's full privileges, can read and write files, make network
calls, or import anything. The core does **not** sandbox plugins.

- Plugins from the `path` origin (`--plugin-path`,
  `AUDIO_VISUALIZER_PLUGIN_PATH`) and the `entrypoint` origin
  (installed distributions) print a one-line warning on first load:
  they are untrusted until you have read the code.
- The trust decision is the user's: review a third-party plugin's
  source before installing or pointing `--plugin-path` at it, and keep
  `path`/`entrypoint` plugins out of CI that processes untrusted input.
- Built-in plugins (`builtin` origin) are part of this repository and
  are not warned about; the `installed` origin (the user plugin
  directory) is your own machine's configuration.

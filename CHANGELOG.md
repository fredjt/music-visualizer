# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- **Per-mode option syntax (v2.2.0 sec.2.1)** — `--mode "spectrum:bg_color=navy" --mode "vectorscope:zoom=1.5"`: `mode:key=value` pairs override that mode's option in a composite (repeatable, comma-separated; values validated against the mode's schema; full option names and bare prefix-stripped names both work, plus per-mode `bg_color`/`colors` and `opacity`). Precedence is per-mode pair > global CLI flag > config file > default, and a global flag still applies to unpaired modes. `--mode` now accepts repeated flags (append) as well as the `--mode a b` and `a+b` forms; `--dry-run --json` surfaces the resolved pairs under `per_mode_options`

### Changed
- **PR CI feedback via smoke subset (v2.2.0 sec.4.1)** — the Test workflow now splits on event: pull requests run the unit tests plus a new `smoke` subset (one short encode per built-in visualizer, ~1 s clips at 10 fps on a 640x360 frame, via `pytest -m "smoke or not e2e"`), while pushes to master run the full suite. All encode-based tests are marked `@pytest.mark.e2e`; the smoke subset is marked `@pytest.mark.smoke` (tests/test_e2e.py::TestSmoke, driven by a session fixture that renders 1 s/2 s sine tones with ffmpeg). PR legs no longer run coverage, keeping PR feedback well under five minutes
- **Smoke: tap-chain encode caps and per-format coverage (v2.2.0 sec.4.2)** — the smoke subset encodes `peakbars` and `oscilloscope` on 2 s clips (the 21–60 tap delay chains are the slowest paths; 2 s at 10 fps keeps the default hold+decay window running while the graph stays small), and it now also encodes once per mkv and webm output format (mp4 is already covered by the per-visualizer encodes; webm is skipped where the ffmpeg build lacks libvpx-vp9). The full-length peak-hold/oscilloscope encodes run only in the push-only full suite
- **One coverage leg in CI (v2.2.0 sec.4.3)** — branch coverage and the Codecov upload now run only on the Python 3.12 matrix leg (Linux); the other legs (3.10, 3.11, 3.13, 3.14) run plain `pytest --no-cov`, so the 75% branch-coverage gate is enforced exactly once per push instead of five times
- **macOS joins the PR test matrix (v2.2.0 sec.4.4)** — a `macos-latest` leg (Python 3.12, ffmpeg via Homebrew) runs the smoke subset on pull requests, catching subprocess/path handling that only misbehaves off Linux. Windows is explicitly deferred to a later release and the README now documents the tested platforms ("Linux and macOS")
- **Post-release `[Unreleased]` stub (v2.2.0 sec.5.1)** — the Release workflow gains a `post-release` job: after the GitHub release is created, it pushes a `chore: stub [Unreleased] for next cycle` commit restoring the empty `## [Unreleased]` section the cut consumed as release notes, and opens a PR for it (needs `pull-requests: write`). The `[Unreleased]` notes-extraction fallback is now guaranteed for every future tag, so cutting a release no longer depends on remembering the stub
- **Tag health checks (v2.2.0 sec.5.2)** — the Release workflow's `verify` job now also asserts (a) the tag's commit is reachable from master (catches tags cut from side branches) and (b) the `[project].name` in the built wheel and sdist metadata is the expected PyPI project `musicvisualizer`, before the `pypi` job publishes anything
- **PyPI project page (v2.2.0 sec.5.4)** — `[project.urls]` (Repository, Issues, Changelog) is set in pyproject.toml, so the `musicvisualizer` project page links out to the GitHub repo, issue tracker, and changelog; the generated README flag/theme tables are verified to render on the page (screenshot check in the release notes PR)
- **Project minimum ffmpeg version (v2.2.0 sec.8.4)** — the project now declares a minimum ffmpeg (6.0, documented in the README Requirements). At startup the detected ffmpeg version is parsed and compared: below the minimum, a clear error explains what is required and how to upgrade. In addition, the per-plugin `requires_ffmpeg_version` is now enforced for the selected modes (single, batch, and dry runs): when a selected visualizer needs a newer build, the error names the exact visualizer(s) and the required version
- **Batch report v2 + `--report` (v2.2.0 sec.1.3)** — the batch report gains `schema_version: 2`, a `run_id` (short uuid, stable within a run), `batch_dir`, the detected `ffmpeg_version`, and a per-file `attempts` count (for diagnosing flakes; `--resume`/`--retry-failed` accumulate it across runs). The new `--report PATH` flag (repeatable) also writes the report to one or more files in addition to the unchanged default `batch_report.json` in the batch output directory. Old v1 reports keep working as input via the same `files` fallback
- **`--retry-failed` batch recovery (v2.2.0 sec.1.1)** — `--retry-failed PATH` takes a batch report (v1 or v2) and re-runs only the entries with status `failed` (with this invocation's settings), preserving all other entries in the new report. It exits 0 when the retry pass completes, even if some entries are still failing — the new report lists them as `failed` with their accumulated `attempts`. A missing report file is an error naming the path, and `--resume`/`--retry-failed` are mutually exclusive
- **`--resume` batch recovery (v2.2.0 sec.1.2)** — `--resume PATH` takes a batch report (v1 or v2) and re-runs only the entries that are not effectively successful ("successful" = old status `success` **and** the output file still exists). The resume run writes a fresh report that merges the preserved successful entries (status and output kept, old ordering preserved) with the re-run entries, whose `attempts` accumulate across runs. The old report is never modified: a copy is kept next to it as `batch_report.before-resume.json`. A resume where everything is already successful re-runs nothing and exits 0
- **`--compose-grid ROWSxCOLS` (v2.2.0 sec.2.2)** — explicit tile-grid placement for `--compose tile` (e.g. `--compose-grid 2x3`): cells fill row-major in the given grid; a grid larger than the mode count pads the remainder with the background color, a grid too small (or malformed, or used with a non-tile layout) fails with a clear error. The default row-major `ceil(sqrt(n))` grid is unchanged

- **`audio-visualizer new-plugin NAME [--dir PATH]` scaffolding (v2.2.0 sec.6.1)** — writes a ready-to-edit plugin package: pyproject.toml with the `audio-visualizer.plugins` entry point (depending on `musicvisualizer>=2.2`), a template plugin module that doubles as the canonical minimal example, and a label-discipline test using the new public helpers; prints the `pip install -e .` follow-up. The generated plugin is loadable out of the box (verified in the test suite)

- **`audio_visualizer.testing` public helpers (v2.2.0 sec.6.3)** — a small public module for third-party plugin authors: `make_tone_wav()` / `make_silence_wav()` generate deterministic 1 s WAV fixtures with ffmpeg, and `assert_label_discipline(graph, source, main="viz")` checks the named-pad rules every plugin graph must follow for compositing, so plugin test suites stop copy-pasting the repo's test regexes. The plugin guide links to it

- **Plugin trust warning (v2.2.0 sec.6.4)** — loading a plugin from the `path` (`--plugin-path` / `AUDIO_VISUALIZER_PLUGIN_PATH`) or `entrypoint` origin prints a one-line warning on first use: plugins are arbitrary Python code and the trust decision is the user's. The plugin guide (docs/PLUGIN_DEVELOPMENT.md) gains a "Security model" section stating this

- **`PluginMetadata.requires_core_version` (v2.2.0 sec.6.2)** — third-party plugins can declare the minimum audio-visualizer core they need (e.g. `requires_core_version="2.2"`); the registry warns and skips plugins requiring a newer core (mirroring the existing ffmpeg version check), and `--list-plugins --verbose` shows the requirement

- **Overlay layer opacity (v2.2.0 sec.2.3)** — `--compose overlay` now honors a per-mode `opacity` pair (`--mode "vectorscope:opacity=0.5"`): the overlaid layer is blended at the given alpha over the layers below it; the last mode is always opaque

- **User-defined themes (v2.2.0 sec.3.1)** — drop a JSON file in `~/.config/audio-visualizer/themes/<name>.json` (`{"palette": ["red", "orange", ...]}`, 1–12 validated colors) and the theme name works everywhere a built-in one does: `--theme`, the `AUDIO_VISUALIZER_THEME` env var, and `theme:` in the config file. `--list-themes` shows built-in and user themes in separate sections (swatches on a tty, as before). Invalid theme files are skipped with a warning instead of crashing; a user theme with the same name as a built-in overrides it
### Fixed
- **`--mode showfreqs` with a theme or `--colors` (v2.2.0 sec.3.2 follow-up)** — showfreqs' `colors` filter option is pipe-separated but theme/`--colors` values are comma-separated, so the generated filtergraph was rejected by ffmpeg and the encode failed (the dry-run output looked fine). The palette is now converted with the same `ColorParser.as_pipe_colors()` the other palette visualizers use. New real-encode e2e regression test

- **12-color palettes (v2.2.0 sec.3.2)** — built-in and custom themes each carry up to 12 colors (validated on load; longer palettes are interpolated by the color-list filters such as `showfreqs`/`showwaves`, no new filter code). `--list-themes` now shows the palette length next to every theme so users can compare, and the README documents the custom-theme file format and the limit
- **Theme preview export (v2.2.0 sec.3.3)** — `--list-themes --png DIR` renders one small preview PNG per theme (built-in and user) into DIR: a 1 s tone run through `showfreqs` with the theme palette, one channel per palette color at a distinct frequency so every color shows as its own colored peak. Feeds the README/PyPI docs and gives a visual before committing to a theme

- **Version bump helper (v2.2.0 sec.5.3)** — `python scripts/next_version.py {patch,minor,major}` rewrites only the `version = "X.Y.Z"` line in `pyproject.toml` and prints the exact `git add` / `git commit` / `git tag` / `git push` sequence for the cut; the script itself never touches git

## [2.1.0] - 2026-10-31

### Changed
- **PyPI distribution name is `musicvisualizer`** — PyPI rejected `audio-visualizer` (too similar to the existing `audiovisualizer` project), so the package publishes as `musicvisualizer` (`pip install musicvisualizer`). The `audio-visualizer` CLI command, the `audio-visualizer.plugins` entry-point group, and the importable `audio_visualizer` module are all unchanged

### Added
- **Tag/version consistency check in CI** — the Build workflow now also runs on `v*` tag pushes, where a dedicated job fails the build if the tag does not match `[project].version` in pyproject.toml — the stale-checkout failure mode that once produced `1.0.0`-named artifacts is caught before any build runs (the regular build job skips tag pushes; the Release workflow owns tag builds)
- **PyPI publishing via OIDC trusted publishing** — the release workflow's `pypi` job (gated by the `pypi` environment) runs `twine check` on the release artifacts and publishes them to PyPI with no long-lived token: it presents the OIDC identity `repo:fredjt/music-visualizer:environment:pypi`, which must be registered as a trusted publisher for the `audio-visualizer` project on pypi.org
- **Tag-triggered release workflow** — pushing a `v*` tag now runs a `verify -> build -> release` pipeline: the tag must match `[project].version`, `python -m build` produces the wheel + sdist, and the GitHub release is created with the matching CHANGELOG section (falling back to `[Unreleased]`) as the notes and the `dist/` artifacts attached — releases can no longer be cut manually with missing assets
- **Plugin development guide** — `docs/PLUGIN_DEVELOPMENT.md` covers plugin anatomy (metadata, option schemas, the `build_filter()` label discipline, optional hooks), a worked example built on the `peakbars` plugin, packaging a plugin as an entry-point distribution (`[project.entry-points."audio-visualizer.plugins"]`), and testing (schema/label unit tests + e2e encodes); linked from the README and printed in the `--list-plugins --verbose` footer
- **Generated README flag reference** — the flag tables and theme table in the README are now generated from the live CLI parser by `scripts/generate_flag_reference.py` (replacing the stale hand-maintained option list); the script's `--check` mode runs in CI and fails when the README drifts from the parser, and the `--help` epilog now lists all 13 built-in visualizers
- **Theme and batch mode docs** — the README documents `--theme` (available themes, precedence: explicit `--colors` > CLI `--theme` > `AUDIO_VISUALIZER_THEME` env var > config file) and batch mode in full (`--parallel`/`-j`, `--recursive`, `--include`/`--exclude`, `--output-template`, `batch_report.json`, and the failure exit code)
- **`--version` flag** — prints the package version and the detected ffmpeg version (works without an input file); previously argparse rejected the flag as unrecognized
- **Resolution presets** — `--resolution` now accepts `360p`, `480p`, `720p`, `1080p`, `1440p`, and `4k` (16:9) in addition to `WxH`; `--aspect-ratio` still overrides, and presets are accepted in config files
- **`--list-themes` flag** — lists the available color themes with ANSI swatches on a tty and a plain palette list when piped
- **`--log-file PATH`** — tees log output to a file at debug level while the console keeps its own verbosity (`--quiet --log-file` keeps the console silent but the file complete); unopenable paths fail with a clear error
- **`--dry-run --json`** — machine-readable dry run: the resolved options plus the exact ffmpeg command for a single input, or one entry per file in batch mode
- **CLI/UX contract tests** — cover version info, preset expansion, theme listing (tty/non-tty), log-file capture, and JSON dry-run payloads

- **Third-party plugin discovery** — plugins now load from installed distributions that register the `audio-visualizer.plugins` entry-point group, from `--plugin-path PATH` (repeatable; a `.py` file or directory), and from the `AUDIO_VISUALIZER_PLUGIN_PATH` environment variable (path-separated list); external plugin schemas contribute auto-generated CLI flags like built-ins
- **Plugin origin tracking** — the registry records how each plugin was discovered (`builtin`, `entrypoint`, `installed`, `path`); `--list-plugins` marks non-built-in plugins with their source and `--list-plugins --verbose` shows a `Source:` line with version and ffmpeg requirement
- **Explicit plugin shadowing** — an external plugin named after a built-in replaces it with a warning (precedence: path > installed > entrypoint > builtin) instead of a silent overwrite

- **End-to-end `--theme` tests** — verify that themes passed via CLI, env var, and config file all resolve to the correct palette in the ffmpeg command, with precedence CLI > env > config and explicit `--colors` always winning
- **End-to-end WebM encode test** — the previously skipped WebM test now performs a real encode (VP9 video + Opus audio) whenever the ffmpeg build provides `libvpx-vp9`
- **Source tags copied to the output video** — the audio file's title/artist/album/comment tags now reach the video container (`-map_metadata 0`), so the exported video keeps the song's identity
- **Metadata overrides** — `--title`, `--artist`, `--album`, and `--comment` override the copied tags, and `--no-metadata` strips all tags for a clean output
- **Metadata e2e tests** — encode a tagged MP3 and verify via ffprobe that the output container tags are copied, overridden, or stripped as the flags dictate
- **Batch output naming template** — `--output-template TEMPLATE` (batch mode) names outputs with `{name}`, `{ext}`, `{mode}`, and `{width}` placeholders; the previous `{stem}_visualizer.{format}` pattern is the default template, and an unrenderable template fails fast before any file is processed (dry run included)
- **Batch discovery options** — `--recursive` scans subdirectories; `--include PATTERN` / `--exclude PATTERN` (repeatable globs matched against the path relative to the batch dir) filter the file list, with the built-in audio extension list as the default include; batch and dry-run share one `discover_batch_files()` implementation
- **Parallel batch encode** — `--parallel N` / `-j N` (default 1 = sequential, `auto` = CPU count) runs N concurrent ffmpeg encodes with an accurate global progress bar; failures are still captured per file in the report and set the exit code
- **Multi-visualizer compositing** — `--mode` accepts several modes (`audio-visualizer input --mode spectrum waveform`): each mode renders its own cell and the cells are combined into the requested frame. Every mode keeps its own options and background, the frame border applies to the final composite, and the `{mode}` output template / batch report label them as `spectrum+waveform`; batch mode, dry run, and `--dry-run --json` all support composites
- **Composite layout and cell scaling** — `--compose {hstack,vstack,tile,overlay}` (default `hstack`) controls how the cells are arranged: side by side, stacked, in a row-major grid (missing corner cells become black pads), or overlaid full-frame in the order given (last mode on top); `--compose-scale {fill,fit}` (default `fill`) either stretches each mode to its cell or preserves its aspect ratio and pads the letterbox with the background color
- **Composite option scoping** — options shared by the selected modes (background, colors, border, codec settings) resolve once for all of them; if two modes declare an option with the same name, the first mode's value (and default) is canonical for every later mode and a warning names the conflicting options; precedence is documented in the README
- **Combo presets** — `--mode spectrum+waveform` is sugar for `--mode spectrum waveform`; `--list-plugins` shows the built-in presets (`spectrum+waveform`, `spectrum+vectorscope`) under `[combos]`, and any combination of loaded modes works
- **Batch report** — every batch run writes `<outdir>/batch_report.json` with per-file status (success/failed/skipped), output path, size, duration, failure reason, and timestamp, plus summary counts; the process now exits non-zero when any file failed (clean run → 0, failures → 1, Ctrl+C → 130), so CI can gate on the batch exit code
- **`peakbars` visualizer** — `--mode peakbars` renders the spectrum as vertical bars with persistent peak indicators: each bar's maximum recent height is held at full brightness for `--peakbars-hold` seconds (default 0.1), then decays away over `--peakbars-decay` seconds (default 0.6). `showfreqs` cannot hold peaks, so the plugin builds a custom filter chain — a split fan-out, per-tap `tmix` delays, `colorchannelmixer` attenuation, and a pairwise `blend=lighten` max tree (shared with `oscilloscope` in `visualizers/utils.py`)
- **`oscilloscope` visualizer** — `--mode oscilloscope` shows the raw waveform as a rolling point-to-point trace on a dark graticule (`--oscilloscope-grid`, default 0.25 = line every quarter of the frame; 0.0 disables) with trace persistence: recent positions fade out as an afterglow over `--oscilloscope-persist` seconds (default 0.5; 0.0 disables). `--oscilloscope-scale` selects the amplitude scale (`lin`, `sqrt`, `cbrt` (default), `log`, `dbl`, `pwr`). Distinct from the `waveform` mode, which is plain scrolling `showwaves` without grid or persistence
- **Peak-hold/afterglow chain helper** — `visualizers/utils.build_peak_hold_chain()` composes the delay/attenuate/max filter graph; hold+decay requests are clamped to a 60-tap budget (2 s at 30 fps), scaled proportionally when exceeded
- **New-plugin tests** — unit tests for both plugins and the chain builder (label discipline, tap counts, clamping, degenerate hold=0/decay=0 and persist=0/graph=0 paths) plus end-to-end encodes with default and custom options

### Fixed
- **CI lint failure in peak-hold chain tests** — `tests/test_visualizers.py` used the `str | None` graph returned by `build_peak_hold_chain()` without narrowing; pyright flagged the `findall`/`in` usages (reportCallIssue/reportOperatorIssue)
- **Installed plugins never loaded at runtime** — `--install-plugin` copied plugins to `~/.audio_visualizer/plugins`, but the CLI's registry never scanned that directory, so installed plugins never appeared in `--list-plugins` or `--mode`
- **Missing `--plugin-path` targets were silent** — nonexistent or non-`.py` paths now warn instead of being ignored

### Changed
- **pyright type checking in CI** — the package is checked with pyright (standard mode; the public plugin API in `visualizers/base.py` and `visualizers/registry.py` in strict mode); the plugin base class, registry, and config module APIs are fully typed

## [2.0.0] - 2026-10-29

### Changed — Plugin System Overhaul
- **Per-plugin option schemas** — every plugin declares its options via a `PluginOption` schema; the CLI auto-generates flags from these schemas, so adding a plugin no longer requires touching `__main__.py`
- **Filter-only `build_filter()`** — plugins return the filter graph ending at their main output label (default `[viz]`) instead of the complete `[out]` composition; the base class composes the final `[out]` via the new `compose_final_filter()` hook and supports multi-output plugins returning `dict[str, str]`
- **Granular plugin hooks** — `get_inputs()`, `get_codec_settings()`, `compose_final_filter()`, `post_process_filter()`, `get_output_label()`, and `get_bg_opacity()` replace `build_command()` overrides; `albumart` and `vectorscope` now use hooks instead of full command overrides
- **Shared filter utilities** — duplicated background/overlay code across plugins replaced with `visualizers/utils.py` helpers
- **Enhanced plugin metadata** — `category`, `requires_ffmpeg_version`, and `input_types` fields
- **Plugin validation & isolation** — the registry validates schemas on load and skips broken plugins with a warning instead of crashing
- **Schema-aware config file** — per-plugin YAML sections validated against option schemas; `--save-config` writes non-default plugin options
- **Category-based CLI** — `--list-plugins --category <cat>` and `--list-plugins --verbose`; `--help` groups plugin flags by category

### Fixed
- **User options ignored in the actual encode** — the encode command was built from a reduced args dict, so plugin options (`--spectrum-mode`, `--waveform-mode`, …), `--bg-color`, `--border*`, and `--format` never reached ffmpeg (only the verbose display showed them); `run_visualizer` now passes the full args dict
- **`--border` produced an invalid filter graph** — the border chain was appended without a chain separator (`…[out]format=rgba…`), so any border render failed in ffmpeg; the chain now consumes the `[out]` pad properly
- **Batch mode crashed with `AttributeError`** — a stale `vectorscope_draw` reference (no such flag exists); batch now also forwards `--border*` and the vectorscope border/framerate/color-index options
- **Test-encode size estimation** — the short test encode used by the size estimator was silently broken (missing `options` argument and string-sniffed background detection); it now uses the plugin's `build_filter_complex()` and `get_inputs()` hooks, so size estimates are measured instead of falling back to the formula
- **`--vectorscope-border`, `--vectorscope-framerate`, `--vectorscope-color-index`** — these flags existed but were never passed to the plugin; they now work
- **Album art `--albumart-position top`** — the filter graph referenced an undefined `[with_spectrum]` label and failed in ffmpeg; it now correctly overlays the spectrum on the processed image
- **`circular-spectrum` could never encode** — its filter graph consumed the `[spectrum]` label four times (ffmpeg rejects a label consumed more than once); the spectrum is now fanned out with `split=4`
- **Batch aborted on the first file failure** — an ffmpeg failure raised `SystemExit(1)` inside the batch loop, which `except Exception` does not catch; one bad file killed the whole batch. Failures are now counted per file and the batch continues (Ctrl+C still aborts)
- **Unknown `--mode` crashed with `TypeError`** — `", ".join(registry.list_plugins())` joins a list of metadata dicts; the message now lists the available mode names (batch and dry-run paths too)
- **Crash when ffprobe cannot read the duration** — `duration=None` hit `duration <= 0` in the size estimator; now handled
- **Size estimator's measured path was dead code** — `shutil` was imported only in the albumart branch, so every other plugin raised a swallowed `NameError`, fell back to the formula silently, and leaked a temp dir per run
- **`--aspect-ratio` was a dead flag** — parsed but never applied; it now recomputes the resolution from the base width (`apply_aspect_ratio()`)
- **~15 plugin options silently dropped** — single-file, batch, and both dry-run paths used stale curated args dicts (missing `spectrum-style/opacity/start/stop`, `bar-*`, `circular-spectrum-*`, `mirror-opacity`, `spectrogram-speed/opacity/transpose`, `waveform-colors-per-channel`); all paths now build args from the full CLI namespace via `build_args_dict()`
- **`--preset` broke hardware encodes** — nvenc rejects `ultrafast`/`superfast`/`veryfast`/`faster`/`slower`/`veryslow`, qsv rejects `ultrafast`/`superfast`, and h264_vaapi has no preset option at all; presets are now mapped per encoder (`ultrafast`→`p1` on nvenc, `ultrafast`→`veryfast` on qsv, omitted on vaapi)
- **QSV/VA-API quality mapping was inverted** — `31 - crf` made lower CRF (better quality) produce worse encoding; now `clamp(crf, 1, 31)`
- **`--bar-orientation vertical` produced a portrait video** (H×W) in a W×H session; the frame is now transposed back to the requested size
- **`--vectorscope-border` was invisible** — the opaque scope was drawn over a same-size border underlay; the border is now larger than the scope with the scope centered on it
- **`--spectrogram-transpose` mismatched the advertised resolution** — the rotated frame is now scaled back to the requested WxH
- **`--validate-config` false positive** — "CRF incompatible with hardware encoding" was an ERROR although the pipeline remaps CRF for hw encoders; now an accurate WARNING
- **`--visualizer-config` presets saved `input` and CLI-management flags** — loading a preset overwrote the current input file; presets now contain only encoding and plugin-schema options
- **`--retry` with a negative value ran zero attempts** and produced nothing; clamped to ≥ 0
- **`--bar-width`/`--bar-radius` were dead options** (computed but never used; `showspectrum` has no such parameters); removed from the schema
- **Missing albumart image** — now a clean error message and exit 1 instead of a traceback

## [1.5.0] - 2026-10-28

### Added
- **CQT (Constant Q Transform) visualizer** — Music-theory-friendly frequency display with logarithmic spacing, ideal for musical content
- **Showfreqs visualizer** — Frequency-domain visualization with labeled bands using ffmpeg's `showfreqs` filter
- **Showvolume visualizer** — Reactive volume meter (peak/RMS) with configurable orientation and scale
- **Circular Spectrum visualizer** — True radial/circular spectrum wrapped into a circle using hstack/vstack/transpose
- `--spectrum-mode` flag — 16+ colormapping modes (swirl, rainbow, fire, magma, viridis, etc.)
- `--spectrum-style` flag — `replace`, `scroll`, `fill` display styles
- `--spectrum-opacity` flag — Control spectrum opacity (0.0–1.0)
- `--spectrum-start` / `--spectrum-stop` flags — Restrict displayed frequency range
- `--bar-width` flag — Custom bar width/thickness in pixels
- `--bar-spacing` flag — Control spacing between bars
- `--bar-orientation` flag — `horizontal` or `vertical` display
- `--bar-radius` flag — Rounded bar tops (0–max radius)
- `--waveform-mode` flag — `line`, `point`, `p2p`, `cline`, `pict` (static picture)
- `--waveform-splits` flag — Split waveform into 1–8 channels
- `--waveform-frame` flag — Audio samples per frame
- `--waveform-colors-per-channel` flag — Assign different colors per channel
- `--mirror-axis` flag — `x`, `y`, or `xy` flip mode for mirrored spectrum
- `--mirror-gap` flag — Gap pixels between original and mirrored halves
- `--mirror-opacity` flag — Opacity of mirrored half (0.0–1.0)
- `--vectorscope-mode` flag — `frame`, `line`, `dot` draw modes
- `--vectorscope-scale` flag — `lin`, `sqrt`, `cbrt`, `log` amplitude scales
- `--vectorscope-zoom` flag — Zoom level (0.1–10.0)
- `--vectorscope-trails` flag — Trail persistence (0–255)
- `--vectorscope-framerate` flag — Custom frame rate for vectorscope trace
- `--vectorscope-border` flag — Add border/frame around the scope
- `--vectorscope-color-index` flag — Select palette color by index
- `--spectrogram-speed` flag — Control waterfall scroll speed
- `--spectrogram-mode` flag — `intensity`, `rain`, `fire`, `heat`, `ice`, `swirl` modes
- `--spectrogram-opacity` flag — Waterfall opacity (0.0–1.0)
- `--spectrogram-transpose` flag — Rotate spectrogram 90°
- `--albumart-effect` flag — `glow`, `pulse`, `zoom` background effects
- `--albumart-position` flag — Spectrum overlay position (`bottom`, `top`, `left`, `right`, `fullscreen`)
- `--albumart-glow-intensity` flag — Control glow intensity (0.0–1.0)
- `--albumart-fit` flag — `cover`, `contain`, `stretch` image fit modes
- `--albumart-blur` flag — Gaussian blur radius (0–50)
- `--bg-color` flag — Custom background color for all plugins
- `--border` flag — Colored border around visualization
- `--border-color` flag — Border color
- `--border-width` flag — Border width in pixels

### Changed
- All plugins now use unified `ColorParser` for consistent color handling
- Showfreqs filter graph now properly chains background and overlay
- Showvolume filter now uses correct `w=`/`h=` parameters instead of `size=`

### Fixed
- Showfreqs `:format=` now chains as separate filter instead of invalid filter option
- Showvolume `:mode=` corrected to `:m=`, `:size=` corrected to `:w=`/`:h=`
- Waveform pict mode no longer passes invalid `mode=separate_colors` to `showwavespic`
- Vectorscope color parsing now supports full palette selection

## [1.4.0] - 2026-10-27

### Added
- `--theme` CLI flag for predefined color themes (neon, sunset, ocean, forest, dark, light)
- `--colors` CLI flag for custom color palettes
- Batch processing mode (`--batch` / `-b`) for processing entire directories
- `--image` flag for album art visualizer plugin
- `--install-plugin` flag for installing custom plugins
- `--list-plugins` flag to list all available visualizer plugins
- `--config` flag to show current configuration file path
- `--save-config` flag to save current options to configuration file
- `--overwrite` flag for batch mode to replace existing output files
- Plugin registry system with automatic discovery
- User plugin directory support (`~/.audio_visualizer/plugins/`)

### Changed
- **BREAKING**: `colors` parameter now works consistently across all plugins (waveform, bars, radial, spectrogram, vectorscope, albumart, spectrum)
- Hardware acceleration auto-detection now checks for NVENC, QSV, and VA-API encoders
- Configuration file format changed to simple YAML-like key-value pairs

### Fixed
- `colors` parameter no longer causes `TypeError` in non-spectrum plugins
- `mode` setting from config file now properly applied via `merge_config`

### Improved
- Test coverage increased from 70% to 90%
- Added ruff linting and formatting checks to CI
- Added Codecov coverage upload to CI
- Added branch coverage tracking (`--cov-branch`)
- Progress bar with ETA during encoding
- Better error messages for missing ffmpeg and input files

## [1.2.0] - 2026-10-26

### Added
- Initial public release
- Plugin-based architecture for visualizers
- Built-in visualizers: spectrum, waveform, bars, radial, spectrogram, vectorscope, album art
- Hardware acceleration support (NVENC, QSV, VA-API)
- Multiple output formats (MP4, MKV, WebM, AVI, MOV, FLV)
- Configuration file support (~/.audio_visualizer/config.yml)
- CLI argument parsing with sensible defaults

[Unreleased]: https://github.com/fredjt/music-visualizer/compare/v1.5.0...HEAD
[1.5.0]: https://github.com/fredjt/music-visualizer/releases/tag/v1.5.0
[1.4.0]: https://github.com/fredjt/music-visualizer/releases/tag/v1.4.0
[1.2.0]: https://github.com/fredjt/music-visualizer/releases/tag/v1.2.0

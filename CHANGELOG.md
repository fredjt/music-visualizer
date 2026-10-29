# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
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

### Fixed
- **Installed plugins never loaded at runtime** — `--install-plugin` copied plugins to `~/.audio_visualizer/plugins`, but the CLI's registry never scanned that directory, so installed plugins never appeared in `--list-plugins` or `--mode`
- **Missing `--plugin-path` targets were silent** — nonexistent or non-`.py` paths now warn instead of being ignored

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

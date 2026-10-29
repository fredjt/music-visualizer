# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased] — v2.0.0 (in development)

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

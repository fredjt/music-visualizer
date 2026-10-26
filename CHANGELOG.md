# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

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

[Unreleased]: https://github.com/fredjt/music-visualizer/compare/v1.2.0...HEAD
[1.2.0]: https://github.com/fredjt/music-visualizer/releases/tag/v1.2.0

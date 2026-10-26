# Audio Visualizer — Release v1.3.0 Improvement Targets

## 1. High Priority — Test Coverage

| Area | Current Coverage | Gap |
|------|-----------------|-----|
| `albumart.py` | **21%** | No tests for `build_filter()` or `build_command()` with real image, no error path for missing image |
| `registry.py` | **61%** | No tests for `uninstall()`, `install_from_file()` success path, user plugin dir loading, duplicate plugin handling |
| `spectrum.py` | **53%** | No tests for custom `colors` parameter (`colormapping` mode) |
| `config.py` | **77%** | No tests for float/int parsing edge cases, `mode` validator, `output_dir` in config, `theme` resolution in `merge_config` |

**Missing plugin tests entirely:**
- `radial.py` — no unit tests for `build_filter()` output
- `spectrogram.py` — no unit tests for `build_filter()`
- `bars.py` — no unit tests for `build_filter()`
- `vectorscope.py` — no tests for its custom `build_command()` override
- `waveform.py` — only `build_filter()` tested, no `build_command()` test

**Missing main() tests:**
- `run_visualizer()` — no unit tests (currently only integration tests with real ffmpeg)
- `_process_batch()` — no unit tests
- `list_plugins()` — no unit tests
- `_run_with_progress()` — no tests for KeyboardInterrupt, progress bar completion, or stderr capture
- CLI argument parsing — no tests for `--config`, `--save-config`, `--install-plugin`, `--list-plugins`, `--batch`, `--overwrite`, `--colors`, `--theme`

---

## 2. Medium Priority — Code Quality & Bug Fixes

- **`colors` parameter inconsistency**: The `colors` argument is passed through to `build_filter()` in `__main__.py` but only `spectrum.py` actually uses it. Other plugins ignore it silently.
- **`mode` in `key_map`**: `config.py` has `"mode"` in `VALID_KEYS` and `DEFAULT_CONFIG` but it's missing from the `key_map` in `merge_config()`, so the config file `mode` setting never applies.
- **`__main__.py` excluded from coverage**: At 662 lines, it's the largest file and contributes nothing to coverage. Consider extracting `run_visualizer()`, `_run_with_progress()`, `_process_batch()`, and `list_plugins()` into a separate module so they can be tested.
- **Plugin loading failures are silent**: `PluginRegistry._load_from_package()` catches all exceptions and just prints a warning. Should log or raise with more context.
- **`detect_hwaccel()` timeout path**: The `except (subprocess.TimeoutExpired, FileNotFoundError)` path in `detect_hwaccel()` is not tested.

---

## 3. Medium Priority — CI/CD Improvements

- **Add linting step**: `ruff` is configured in `pyproject.toml` but not run in CI. Add a `lint` job.
- **Add coverage reporting**: Upload coverage.xml to Codecov or similar.
- **Add `--cov-branch`**: Already configured in `pyproject.toml` but CI overrides with `pytest -v --tb=short --cov-report=xml` which drops branch coverage.
- **Add a PyPI publish workflow**: For releasing to PyPI on tags.

---

## 4. Lower Priority — Feature & UX Improvements

- **Environment variable support**: Allow overriding config via env vars (e.g., `AUDIO_VISUALIZER_RESOLUTION`).
- **Config validation at startup**: Validate the entire config before running, not just individual values during parsing.
- **Logging system**: Replace `print()` statements with proper `logging` module for better control over verbosity.
- **Retry logic**: Add optional retry for ffmpeg failures (transient issues).
- **Plugin versioning & validation**: Add a `--validate` flag for installed plugins, and check version compatibility.
- **More test assets**: Add AAC, M4A, and stereo audio test files; add audio with different sample rates (44100, 48000, 96000 Hz).
- **CHANGELOG**: Add a `CHANGELOG.md` to track release changes.
- **`--theme` CLI support**: The `--theme` flag exists but is only resolved in `merge_config()`. Need to ensure it works when passed directly on the CLI (not just from config file).
- **Progress bar for batch mode**: The batch mode shows a file-level progress bar but no encoding progress per file.

---

## 5. Suggested Release Checklist for v1.3.0

```
[x] Fix `mode` in merge_config key_map
[x] Add tests for albumart.py (build_filter + build_command)
[x] Add tests for registry.py (uninstall, install_from_file)
[x] Add tests for spectrum.py (custom colors)
[x] Add tests for radial, spectrogram, bars plugins
[x] Add tests for _run_with_progress (KeyboardInterrupt, stderr)
[x] Add tests for run_visualizer (mocked ffmpeg)
[x] Add tests for CLI flags (--config, --save-config, --batch, --theme)
[x] Add ruff lint job to CI
[x] Fix CI pytest command to include --cov-branch
[x] Add coverage upload to CI
[x] Add CHANGELOG.md
[ ] Add more test audio assets (AAC, M4A, stereo)
[ ] Ensure --theme works from CLI (not just config file)
[x] Fix colors parameter consistency across all plugins
```

### Coverage Progress

| Module | Before | After |
|--------|--------|-------|
| `albumart.py` | 21% | 100% (skipped) |
| `registry.py` | 61% | 85% |
| `spectrum.py` | 53% | 100% (skipped) |
| `config.py` | 77% | 86% |
| **Total** | **70%** | **90%** |

### Test Count

| | Before | After |
|---|--------|-------|
| Tests | 54 | 103 |
| New tests | — | +49 |

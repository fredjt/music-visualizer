# Audio Visualizer

A plugin-based Python tool for converting audio files into animated visualizer videos.

## Features

- **Plugin Architecture**: Easily create, add, or remove visualizer plugins
- **Multiple Visualizer Modes**: Choose from several visualization styles
- **Hardware Acceleration**: NVENC (NVIDIA), QSV (Intel), VA-API (Linux) support
- **Multiple Output Formats**: MP4, MKV, WebM, AVI, MOV, FLV
- **Batch Processing**: Process entire directories of audio files
- **Progress Tracking**: Real-time progress bar with ETA
- **Customizable**: Adjust resolution, FPS, preset, CRF, and more

## Available Visualizers

- **Spectrum** (default) - Classic frequency spectrum bars
- **Waveform** - Audio waveform visualization
- **Bars** - Animated bar visualization
- **Radial** - Radial/circular spectrum display
- **Spectrogram** - Time-frequency spectrogram
- **Vectorscope** - Psychedelic circular visualization
- **Album Art** - Visualizer with album art overlay

## Requirements

- Python 3.10+
- [FFmpeg](https://ffmpeg.org/) - Required for video encoding

## Installation

1. Clone the repository:
   ```bash
   git clone <repository-url>
   cd audio-visualizer
   ```

2. Install FFmpeg:
   - **Ubuntu/Debian**: `sudo apt install ffmpeg`
   - **macOS**: `brew install ffmpeg`
   - **Windows**: Download from [ffmpeg.org](https://ffmpeg.org/download.html)

3. Install the package:
   ```bash
   pip install .
   ```

## Usage

### Basic Usage

```bash
audio-visualizer input.mp3
```

### Specify a Visualizer Mode

```bash
audio-visualizer input.mp3 --mode waveform
audio-visualizer input.mp3 --mode radial

# Compose several visualizers side by side in one frame
audio-visualizer input.mp3 --mode spectrum waveform
```

### Custom Output

```bash
audio-visualizer input.mp3 -o output.mp4 --resolution 1920x1080
```

### Hardware Acceleration

```bash
# Auto-detect (default)
audio-visualizer input.mp3

# Force NVIDIA encoding
audio-visualizer input.mp3 --accel nvenc

# Force Intel Quick Sync
audio-visualizer input.mp3 --accel qsv

# Force Linux VA-API
audio-visualizer input.mp3 --accel vaapi

# Disable hardware acceleration
audio-visualizer input.mp3 --accel disabled
```

### Output Format

```bash
# MP4 (default)
audio-visualizer input.mp3

# MKV
audio-visualizer input.mp3 --format mkv

# WebM (VP9)
audio-visualizer input.mp3 -f webm

# AVI
audio-visualizer input.mp3 -f avi
```

### Batch Processing

Process all audio files in a directory:

```bash
# Process all audio files in a directory
audio-visualizer ./my-album/ --batch

# Short form
audio-visualizer ./my-album/ -b

# With custom settings
audio-visualizer ./my-album/ -b --mode waveform --resolution 1920x1080
```

Supported formats: MP3, WAV, FLAC, OGG, M4A, AAC, WMA

### Environment Variables

All configuration options can be set via environment variables with the `AUDIO_VISUALIZER_` prefix. This is useful for Docker, CI/CD, or shell profiles.

```bash
# Set resolution and FPS via environment
export AUDIO_VISUALIZER_RESOLUTION=1920x1080
export AUDIO_VISUALIZER_FPS=60
export AUDIO_VISUALIZER_PRESET=fast

audio-visualizer input.mp3
```

Supported environment variables:

| Variable | Description | Example |
|---|---|---|
| `AUDIO_VISUALIZER_RESOLUTION` | Output resolution | `1920x1080` |
| `AUDIO_VISUALIZER_FORMAT` | Output format | `mkv` |
| `AUDIO_VISUALIZER_FPS` | Frame rate | `60` |
| `AUDIO_VISUALIZER_PRESET` | Encoding preset | `fast` |
| `AUDIO_VISUALIZER_CRF` | Quality (0-51) | `18` |
| `AUDIO_VISUALIZER_ACCEL` | Hardware acceleration | `nvenc` |
| `AUDIO_VISUALIZER_MODE` | Visualizer mode | `waveform` |
| `AUDIO_VISUALIZER_COLORS` | Custom colors | `red,blue,green` |
| `AUDIO_VISUALIZER_THEME` | Color theme | `neon` |
| `AUDIO_VISUALIZER_OUTPUT_DIR` | Output directory | `/path/to/output` |

**Precedence**: CLI arguments > environment variables > config file > defaults.

### Configuration File

Options can be persisted to `~/.audio_visualizer/config.yml`. Use `--save-config` to write the current options and `--config` to display the file:

```bash
audio-visualizer input.mp3 --save-config
audio-visualizer --config
```

Per-plugin options can be set in indented sections. Values are validated against each plugin's option schema (type, choices, range):

```yaml
# Global options
resolution: 1920x1080
fps: 60

# Per-plugin options
spectrum:
  mode: rainbow
  opacity: 0.8
waveform:
  mode: line
  splits: 2
```

Unknown plugins/options and values that fail validation are skipped with a warning, so a broken config file never crashes the tool.

### List Available Plugins

```bash
audio-visualizer --list-plugins
```

### Install Custom Plugins

```bash
audio-visualizer --install-plugin my_plugin.py
```

Installs the plugin to `~/.audio_visualizer/plugins`, where it is
auto-discovered on every run.

### Load External Plugins

Plugins can be loaded without installing, either for one run or for all
runs:

```bash
# From the command line (repeatable, file or directory)
audio-visualizer --plugin-path ~/plugins/my_plugin.py --mode myviz input.mp3
audio-visualizer --plugin-path ~/plugins/ --list-plugins

# For all runs, via environment variable (path-separated list)
export AUDIO_VISUALIZER_PLUGIN_PATH=~/plugins/my_plugin.py:~/plugins/other/
```

Third-party distributions can ship plugins too: register them under the
`audio-visualizer.plugins` entry-point group (see *Creating a New Visualizer
Plugin*). Installed plugins and `--plugin-path` plugins shadow built-ins of
the same name, with a warning; `--list-plugins --verbose` shows each
plugin's source (builtin, entrypoint, installed, or path).

### Full Usage

```bash
audio-visualizer input.mp3 [options]
audio-visualizer ./directory/ --batch [options]

Options:
  --mode MODE [MODE ...]   Visualizer mode(s); 2+ are composed into one frame (default: spectrum)
  --resolution RES         Output resolution WxH (default: 1280x720)
  --fps FPS                Frame rate (default: 30)
  -o, --output FILE        Output filename
  -f, --format FORMAT      Output format: mp4, mkv, webm, avi, mov, flv
  --accel ACCEL            Hardware acceleration: auto, nvenc, qsv, vaapi, disabled
  --preset PRESET          Encoding preset (default: medium)
  --crf CRF                Quality 0-51 (default: 23, lower=better)
  -b, --batch DIRECTORY    Process all audio files in a directory
  --image FILE             Image file for album art visualizer
  --list-plugins           List all available visualizer plugins
  --install-plugin FILE    Install a plugin from a Python file
  -v, --verbose            Show detailed filter and command info
  -h, --help               Show this help message

All options can also be set via environment variables (e.g., AUDIO_VISUALIZER_RESOLUTION=1920x1080).
```

## Creating a New Visualizer Plugin

1. Create a Python file with a class inheriting from `VisualizerPlugin` in
   `audio_visualizer/visualizers/base.py`
2. Define a `metadata` (`PluginMetadata`) and an `options` list (`PluginOption`)
   — the CLI flags are auto-generated from this schema
3. Implement `build_filter()`
4. Choose how it gets discovered:
   - **Built-in**: place the file in the `visualizers/` directory
   - **Installed**: `audio-visualizer --install-plugin my_plugin.py`
   - **External path**: `--plugin-path` or `AUDIO_VISUALIZER_PLUGIN_PATH`
   - **Distribution**: ship a package registering an entry point, e.g.

     ```toml
     [project.entry-points."audio-visualizer.plugins"]
     myviz = "mymypkg.plugin:MyVizPlugin"
     ```

All discovery paths apply the same schema validation and isolation: a broken
plugin is skipped with a warning instead of crashing the run.

### The `build_filter()` contract

`build_filter()` returns the filter graph for your visualization. It must
produce the plugin's **main output** labeled with `get_output_label()`
(default: `viz`) and must **not** produce the final `[out]` label — the
base class composes that (overlaying your output on the background input,
or relabeling it) and then applies post-processing such as the border.

```python
def build_filter(self, width, height, fps, options, audio_index=0, video_index=1, **kwargs):
    return f"[{audio_index}:a] showspectrum=size={width}x{height}[viz]"
```

For multi-layer visualizations, return a `dict` mapping output names to
filter segments (the first key is the main output):

```python
def build_filter(self, width, height, fps, options, **kwargs):
    return {
        "viz": "[0:a] showvolume=w=1280:h=720[viz]",
        "spectrum": "[0:a] showspectrum=size=1280x720[spectrum]",
    }
```

Plugins that need custom inputs (image files, no background, etc.)
override `get_inputs()`, and plugins with a custom final composition
override `compose_final_filter()`. See `albumart.py`, `vectorscope.py`,
and `radial.py` for examples.

See existing plugins for examples.

## Project Structure

```
audio_visualizer/
├── __init__.py
├── __main__.py              # Main application entry point
└── visualizers/
    ├── __init__.py
    ├── base.py              # Base plugin class
    ├── registry.py          # Plugin registry system
    ├── spectrum.py          # Spectrum visualizer
    ├── waveform.py          # Waveform visualizer
    ├── bars.py              # Bars visualizer
    ├── radial.py            # Radial visualizer
    ├── spectrogram.py       # Spectrogram visualizer
    ├── vectorscope.py       # Vectorscope visualizer
    └── albumart.py          # Album art visualizer
```

## License

MIT License

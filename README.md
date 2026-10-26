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

### List Available Plugins

```bash
audio-visualizer --list-plugins
```

### Install Custom Plugins

```bash
audio-visualizer --install-plugin my_plugin.py
```

### Full Usage

```bash
audio-visualizer input.mp3 [options]
audio-visualizer ./directory/ --batch [options]

Options:
  --mode MODE              Visualizer mode (default: spectrum)
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
```

## Creating a New Visualizer Plugin

1. Create a new file in the `visualizers/` directory
2. Inherit from `VisualizerPlugin` in `audio_visualizer/visualizers/base.py`
3. Implement the required methods
4. The plugin will be automatically discovered

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

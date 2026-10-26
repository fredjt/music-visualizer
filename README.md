# Audio Visualizer

A plugin-based Python tool for converting audio files into animated visualizer videos.

## Features

- **Plugin Architecture**: Easily create, add, or remove visualizer plugins
- **Multiple Visualizer Modes**: Choose from several visualization styles
- **FFmpeg Integration**: Outputs high-quality MP4 videos
- **Customizable**: Adjust resolution, output filename, and more

## Available Visualizers

- **Spectrum** (default) - Classic frequency spectrum bars
- **Waveform** - Audio waveform visualization
- **Bars** - Animated bar visualization
- **Radial** - Radial/circular spectrum display
- **Spectrogram** - Time-frequency spectrogram
- **Vectorscope** - Audio vectorscope visualization
- **Album Art** - Visualizer with album art overlay

## Requirements

- Python 3.6+
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

## Usage

### Basic Usage

```bash
python3 audio_visualizer.py input.mp3
```

### Specify a Visualizer Mode

```bash
python3 audio_visualizer.py input.mp3 --mode waveform
python3 audio_visualizer.py input.mp3 --mode radial
```

### Custom Output

```bash
python3 audio_visualizer.py input.mp3 -o output.mp4 --resolution 1920x1080
```

### List Available Plugins

```bash
python3 audio_visualizer.py --list-plugins
```

### Full Usage

```bash
python3 audio_visualizer.py input.mp3 [options]

Options:
  --mode MODE          Visualizer mode (default: spectrum)
  --resolution RES     Output resolution (e.g., 1920x1080)
  -o, --output FILE    Output filename
  --list-plugins       List all available visualizer plugins
  -h, --help           Show this help message
```

## Creating a New Visualizer Plugin

1. Create a new file in the `visualizers/` directory
2. Inherit from `VisualizerPlugin` in `visualizers/base.py`
3. Implement the required methods
4. Register your plugin in the plugin registry

See existing plugins for examples.

## Project Structure

```
audio_visualizer.py      # Main application entry point
visualizers/
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

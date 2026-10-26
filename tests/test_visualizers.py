"""Tests for visualizer plugins."""

import pytest

from audio_visualizer.visualizers.base import PluginMetadata, VisualizerPlugin
from audio_visualizer.visualizers.spectrum import SpectrumPlugin
from audio_visualizer.visualizers.waveform import WaveformPlugin


class TestSpectrumPlugin:
    """Test spectrum visualizer plugin."""

    def test_metadata(self):
        """Test plugin metadata."""
        meta = SpectrumPlugin.get_metadata()
        assert meta.name == "spectrum"
        assert meta.display_name == "Color Spectrum"
        assert meta.version == "1.0.0"

    def test_build_filter(self):
        """Test filter building."""
        plugin = SpectrumPlugin()
        filter_complex = plugin.build_filter(1920, 1080, 30)
        assert "showspectrum" in filter_complex
        assert "1920x1080" in filter_complex
        assert "30" in filter_complex

    def test_build_command(self):
        """Test command building."""
        plugin = SpectrumPlugin()
        cmd = plugin.build_command(
            {
                "input": "test.mp3",
                "output": "test.mp4",
                "width": 1920,
                "height": 1080,
                "fps": 30,
                "preset": "medium",
                "crf": 23,
                "format": "mp4",
                "accel": "sw",
            }
        )
        assert cmd[0] == "ffmpeg"
        assert "-i" in cmd
        assert "test.mp3" in cmd
        assert "-filter_complex" in cmd
        assert "-c:v" in cmd


class TestWaveformPlugin:
    """Test waveform visualizer plugin."""

    def test_metadata(self):
        """Test plugin metadata."""
        meta = WaveformPlugin.get_metadata()
        assert meta.name == "waveform"
        assert meta.display_name == "Gradient Waveform"

    def test_build_filter(self):
        """Test filter building."""
        plugin = WaveformPlugin()
        filter_complex = plugin.build_filter(1920, 1080, 30)
        assert "showwaves" in filter_complex
        assert "1920x1080" in filter_complex


class TestBasePlugin:
    """Test base plugin class."""

    def test_get_metadata_not_implemented(self):
        """Test that get_metadata raises error if metadata is None."""

        class BadPlugin(VisualizerPlugin):
            metadata = None

            def build_filter(self, width, height, fps, audio_index=0, video_index=1, colors=None):
                return ""

        with pytest.raises(NotImplementedError):
            BadPlugin.get_metadata()

    def test_build_command_default(self):
        """Test default build_command implementation."""

        class TestPlugin(VisualizerPlugin):
            metadata = PluginMetadata(
                name="test",
                display_name="Test",
                description="Test plugin",
            )

            def build_filter(self, width, height, fps, audio_index=0, video_index=1, colors=None):
                return f"[{audio_index}:a] testfilter[out]"

        plugin = TestPlugin()
        cmd = plugin.build_command(
            {
                "input": "test.mp3",
                "output": "test.mp4",
                "width": 1280,
                "height": 720,
                "fps": 30,
                "preset": "medium",
                "crf": 23,
                "format": "mp4",
                "accel": "sw",
            }
        )

        assert cmd[0] == "ffmpeg"
        assert "-y" in cmd
        assert "-shortest" in cmd
        assert "test.mp4" in cmd


class TestNvencCommand:
    """Test NVENC hardware acceleration command building."""

    def test_nvenc_command(self):
        """Test that nvenc accel produces correct ffmpeg command."""
        plugin = SpectrumPlugin()
        cmd = plugin.build_command(
            {
                "input": "test.mp3",
                "output": "test.mp4",
                "width": 1920,
                "height": 1080,
                "fps": 30,
                "preset": "medium",
                "crf": 23,
                "format": "mp4",
                "accel": "nvenc",
            }
        )
        assert cmd[0] == "ffmpeg"
        assert "-c:v" in cmd
        nvenc_idx = cmd.index("-c:v")
        assert cmd[nvenc_idx + 1] == "h264_nvenc"
        assert "-preset" in cmd
        assert "-pix_fmt" in cmd
        pix_fmt_idx = cmd.index("-pix_fmt")
        assert cmd[pix_fmt_idx + 1] == "yuv420p"
        assert "-rc" in cmd
        rc_idx = cmd.index("-rc")
        assert cmd[rc_idx + 1] == "vbr"
        assert "-cq" in cmd
        cq_idx = cmd.index("-cq")
        assert cmd[cq_idx + 1] == "26"  # crf(23) + 3

    def test_nvenc_vectorscope_command(self):
        """Test that vectorscope plugin respects nvenc accel."""
        from audio_visualizer.visualizers.vectorscope import VectorscopePlugin

        plugin = VectorscopePlugin()
        cmd = plugin.build_command(
            {
                "input": "test.mp3",
                "output": "test.mp4",
                "width": 1920,
                "height": 1080,
                "fps": 30,
                "preset": "medium",
                "crf": 23,
                "format": "mp4",
                "accel": "nvenc",
            }
        )
        assert cmd[0] == "ffmpeg"
        nvenc_idx = cmd.index("-c:v")
        assert cmd[nvenc_idx + 1] == "h264_nvenc"
        assert "-shortest" in cmd


class TestIntegration:
    """Integration tests using real audio/image files."""

    def test_load_audio_formats(self):
        """Test loading different audio formats."""
        import subprocess

        formats = ["test.wav", "test.mp3", "test.flac", "test.ogg"]
        for fmt in formats:
            path = f"tests/assets/{fmt}"
            result = subprocess.run(
                ["ffprobe", "-v", "error", "-show_entries", "format=duration",
                 "-of", "csv=p=0", path],
                capture_output=True, text=True
            )
            assert result.returncode == 0
            duration = float(result.stdout.strip())
            assert duration > 0
            assert duration <= 11  # Should be ~10 seconds

    def test_mono_audio(self):
        """Test loading mono audio."""
        import subprocess

        result = subprocess.run(
            ["ffprobe", "-v", "error", "-show_entries", "stream=channels",
             "-of", "csv=p=0", "tests/assets/mono.mp3"],
            capture_output=True, text=True
        )
        assert result.returncode == 0
        assert result.stdout.strip() == "1"  # Mono = 1 channel

    def test_long_audio(self):
        """Test loading long audio file."""
        import subprocess

        result = subprocess.run(
            ["ffprobe", "-v", "error", "-show_entries", "format=duration",
             "-of", "csv=p=0", "tests/assets/long.mp3"],
            capture_output=True, text=True
        )
        assert result.returncode == 0
        duration = float(result.stdout.strip())
        assert duration >= 299  # Should be ~5 minutes

    def test_image_formats(self):
        """Test loading different image formats."""
        from pathlib import Path

        images = ["album.jpg", "album.png", "small.jpg"]
        for img in images:
            path = Path(f"tests/assets/{img}")
            assert path.exists()
            assert path.stat().st_size > 0

    def test_invalid_image(self):
        """Test that invalid image is detected."""
        from pathlib import Path

        path = Path("tests/assets/invalid.txt")
        assert path.exists()
        content = path.read_text()
        assert "not an image" in content.lower()

    def test_batch_directory(self):
        """Test batch directory structure."""
        from pathlib import Path

        batch_dir = Path("tests/assets/batch")
        assert batch_dir.exists()
        audio_files = list(batch_dir.glob("*"))
        assert len(audio_files) >= 3
        extensions = {f.suffix.lower() for f in audio_files}
        assert ".wav" in extensions or ".mp3" in extensions

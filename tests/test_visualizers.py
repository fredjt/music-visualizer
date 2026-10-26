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

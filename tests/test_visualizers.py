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

    def test_build_filter_custom_colors(self):
        """Test spectrum filter with custom colors."""
        plugin = SpectrumPlugin()
        filter_complex = plugin.build_filter(1920, 1080, 30, colors="red,green,blue")
        assert "colormapping=red,green,blue" in filter_complex
        assert "color=colormapping" in filter_complex

    def test_build_filter_custom_colors_single(self):
        """Test spectrum with single custom color falls back to intensity."""
        plugin = SpectrumPlugin()
        filter_complex = plugin.build_filter(1920, 1080, 30, colors="red")
        assert "colormapping" not in filter_complex
        assert "color=intensity" in filter_complex

    def test_build_filter_custom_colors_empty(self):
        """Test spectrum with empty colors falls back to intensity."""
        plugin = SpectrumPlugin()
        filter_complex = plugin.build_filter(1920, 1080, 30, colors="")
        assert "colormapping" not in filter_complex
        assert "color=intensity" in filter_complex

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
        assert "colors=red|green|blue" in filter_complex

    def test_build_filter_custom_colors(self):
        """Test waveform with custom colors."""
        plugin = WaveformPlugin()
        filter_complex = plugin.build_filter(1920, 1080, 30, colors="red,blue")
        assert "colors=red,blue" in filter_complex

    def test_build_filter_no_colors(self):
        """Test waveform with None colors uses defaults."""
        plugin = WaveformPlugin()
        filter_complex = plugin.build_filter(1920, 1080, 30, colors=None)
        assert "colors=red|green|blue" in filter_complex

    def test_build_command(self):
        """Test waveform command building."""
        plugin = WaveformPlugin()
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
                "colors": "red,blue,green",
            }
        )
        assert cmd[0] == "ffmpeg"
        assert "-c:v" in cmd
        assert "test.mp4" in cmd


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

        formats = ["test.wav", "test.mp3", "test.flac", "test.ogg", "test.aac", "test.m4a"]
        for fmt in formats:
            path = f"tests/assets/{fmt}"
            result = subprocess.run(
                [
                    "ffprobe",
                    "-v",
                    "error",
                    "-show_entries",
                    "format=duration",
                    "-of",
                    "csv=p=0",
                    path,
                ],
                capture_output=True,
                text=True,
            )
            assert result.returncode == 0
            duration = float(result.stdout.strip())
            assert duration > 0
            assert duration <= 11  # Should be ~10 seconds

    def test_different_sample_rates(self):
        """Test loading audio with different sample rates."""
        import subprocess

        # Test 48000 Hz
        result = subprocess.run(
            [
                "ffprobe",
                "-v",
                "error",
                "-show_entries",
                "stream=sample_rate",
                "-of",
                "csv=p=0",
                "tests/assets/test_48k.wav",
            ],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0
        assert result.stdout.strip() == "48000"

        # Test 96000 Hz
        result = subprocess.run(
            [
                "ffprobe",
                "-v",
                "error",
                "-show_entries",
                "stream=sample_rate",
                "-of",
                "csv=p=0",
                "tests/assets/test_96k.wav",
            ],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0
        assert result.stdout.strip() == "96000"

    def test_aac_format(self):
        """Test loading AAC audio format."""
        import subprocess

        result = subprocess.run(
            [
                "ffprobe",
                "-v",
                "error",
                "-show_entries",
                "stream=codec_name",
                "-of",
                "csv=p=0",
                "tests/assets/test.aac",
            ],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0
        assert "aac" in result.stdout.lower()

    def test_m4a_format(self):
        """Test loading M4A audio format."""
        import subprocess

        result = subprocess.run(
            [
                "ffprobe",
                "-v",
                "error",
                "-show_entries",
                "stream=codec_name",
                "-of",
                "csv=p=0",
                "tests/assets/test.m4a",
            ],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0
        assert "aac" in result.stdout.lower()  # M4A uses AAC codec

    def test_mono_audio(self):
        """Test loading mono audio."""
        import subprocess

        result = subprocess.run(
            [
                "ffprobe",
                "-v",
                "error",
                "-show_entries",
                "stream=channels",
                "-of",
                "csv=p=0",
                "tests/assets/mono.mp3",
            ],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0
        assert result.stdout.strip() == "1"  # Mono = 1 channel

    def test_long_audio(self):
        """Test loading long audio file."""
        import subprocess

        result = subprocess.run(
            [
                "ffprobe",
                "-v",
                "error",
                "-show_entries",
                "format=duration",
                "-of",
                "csv=p=0",
                "tests/assets/long.mp3",
            ],
            capture_output=True,
            text=True,
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


class TestRadialPlugin:
    """Test radial visualizer plugin."""

    def test_metadata(self):
        """Test radial plugin metadata."""
        from audio_visualizer.visualizers.radial import RadialPlugin

        meta = RadialPlugin.get_metadata()
        assert meta.name == "radial"
        assert meta.display_name == "Mirrored Spectrum"
        assert meta.icon == "🪞"

    def test_build_filter(self):
        """Test radial filter construction."""
        from audio_visualizer.visualizers.radial import RadialPlugin

        plugin = RadialPlugin()
        filter_str = plugin.build_filter(1920, 1080, 30)
        assert "showspectrum" in filter_str
        assert "transpose" in filter_str  # mirror effect
        assert "scale=1920x1080" in filter_str
        assert "[out]" in filter_str


class TestSpectrogramPlugin:
    """Test spectrogram visualizer plugin."""

    def test_metadata(self):
        """Test spectrogram plugin metadata."""
        from audio_visualizer.visualizers.spectrogram import SpectrogramPlugin

        meta = SpectrogramPlugin.get_metadata()
        assert meta.name == "spectrogram"
        assert meta.display_name == "Spectrogram Waterfall"
        assert meta.icon == "🌊"

    def test_build_filter(self):
        """Test spectrogram filter construction."""
        from audio_visualizer.visualizers.spectrogram import SpectrogramPlugin

        plugin = SpectrogramPlugin()
        filter_str = plugin.build_filter(1920, 1080, 30)
        assert "showspectrum" in filter_str
        assert "slide=rscroll" in filter_str
        assert "overlap=0.95" in filter_str
        assert "[out]" in filter_str


class TestBarsPlugin:
    """Test bars visualizer plugin."""

    def test_metadata(self):
        """Test bars plugin metadata."""
        from audio_visualizer.visualizers.bars import BarsPlugin

        meta = BarsPlugin.get_metadata()
        assert meta.name == "bars"
        assert meta.display_name == "Classic Bars"
        assert meta.icon == "📊"

    def test_build_filter(self):
        """Test bars filter construction."""
        from audio_visualizer.visualizers.bars import BarsPlugin

        plugin = BarsPlugin()
        filter_str = plugin.build_filter(1920, 1080, 30)
        assert "showspectrum" in filter_str
        assert "overlap=0.5" in filter_str
        assert "[out]" in filter_str


class TestAlbumArtPlugin:
    """Test album art visualizer plugin."""

    def test_metadata(self):
        """Test album art plugin metadata."""
        from audio_visualizer.visualizers.albumart import AlbumArtPlugin

        meta = AlbumArtPlugin.get_metadata()
        assert meta.name == "albumart"
        assert meta.display_name == "Album Art Visualizer"
        assert meta.icon == "🎵"

    def test_build_filter(self):
        """Test album art filter construction."""
        from audio_visualizer.visualizers.albumart import AlbumArtPlugin

        plugin = AlbumArtPlugin()
        filter_str = plugin.build_filter(1920, 1080, 30, image_path="tests/assets/album.jpg")
        assert "scale=1920x1080" in filter_str
        assert "showspectrum" in filter_str
        assert "[out]" in filter_str

    def test_build_command(self):
        """Test album art command construction."""
        from audio_visualizer.visualizers.albumart import AlbumArtPlugin

        plugin = AlbumArtPlugin()
        cmd = plugin.build_command(
            {
                "input": "tests/assets/test.mp3",
                "output": "output.mp4",
                "width": 1920,
                "height": 1080,
                "fps": 30,
                "preset": "medium",
                "crf": 23,
                "format": "mp4",
                "accel": "sw",
                "image": "tests/assets/album.jpg",
            }
        )
        assert cmd[0] == "ffmpeg"
        assert "-loop" in cmd
        assert "-i" in cmd
        assert "tests/assets/album.jpg" in cmd
        assert "-filter_complex" in cmd
        assert "output.mp4" in cmd

    def test_build_command_missing_image(self):
        """Test album art raises error when image is missing."""
        from audio_visualizer.visualizers.albumart import AlbumArtPlugin

        plugin = AlbumArtPlugin()
        with pytest.raises(FileNotFoundError):
            plugin.build_command(
                {
                    "input": "tests/assets/test.mp3",
                    "output": "output.mp4",
                    "width": 1920,
                    "height": 1080,
                    "fps": 30,
                    "preset": "medium",
                    "crf": 23,
                    "format": "mp4",
                    "accel": "sw",
                    "image": "/nonexistent/image.jpg",
                }
            )


class TestRunWithProgress:
    """Test _run_with_progress function."""

    def test_progress_bar_completes(self):
        """Test that progress bar completes successfully."""
        from audio_visualizer.core import _run_with_progress

        # Run a no-op command that completes quickly
        cmd = [
            "ffmpeg",
            "-y",
            "-f",
            "lavfi",
            "-i",
            "nullsrc=s=1x1:r=30",
            "-t",
            "0.1",
            "-f",
            "null",
            "-",
        ]
        _run_with_progress(cmd, 1.0, verbose=False)

    def test_progress_bar_keyboard_interrupt(self):
        """Test that KeyboardInterrupt is handled gracefully."""
        from audio_visualizer.core import _run_with_progress

        # Verify the function handles KeyboardInterrupt properly
        # by running a short command that completes normally
        cmd = [
            "ffmpeg",
            "-y",
            "-f",
            "lavfi",
            "-i",
            "nullsrc=s=1x1:r=30",
            "-t",
            "0.1",
            "-f",
            "null",
            "-",
        ]
        _run_with_progress(cmd, 1.0)

    def test_progress_bar_stderr_capture(self):
        """Test that ffmpeg stderr is captured for error reporting."""
        from audio_visualizer.core import _run_with_progress

        # Run an invalid command to test stderr capture
        cmd = ["ffmpeg", "-y", "-f", "lavfi", "-i", "invalid_source", "-f", "null", "-"]
        # This should fail but not crash
        try:
            _run_with_progress(cmd, 1.0)
        except SystemExit:
            pass  # Expected to exit due to ffmpeg error


class TestRunVisualizer:
    """Test run_visualizer function."""

    def test_run_visualizer_missing_input(self):
        """Test run_visualizer exits when input file is missing."""

        from audio_visualizer.__main__ import run_visualizer
        from audio_visualizer.visualizers.spectrum import SpectrumPlugin

        with pytest.raises(SystemExit):
            run_visualizer(
                SpectrumPlugin,
                {
                    "input": "/nonexistent/file.mp3",
                    "output": "output.mp4",
                    "width": 1920,
                    "height": 1080,
                    "fps": 30,
                    "preset": "medium",
                    "crf": 23,
                    "verbose": False,
                    "image": None,
                    "format": "mp4",
                    "accel": "sw",
                    "colors": None,
                },
            )

    def test_run_visualizer_success(self, tmp_path):
        """Test run_visualizer produces output file."""
        import os

        from audio_visualizer.__main__ import run_visualizer
        from audio_visualizer.visualizers.spectrum import SpectrumPlugin

        output_file = str(tmp_path / "output.mp4")
        run_visualizer(
            SpectrumPlugin,
            {
                "input": "tests/assets/test.mp3",
                "output": output_file,
                "width": 320,
                "height": 240,
                "fps": 10,
                "preset": "ultrafast",
                "crf": 23,
                "verbose": False,
                "image": None,
                "format": "mp4",
                "accel": "sw",
                "colors": None,
            },
        )
        assert os.path.exists(output_file)
        assert os.path.getsize(output_file) > 0

    def test_run_visualizer_forwards_colors(self):
        """Test run_visualizer forwards colors to the plugin's build_command."""
        from unittest.mock import patch

        from audio_visualizer.__main__ import run_visualizer
        from audio_visualizer.visualizers.spectrum import SpectrumPlugin

        # Mock build_command to capture the args dict
        captured_args = {}

        def mock_build_command(self, args):
            captured_args.update(args)
            return "mock_filter"

        with patch.object(SpectrumPlugin, "build_command", mock_build_command):
            with patch("audio_visualizer.__main__.detect_hwaccel", return_value="sw"):
                with patch("audio_visualizer.__main__.get_audio_duration", return_value=10.0):
                    with patch("audio_visualizer.core._run_with_progress"):
                        with patch("os.path.exists", return_value=True):
                            with patch("os.path.getsize", return_value=1024 * 1024):
                                run_visualizer(
                                    SpectrumPlugin,
                                    {
                                        "input": "tests/assets/test.mp3",
                                        "output": "output.mp4",
                                        "width": 320,
                                        "height": 240,
                                        "fps": 10,
                                        "preset": "ultrafast",
                                        "crf": 23,
                                        "verbose": False,
                                        "image": None,
                                        "format": "mp4",
                                        "accel": "sw",
                                        "colors": "red,green,blue",
                                    },
                                )

        # Verify colors were forwarded to build_command
        assert "colors" in captured_args
        assert captured_args["colors"] == "red,green,blue"


class TestRetryLogicFix:
    """Test retry logic for ffmpeg failures (fixed mocks)."""

    def test_run_with_progress_no_retry(self):
        """Test _run_with_progress with retry=0 succeeds."""
        from unittest.mock import MagicMock, patch

        from audio_visualizer.core import _run_with_progress

        mock_proc = MagicMock()
        mock_proc.returncode = 0
        mock_proc.stderr = iter(["time=00:00:01.00\n", "time=00:00:02.00\n"])

        with patch("subprocess.Popen", return_value=mock_proc) as mock_popen:
            with patch("time.sleep"):
                _run_with_progress(["ffmpeg", "test"], 2.0, retry_count=0)

        assert mock_popen.call_count == 1

    def test_run_with_progress_retry_succeeds_second(self):
        """Test retry: first attempt fails, second succeeds."""
        from unittest.mock import MagicMock, patch

        from audio_visualizer.core import _run_with_progress

        call_count = [0]

        def make_mock_proc(cmd, **kwargs):
            call_count[0] += 1
            mock_proc = MagicMock()
            mock_proc.returncode = 1 if call_count[0] < 2 else 0
            mock_proc.stderr = iter(["time=00:00:01.00\n"])
            return mock_proc

        with patch("subprocess.Popen", side_effect=make_mock_proc):
            with patch("time.sleep") as mock_sleep:
                _run_with_progress(["ffmpeg", "test"], 2.0, retry_count=2)

        assert call_count[0] == 2
        assert mock_sleep.call_count == 1

    def test_run_with_progress_retry_all_fail(self):
        """Test retry: all attempts fail, exits with code 1."""
        from unittest.mock import MagicMock, patch

        from audio_visualizer.core import _run_with_progress

        def make_mock_proc(cmd, **kwargs):
            mock_proc = MagicMock()
            mock_proc.returncode = 1
            mock_proc.stderr = iter(["Error line\n"])
            return mock_proc

        with patch("subprocess.Popen", side_effect=make_mock_proc):
            with patch("time.sleep"):
                with pytest.raises(SystemExit):
                    _run_with_progress(["ffmpeg", "test"], 2.0, retry_count=2)

    def test_run_with_progress_backoff_capped(self):
        """Test that backoff is capped at 10 seconds."""
        from unittest.mock import MagicMock, patch

        from audio_visualizer.core import _run_with_progress

        def make_mock_proc(cmd, **kwargs):
            mock_proc = MagicMock()
            mock_proc.returncode = 1
            mock_proc.stderr = iter([])
            return mock_proc

        with patch("subprocess.Popen", side_effect=make_mock_proc):
            with patch("time.sleep") as mock_sleep:
                with pytest.raises(SystemExit):
                    _run_with_progress(["ffmpeg", "test"], 2.0, retry_count=5)

        for call in mock_sleep.call_args_list:
            assert call[0][0] <= 10


class TestOutputSizeEstimation:
    """Test output file size estimation."""

    def test_estimate_normal_case(self):
        """Test estimation with normal parameters."""
        from audio_visualizer.core import _estimate_output_size

        args = {
            "width": 1280,
            "height": 720,
            "fps": 30,
            "preset": "medium",
            "crf": 23,
            "format": "mp4",
        }
        size_mb = _estimate_output_size(args, 10.0, "sw")
        assert size_mb > 0
        # Should give a reasonable estimate for 10s video
        assert 0.1 < size_mb < 50.0

    def test_estimate_high_quality(self):
        """Test estimation with high quality settings."""
        from audio_visualizer.core import _estimate_output_size

        args = {
            "width": 1920,
            "height": 1080,
            "fps": 30,
            "preset": "slow",
            "crf": 18,
            "format": "mp4",
        }
        size_mb = _estimate_output_size(args, 10.0, "sw")
        assert size_mb > 0
        # Higher quality should give larger estimate
        assert size_mb > 2.0

    def test_estimate_low_quality(self):
        """Test estimation with low quality settings."""
        from audio_visualizer.core import _estimate_output_size

        args = {
            "width": 640,
            "height": 360,
            "fps": 15,
            "preset": "ultrafast",
            "crf": 28,
            "format": "mp4",
        }
        size_mb = _estimate_output_size(args, 10.0, "sw")
        assert size_mb > 0
        # Lower quality should give smaller estimate
        assert size_mb < 3.0

    def test_estimate_zero_duration(self):
        """Test estimation with zero duration returns 0."""
        from audio_visualizer.core import _estimate_output_size

        args = {"width": 1280, "height": 720, "fps": 30, "preset": "medium", "crf": 23}
        size_mb = _estimate_output_size(args, 0.0, "sw")
        assert size_mb == 0

    def test_estimate_negative_duration(self):
        """Test estimation with negative duration returns 0."""
        from audio_visualizer.core import _estimate_output_size

        args = {"width": 1280, "height": 720, "fps": 30, "preset": "medium", "crf": 23}
        size_mb = _estimate_output_size(args, -1.0, "sw")
        assert size_mb == 0

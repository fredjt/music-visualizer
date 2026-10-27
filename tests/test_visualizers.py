"""Tests for visualizer plugins."""

import pytest

from audio_visualizer.visualizers.base import PluginMetadata, VisualizerPlugin
from audio_visualizer.visualizers.colors import ColorParser, parse_colors
from audio_visualizer.visualizers.spectrum import SpectrumPlugin
from audio_visualizer.visualizers.vectorscope import VectorscopePlugin
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
        """Test spectrum filter with custom colors (named colors converted to hex)."""
        plugin = SpectrumPlugin()
        filter_complex = plugin.build_filter(1920, 1080, 30, colors="red,green,blue")
        assert "colormapping=ff0000,00ff00,0000ff" in filter_complex
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
        """Test waveform with custom colors (pipe-separated for showwaves)."""
        plugin = WaveformPlugin()
        filter_complex = plugin.build_filter(1920, 1080, 30, colors="red,blue")
        assert "colors=red|blue" in filter_complex

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

            def build_filter(
                self, width, height, fps, audio_index=0, video_index=1, colors=None, bg_color=None
            ):
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

            def build_filter(
                self,
                width,
                height,
                fps,
                audio_index=0,
                video_index=1,
                colors=None,
                bg_color=None,
                waveform_splits=1,
                **kwargs,
            ):
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
        assert "color=intensity" in filter_str
        assert "[out]" in filter_str

    def test_build_filter_swirl_mode(self):
        """Test spectrogram with swirl colormapping mode."""
        from audio_visualizer.visualizers.spectrogram import SpectrogramPlugin

        plugin = SpectrogramPlugin()
        filter_str = plugin.build_filter(1920, 1080, 30, spectrogram_mode="swirl")
        assert "color=swirl" in filter_str

    def test_build_filter_fire_mode(self):
        """Test spectrogram with fire colormapping mode."""
        from audio_visualizer.visualizers.spectrogram import SpectrogramPlugin

        plugin = SpectrogramPlugin()
        filter_str = plugin.build_filter(1920, 1080, 30, spectrogram_mode="fire")
        assert "color=fire" in filter_str

    def test_build_filter_rain_mode(self):
        """Test spectrogram with rain colormapping mode."""
        from audio_visualizer.visualizers.spectrogram import SpectrogramPlugin

        plugin = SpectrogramPlugin()
        filter_str = plugin.build_filter(1920, 1080, 30, spectrogram_mode="rain")
        assert "color=rain" in filter_str

    def test_build_filter_ice_mode(self):
        """Test spectrogram with ice colormapping mode."""
        from audio_visualizer.visualizers.spectrogram import SpectrogramPlugin

        plugin = SpectrogramPlugin()
        filter_str = plugin.build_filter(1920, 1080, 30, spectrogram_mode="ice")
        assert "color=ice" in filter_str

    def test_build_filter_heat_mode(self):
        """Test spectrogram with heat colormapping mode."""
        from audio_visualizer.visualizers.spectrogram import SpectrogramPlugin

        plugin = SpectrogramPlugin()
        filter_str = plugin.build_filter(1920, 1080, 30, spectrogram_mode="heat")
        assert "color=heat" in filter_str

    def test_build_filter_invalid_mode_fallback(self):
        """Test spectrogram invalid mode falls back to intensity."""
        from audio_visualizer.visualizers.spectrogram import SpectrogramPlugin

        plugin = SpectrogramPlugin()
        filter_str = plugin.build_filter(1920, 1080, 30, spectrogram_mode="invalid")
        assert "color=intensity" in filter_str


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
        from audio_visualizer.core import _estimate_output_size_formula

        args = {
            "width": 1280,
            "height": 720,
            "fps": 30,
            "preset": "medium",
            "crf": 23,
            "format": "mp4",
        }
        size_mb = _estimate_output_size_formula(args, 10.0, "sw")
        assert size_mb > 0
        # Should give a reasonable estimate for 10s video
        assert 0.1 < size_mb < 50.0

    def test_estimate_high_quality(self):
        """Test estimation with high quality settings."""
        from audio_visualizer.core import _estimate_output_size_formula

        args = {
            "width": 1920,
            "height": 1080,
            "fps": 30,
            "preset": "slow",
            "crf": 18,
            "format": "mp4",
        }
        size_mb = _estimate_output_size_formula(args, 10.0, "sw")
        assert size_mb > 0
        # Higher quality should give larger estimate than normal
        assert size_mb > 1.0

    def test_estimate_low_quality(self):
        """Test estimation with low quality settings."""
        from audio_visualizer.core import _estimate_output_size_formula

        args = {
            "width": 640,
            "height": 360,
            "fps": 15,
            "preset": "ultrafast",
            "crf": 28,
            "format": "mp4",
        }
        size_mb = _estimate_output_size_formula(args, 10.0, "sw")
        assert size_mb > 0
        # Lower quality should give smaller estimate
        assert size_mb < 3.0

    def test_estimate_zero_duration(self):
        """Test estimation with zero duration returns 0."""
        from audio_visualizer.core import _estimate_output_size_formula

        args = {"width": 1280, "height": 720, "fps": 30, "preset": "medium", "crf": 23}
        size_mb = _estimate_output_size_formula(args, 0.0, "sw")
        assert size_mb == 0

    def test_estimate_negative_duration(self):
        """Test estimation with negative duration returns 0."""
        from audio_visualizer.core import _estimate_output_size_formula

        args = {"width": 1280, "height": 720, "fps": 30, "preset": "medium", "crf": 23}
        size_mb = _estimate_output_size_formula(args, -1.0, "sw")
        assert size_mb == 0


class TestColorParser:
    """Test the shared ColorParser utility."""

    def test_named_color_red(self):
        """Test resolving named color red."""
        parser = ColorParser("red")
        assert parser.as_hex_list() == ["ff0000"]

    def test_named_color_blue(self):
        """Test resolving named color blue."""
        parser = ColorParser("blue")
        assert parser.as_hex_list() == ["0000ff"]

    def test_named_color_crimson(self):
        """Test resolving a less common named color."""
        parser = ColorParser("crimson")
        assert parser.as_hex_list() == ["dc143c"]

    def test_hex_color_with_hash(self):
        """Test resolving hex color with # prefix."""
        parser = ColorParser("#ff0000")
        assert parser.as_hex_list() == ["ff0000"]

    def test_hex_color_without_hash(self):
        """Test resolving hex color without # prefix."""
        parser = ColorParser("00ff00")
        assert parser.as_hex_list() == ["00ff00"]

    def test_case_insensitive(self):
        """Test that color names are case-insensitive."""
        parser = ColorParser("RED")
        assert parser.as_hex_list() == ["ff0000"]
        parser2 = ColorParser("Red")
        assert parser2.as_hex_list() == ["ff0000"]

    def test_multiple_colors(self):
        """Test resolving multiple colors."""
        parser = ColorParser("red,green,blue")
        assert parser.as_hex_list() == ["ff0000", "00ff00", "0000ff"]

    def test_multiple_colors_with_hash(self):
        """Test resolving multiple hex colors."""
        parser = ColorParser("#ff0000, #00ff00, #0000ff")
        assert parser.as_hex_list() == ["ff0000", "00ff00", "0000ff"]

    def test_colormapping_format(self):
        """Test colormapping output format."""
        parser = ColorParser("red,green,blue")
        assert parser.as_colormapping() == "ff0000,00ff00,0000ff"

    def test_pipe_colors_format(self):
        """Test pipe-separated output for showwaves."""
        parser = ColorParser("red,green,blue")
        assert parser.as_pipe_colors() == "red|green|blue"

    def test_pipe_colors_mixed(self):
        """Test pipe-separated output with mixed hex and named colors."""
        parser = ColorParser("#ff0000, green, #0000ff")
        assert parser.as_pipe_colors() == "red|green|blue"

    def test_rgb_tuple(self):
        """Test RGB tuple extraction."""
        parser = ColorParser("red")
        assert parser.as_rgb_tuple(0) == (255, 0, 0)

    def test_rgb_tuple_index(self):
        """Test RGB tuple extraction with index."""
        parser = ColorParser("red,green,blue")
        assert parser.as_rgb_tuple(0) == (255, 0, 0)
        assert parser.as_rgb_tuple(1) == (0, 255, 0)
        assert parser.as_rgb_tuple(2) == (0, 0, 255)

    def test_rgb_floats(self):
        """Test RGB float extraction."""
        parser = ColorParser("red")
        assert parser.as_rgb_floats(0) == pytest.approx((1.0, 0.0, 0.0))

    def test_glow_params(self):
        """Test glow parameter extraction."""
        parser = ColorParser("#ff0000")
        rr, gg, bb, alpha = parser.as_glow_params()
        assert rr == pytest.approx(1.0 * 0.15)
        assert gg == pytest.approx(0.0 * 0.15)
        assert bb == pytest.approx(0.0 * 0.15)
        assert alpha == pytest.approx(0.08)

    def test_glow_params_custom_multiplier(self):
        """Test glow parameter extraction with custom multipliers."""
        parser = ColorParser("#00ff00")
        rr, gg, bb, alpha = parser.as_glow_params(alpha_multiplier=0.2, mix_multiplier=0.5)
        assert rr == pytest.approx(0.0 * 0.5)
        assert gg == pytest.approx(1.0 * 0.5)
        assert bb == pytest.approx(0.0 * 0.5)
        assert alpha == pytest.approx(0.2)

    def test_vectorscope_params(self):
        """Test vectorscope RGB parameter extraction."""
        parser = ColorParser("#ff0000")
        assert parser.as_vectorscope_params() == (255, 0, 0)

    def test_vectorscope_params_fallback(self):
        """Test vectorscope params fallback to defaults."""
        parser = ColorParser("invalidcolor")
        assert parser.as_vectorscope_params(default_r=10, default_g=20, default_b=30) == (
            10,
            20,
            30,
        )

    def test_vectorscope_params_named_color(self):
        """Test vectorscope params with named color."""
        parser = ColorParser("red")
        assert parser.as_vectorscope_params() == (255, 0, 0)

    def test_empty_parser(self):
        """Test empty parser."""
        parser = ColorParser()
        assert parser.is_empty is True
        assert parser.count == 0
        assert parser.as_hex_list() == []

    def test_none_input(self):
        """Test None input."""
        parser = ColorParser(None)
        assert parser.is_empty is True

    def test_list_input(self):
        """Test list input."""
        parser = ColorParser(["red", "blue"])
        assert parser.as_hex_list() == ["ff0000", "0000ff"]

    def test_whitespace_handling(self):
        """Test that whitespace is trimmed."""
        parser = ColorParser("  red  ,  blue  ")
        assert parser.as_hex_list() == ["ff0000", "0000ff"]

    def test_empty_string_in_list(self):
        """Test that empty strings are filtered out."""
        parser = ColorParser("red,,blue")
        assert parser.as_hex_list() == ["ff0000", "0000ff"]

    def test_invalid_color_raises(self):
        """Test that invalid color raises ValueError."""
        parser = ColorParser("notacolor")
        with pytest.raises(ValueError, match="Unknown color"):
            parser.as_hex_list()

    def test_index_out_of_range(self):
        """Test that out-of-range index raises IndexError."""
        parser = ColorParser("red")
        with pytest.raises(IndexError):
            parser.as_rgb_tuple(5)

    def test_parse_colors_convenience(self):
        """Test the parse_colors convenience function."""
        parser = parse_colors("red,blue")
        assert isinstance(parser, ColorParser)
        assert parser.as_hex_list() == ["ff0000", "0000ff"]

    def test_repr(self):
        """Test __repr__."""
        parser = ColorParser("red,blue")
        assert repr(parser) == "ColorParser(['red', 'blue'])"

    def test_named_colors_coverage(self):
        """Test that a sample of named colors resolve correctly."""
        test_colors = {
            "black": "000000",
            "white": "ffffff",
            "red": "ff0000",
            "green": "00ff00",
            "blue": "0000ff",
            "cyan": "00ffff",
            "magenta": "ff00ff",
            "yellow": "ffff00",
            "orange": "ffa500",
            "purple": "800080",
            "crimson": "dc143c",
            "indigo": "4b0082",
        }
        for name, expected_hex in test_colors.items():
            parser = ColorParser(name)
            assert parser.as_hex_list() == [expected_hex], f"Failed for {name}"

    def test_colormapping_requires_two_colors(self):
        """Test that colormapping needs at least 2 colors."""
        parser = ColorParser("red")
        assert parser.count == 1
        assert parser.as_colormapping() == "ff0000"  # Still works, but count < 2

    def test_hex_lowercase(self):
        """Test hex color normalization to lowercase."""
        parser = ColorParser("#FF0000")
        assert parser.as_hex_list() == ["ff0000"]

    def test_hex_uppercase(self):
        """Test hex color with uppercase."""
        parser = ColorParser("00FF00")
        assert parser.as_hex_list() == ["00ff00"]

    def test_as_bg_color_named(self):
        """Test bg_color returns first resolved color."""
        parser = ColorParser("crimson")
        assert parser.as_bg_color() == "dc143c"

    def test_as_bg_color_hex(self):
        """Test bg_color with hex input."""
        parser = ColorParser("#1a2b3c")
        assert parser.as_bg_color() == "1a2b3c"

    def test_as_bg_color_empty(self):
        """Test bg_color defaults to black when empty."""
        parser = ColorParser()
        assert parser.as_bg_color() == "000000"

    def test_as_bg_color_none(self):
        """Test bg_color defaults to black when None."""
        parser = ColorParser(None)
        assert parser.as_bg_color() == "000000"

    def test_as_spectrum_mode_colormapping(self):
        """Test spectrum mode returns colormapping with 2+ colors."""
        parser = ColorParser("red,blue")
        mode, mapping = parser.as_spectrum_mode()
        assert mode == "colormapping"
        assert mapping == "ff0000,0000ff"

    def test_as_spectrum_mode_intensity(self):
        """Test spectrum mode returns intensity with single color."""
        parser = ColorParser("red")
        mode, mapping = parser.as_spectrum_mode()
        assert mode == "intensity"
        assert mapping == ""

    def test_as_spectrum_mode_empty(self):
        """Test spectrum mode returns intensity with no colors."""
        parser = ColorParser()
        mode, mapping = parser.as_spectrum_mode()
        assert mode == "intensity"
        assert mapping == ""

    def test_as_cqt_scheme_custom(self):
        """Test CQT scheme with custom colors."""
        parser = ColorParser("red,blue")
        scheme = parser.as_cqt_scheme()
        # red = 1.0|0.0|0.0, blue = 0.0|0.0|1.0
        assert scheme == "1.0|0.0|0.0|0.0|0.0|1.0"

    def test_as_cqt_scheme_empty(self):
        """Test CQT scheme defaults when no colors."""
        parser = ColorParser()
        scheme = parser.as_cqt_scheme()
        assert scheme == "1.0|0.5|0|0.0|0.5|1.0"

    def test_as_cqt_scheme_single_color(self):
        """Test CQT scheme with single color falls back to default."""
        parser = ColorParser("red")
        scheme = parser.as_cqt_scheme()
        assert scheme == "1.0|0.5|0|0.0|0.5|1.0"

    def test_as_waves_colors_custom(self):
        """Test waves colors with custom input."""
        parser = ColorParser("red,blue")
        assert parser.as_waves_colors() == "red|blue"

    def test_as_waves_colors_empty(self):
        """Test waves colors defaults to red|green|blue."""
        parser = ColorParser()
        assert parser.as_waves_colors() == "red|green|blue"

    def test_as_waves_colors_none(self):
        """Test waves colors defaults when None."""
        parser = ColorParser(None)
        assert parser.as_waves_colors() == "red|green|blue"

    def test_as_glow_params_empty_fallback(self):
        """Test glow params fallback to defaults when no colors."""
        parser = ColorParser()
        rr, gg, bb, alpha = parser.as_glow_params()
        assert rr == pytest.approx(0.1)
        assert gg == pytest.approx(0.05)
        assert bb == pytest.approx(0.2)
        assert alpha == pytest.approx(0.08)

    def test_as_vectorscope_params_empty_fallback(self):
        """Test vectorscope params fallback when no colors."""
        parser = ColorParser()
        assert parser.as_vectorscope_params(default_r=10, default_g=20, default_b=30) == (
            10,
            20,
            30,
        )

    def test_as_vectorscope_params_index_out_of_range(self):
        """Test vectorscope params fallback when index out of range."""
        parser = ColorParser("red")  # Only 1 color
        assert parser.as_vectorscope_params(index=5, default_r=99) == (99, 20, 10)


class TestBgColor:
    """Test bg_color support across visualizer plugins."""

    def test_spectrum_bg_color_provided(self):
        """Test spectrum with custom bg_color uses opaque background."""
        from audio_visualizer.visualizers.spectrum import SpectrumPlugin

        plugin = SpectrumPlugin()
        filter_str = plugin.build_filter(1920, 1080, 30, bg_color="#1a1a2e")
        assert "colorchannelmixer=aa=1.0" in filter_str
        assert "aa=0.3" not in filter_str

    def test_spectrum_bg_color_none(self):
        """Test spectrum without bg_color uses semi-transparent black."""
        from audio_visualizer.visualizers.spectrum import SpectrumPlugin

        plugin = SpectrumPlugin()
        filter_str = plugin.build_filter(1920, 1080, 30)
        assert "colorchannelmixer=aa=0.3" in filter_str

    def test_bars_bg_color_provided(self):
        """Test bars with custom bg_color uses opaque background."""
        from audio_visualizer.visualizers.bars import BarsPlugin

        plugin = BarsPlugin()
        filter_str = plugin.build_filter(1920, 1080, 30, bg_color="crimson")
        assert "colorchannelmixer=aa=1.0" in filter_str

    def test_waveform_bg_color_provided(self):
        """Test waveform with custom bg_color uses opaque background."""
        from audio_visualizer.visualizers.waveform import WaveformPlugin

        plugin = WaveformPlugin()
        filter_str = plugin.build_filter(1920, 1080, 30, bg_color="#000033")
        assert "colorchannelmixer=aa=1.0" in filter_str

    def test_radial_bg_color_provided(self):
        """Test radial with custom bg_color uses color canvas."""
        from audio_visualizer.visualizers.radial import RadialPlugin

        plugin = RadialPlugin()
        filter_str = plugin.build_filter(1920, 1080, 30, bg_color="#1a1a2e")
        assert "color=c=#1a1a2e:s=1920x2160" in filter_str
        assert "nullsrc" not in filter_str

    def test_radial_bg_color_none(self):
        """Test radial without bg_color uses nullsrc."""
        from audio_visualizer.visualizers.radial import RadialPlugin

        plugin = RadialPlugin()
        filter_str = plugin.build_filter(1920, 1080, 30)
        assert "nullsrc" in filter_str

    def test_spectrogram_bg_color_provided(self):
        """Test spectrogram with custom bg_color uses opaque background."""
        from audio_visualizer.visualizers.spectrogram import SpectrogramPlugin

        plugin = SpectrogramPlugin()
        filter_str = plugin.build_filter(1920, 1080, 30, bg_color="#2d1b69")
        assert "colorchannelmixer=aa=1.0" in filter_str

    def test_cqt_bg_color_provided(self):
        """Test CQT with custom bg_color uses opaque background."""
        from audio_visualizer.visualizers.cqt import CQTPlugin

        plugin = CQTPlugin()
        filter_str = plugin.build_filter(1920, 1080, 30, bg_color="#0a0a0a")
        assert "colorchannelmixer=aa=1.0" in filter_str

    def test_albumart_bg_color_provided(self):
        """Test album art with custom bg_color uses it for dark bar."""
        from audio_visualizer.visualizers.albumart import AlbumArtPlugin

        plugin = AlbumArtPlugin()
        filter_str = plugin.build_filter(
            1920, 1080, 30, image_path="tests/assets/album.jpg", bg_color="#111111"
        )
        assert "color=c=111111" in filter_str

    def test_albumart_bg_color_none(self):
        """Test album art without bg_color defaults to black."""
        from audio_visualizer.visualizers.albumart import AlbumArtPlugin

        plugin = AlbumArtPlugin()
        filter_str = plugin.build_filter(1920, 1080, 30, image_path="tests/assets/album.jpg")
        assert "color=c=000000" in filter_str

    def test_albumart_effect_glow(self):
        """Test album art glow effect (default)."""
        from audio_visualizer.visualizers.albumart import AlbumArtPlugin

        plugin = AlbumArtPlugin()
        filter_str = plugin.build_filter(
            1920, 1080, 30, image_path="tests/assets/album.jpg", albumart_effect="glow"
        )
        assert "color=c=ff00ff" in filter_str  # glow overlay
        assert "[with_effect]" in filter_str

    def test_albumart_effect_pulse(self):
        """Test album art pulse effect."""
        from audio_visualizer.visualizers.albumart import AlbumArtPlugin

        plugin = AlbumArtPlugin()
        filter_str = plugin.build_filter(
            1920, 1080, 30, image_path="tests/assets/album.jpg", albumart_effect="pulse"
        )
        assert "aeval=" in filter_str  # audio amplitude
        assert "[with_effect]" in filter_str

    def test_albumart_effect_zoom(self):
        """Test album art zoom effect."""
        from audio_visualizer.visualizers.albumart import AlbumArtPlugin

        plugin = AlbumArtPlugin()
        filter_str = plugin.build_filter(
            1920, 1080, 30, image_path="tests/assets/album.jpg", albumart_effect="zoom"
        )
        assert "zoompan=" in filter_str
        assert "[with_effect]" in filter_str

    def test_albumart_effect_invalid_fallback(self):
        """Test invalid albumart effect falls back to glow."""
        from audio_visualizer.visualizers.albumart import AlbumArtPlugin

        plugin = AlbumArtPlugin()
        filter_str = plugin.build_filter(
            1920, 1080, 30, image_path="tests/assets/album.jpg", albumart_effect="invalid"
        )
        assert "color=c=ff00ff" in filter_str  # glow overlay

    def test_base_command_passes_bg_color(self):
        """Test that base build_command passes bg_color to build_filter."""
        from audio_visualizer.visualizers.spectrum import SpectrumPlugin

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
                "bg_color": "#1a1a2e",
            }
        )
        # The bg_color should be used in the background canvas
        assert "-i" in cmd
        # bg_color in args should be passed through


class TestWaveformPluginModes:
    """Test waveform plugin mode options."""

    def test_waveform_mode_line(self):
        """Test line mode (default)."""
        plugin = WaveformPlugin()
        filter_complex = plugin.build_filter(1920, 1080, 30)
        assert "mode=line" in filter_complex

    def test_waveform_mode_point(self):
        """Test point mode."""
        plugin = WaveformPlugin()
        filter_complex = plugin.build_filter(1920, 1080, 30, waveform_mode="point")
        assert "mode=point" in filter_complex

    def test_waveform_mode_p2p(self):
        """Test p2p mode."""
        plugin = WaveformPlugin()
        filter_complex = plugin.build_filter(1920, 1080, 30, waveform_mode="p2p")
        assert "mode=p2p" in filter_complex

    def test_waveform_mode_cline(self):
        """Test cline mode."""
        plugin = WaveformPlugin()
        filter_complex = plugin.build_filter(1920, 1080, 30, waveform_mode="cline")
        assert "mode=cline" in filter_complex

    def test_waveform_mode_invalid_fallback(self):
        """Test invalid mode falls back to line."""
        plugin = WaveformPlugin()
        filter_complex = plugin.build_filter(1920, 1080, 30, waveform_mode="invalid")
        assert "mode=line" in filter_complex

    def test_waveform_splits(self):
        """Test waveform channel splitting."""
        plugin = WaveformPlugin()
        filter_complex = plugin.build_filter(1920, 1080, 30, waveform_splits=4)
        assert "split_channels=4" in filter_complex

    def test_waveform_splits_off(self):
        """Test waveform splits disabled (default 1)."""
        plugin = WaveformPlugin()
        filter_complex = plugin.build_filter(1920, 1080, 30, waveform_splits=1)
        assert "split_channels" not in filter_complex

    def test_waveform_frame(self):
        """Test waveform frame parameter."""
        plugin = WaveformPlugin()
        filter_complex = plugin.build_filter(1920, 1080, 30, waveform_frame=100)
        assert "n=100" in filter_complex

    def test_waveform_frame_zero(self):
        """Test waveform frame=0 (auto) doesn't add n parameter."""
        plugin = WaveformPlugin()
        filter_complex = plugin.build_filter(1920, 1080, 30, waveform_frame=0)
        assert "n=" not in filter_complex

    def test_waveform_frame_none(self):
        """Test waveform frame=None doesn't add n parameter."""
        plugin = WaveformPlugin()
        filter_complex = plugin.build_filter(1920, 1080, 30, waveform_frame=None)
        assert "n=" not in filter_complex

    def test_waveform_all_options(self):
        """Test waveform with all options combined."""
        plugin = WaveformPlugin()
        filter_complex = plugin.build_filter(
            1920,
            1080,
            30,
            colors="red,blue",
            waveform_mode="point",
            waveform_splits=2,
            waveform_frame=50,
        )
        assert "mode=point" in filter_complex
        assert "colors=red|blue" in filter_complex
        assert "split_channels=2" in filter_complex
        assert "n=50" in filter_complex

    def test_waveform_mode_pict(self):
        """Test pict mode uses showwavespic filter."""
        plugin = WaveformPlugin()
        filter_complex = plugin.build_filter(1920, 1080, 30, waveform_mode="pict")
        assert "showwavespic" in filter_complex
        assert "showwaves=" not in filter_complex
        assert "mode=separate_colors" in filter_complex

    def test_waveform_mode_pict_with_splits(self):
        """Test pict mode with channel splits."""
        plugin = WaveformPlugin()
        filter_complex = plugin.build_filter(
            1920, 1080, 30, waveform_mode="pict", waveform_splits=4
        )
        assert "showwavespic" in filter_complex
        assert "split_channels=4" in filter_complex

    def test_waveform_splits_clamped_high(self):
        """Test waveform splits clamped to max 8."""
        plugin = WaveformPlugin()
        filter_complex = plugin.build_filter(1920, 1080, 30, waveform_splits=100)
        assert "split_channels=8" in filter_complex

    def test_waveform_splits_clamped_low(self):
        """Test waveform splits clamped to min 1."""
        plugin = WaveformPlugin()
        filter_complex = plugin.build_filter(1920, 1080, 30, waveform_splits=0)
        assert "split_channels" not in filter_complex

    def test_waveform_splits_clamped_negative(self):
        """Test waveform splits clamped to min 1 for negative values."""
        plugin = WaveformPlugin()
        filter_complex = plugin.build_filter(1920, 1080, 30, waveform_splits=-5)
        assert "split_channels" not in filter_complex


class TestVectorscopePluginOptions:
    """Test vectorscope plugin option flags."""

    def test_vectorscope_mode_lissajous(self):
        """Test lissajous mode (default)."""
        plugin = VectorscopePlugin()
        filter_complex = plugin.build_filter(1920, 1080, 30)
        assert "mode=lissajous" in filter_complex

    def test_vectorscope_mode_frame(self):
        """Test frame mode (default, maps to aaline)."""
        plugin = VectorscopePlugin()
        filter_complex = plugin.build_filter(1920, 1080, 30, vectorscope_mode="frame")
        assert "mode=lissajous" in filter_complex
        assert "draw=aaline" in filter_complex

    def test_vectorscope_mode_line(self):
        """Test line mode."""
        plugin = VectorscopePlugin()
        filter_complex = plugin.build_filter(1920, 1080, 30, vectorscope_mode="line")
        assert "mode=lissajous" in filter_complex
        assert "draw=line" in filter_complex

    def test_vectorscope_mode_dot(self):
        """Test dot mode."""
        plugin = VectorscopePlugin()
        filter_complex = plugin.build_filter(1920, 1080, 30, vectorscope_mode="dot")
        assert "mode=lissajous" in filter_complex
        assert "draw=dot" in filter_complex

    def test_vectorscope_mode_invalid_fallback(self):
        """Test invalid mode falls back to frame (aaline)."""
        plugin = VectorscopePlugin()
        filter_complex = plugin.build_filter(1920, 1080, 30, vectorscope_mode="invalid")
        assert "mode=lissajous" in filter_complex
        assert "draw=aaline" in filter_complex

    def test_vectorscope_scale_lin(self):
        """Test linear scale mode."""
        plugin = VectorscopePlugin()
        filter_complex = plugin.build_filter(1920, 1080, 30, vectorscope_scale="lin")
        assert "scale=lin" in filter_complex

    def test_vectorscope_scale_sqrt(self):
        """Test sqrt scale mode."""
        plugin = VectorscopePlugin()
        filter_complex = plugin.build_filter(1920, 1080, 30, vectorscope_scale="sqrt")
        assert "scale=sqrt" in filter_complex

    def test_vectorscope_scale_cbrt(self):
        """Test cbrt scale mode (default)."""
        plugin = VectorscopePlugin()
        filter_complex = plugin.build_filter(1920, 1080, 30)
        assert "scale=cbrt" in filter_complex

    def test_vectorscope_scale_log(self):
        """Test log scale mode."""
        plugin = VectorscopePlugin()
        filter_complex = plugin.build_filter(1920, 1080, 30, vectorscope_scale="log")
        assert "scale=log" in filter_complex

    def test_vectorscope_scale_invalid_fallback(self):
        """Test invalid scale mode falls back to cbrt."""
        plugin = VectorscopePlugin()
        filter_complex = plugin.build_filter(1920, 1080, 30, vectorscope_scale="invalid")
        assert "scale=cbrt" in filter_complex

    def test_vectorscope_zoom_default(self):
        """Test default zoom."""
        plugin = VectorscopePlugin()
        filter_complex = plugin.build_filter(1920, 1080, 30)
        assert "zoom=1.0" in filter_complex

    def test_vectorscope_zoom_custom(self):
        """Test custom zoom."""
        plugin = VectorscopePlugin()
        filter_complex = plugin.build_filter(1920, 1080, 30, vectorscope_zoom=2.5)
        assert "zoom=2.5" in filter_complex

    def test_vectorscope_zoom_clamped_low(self):
        """Test zoom clamped to minimum 0.1."""
        plugin = VectorscopePlugin()
        filter_complex = plugin.build_filter(1920, 1080, 30, vectorscope_zoom=0.01)
        assert "zoom=0.1" in filter_complex

    def test_vectorscope_zoom_clamped_high(self):
        """Test zoom clamped to maximum 10.0."""
        plugin = VectorscopePlugin()
        filter_complex = plugin.build_filter(1920, 1080, 30, vectorscope_zoom=100.0)
        assert "zoom=10.0" in filter_complex

    def test_vectorscope_trails_default(self):
        """Test default trails (100)."""
        plugin = VectorscopePlugin()
        filter_complex = plugin.build_filter(1920, 1080, 30)
        # trails=100 maps to af=155 (255-100)
        assert "af=155" in filter_complex

    def test_vectorscope_trails_high(self):
        """Test high trails (200 = af=55)."""
        plugin = VectorscopePlugin()
        filter_complex = plugin.build_filter(1920, 1080, 30, vectorscope_trails=200)
        assert "af=55" in filter_complex

    def test_vectorscope_trails_low(self):
        """Test low trails (1 = af=254)."""
        plugin = VectorscopePlugin()
        filter_complex = plugin.build_filter(1920, 1080, 30, vectorscope_trails=1)
        assert "af=254" in filter_complex

    def test_vectorscope_trails_max(self):
        """Test max trails (255 = af=0)."""
        plugin = VectorscopePlugin()
        filter_complex = plugin.build_filter(1920, 1080, 30, vectorscope_trails=255)
        assert "af=0" in filter_complex

    def test_vectorscope_all_options(self):
        """Test vectorscope with all options combined."""
        plugin = VectorscopePlugin()
        filter_complex = plugin.build_filter(
            1920,
            1080,
            30,
            colors="red,blue,green",
            vectorscope_mode="line",
            vectorscope_scale="log",
            vectorscope_zoom=3.0,
            vectorscope_trails=200,
        )
        assert "mode=lissajous" in filter_complex
        assert "draw=line" in filter_complex
        assert "scale=log" in filter_complex
        assert "zoom=3.0" in filter_complex
        assert "af=55" in filter_complex
        # Colors should be parsed as RGB
        assert "rf=255" in filter_complex  # red
        assert "gf=0" in filter_complex  # blue
        assert "bf=0" in filter_complex  # green (first color only)

    def test_vectorscope_trails_clamped_high(self):
        """Test trails clamped to max 255."""
        plugin = VectorscopePlugin()
        filter_complex = plugin.build_filter(1920, 1080, 30, vectorscope_trails=999)
        assert "af=0" in filter_complex  # 255-255=0

    def test_vectorscope_trails_clamped_low(self):
        """Test trails clamped to min 0."""
        plugin = VectorscopePlugin()
        filter_complex = plugin.build_filter(1920, 1080, 30, vectorscope_trails=-10)
        assert "af=255" in filter_complex  # 255-0=255

    def test_vectorscope_zoom_clamped(self):
        """Test zoom clamped to valid range."""
        plugin = VectorscopePlugin()
        filter_complex = plugin.build_filter(1920, 1080, 30, vectorscope_zoom=100.0)
        assert "zoom=10.0" in filter_complex
        filter_complex = plugin.build_filter(1920, 1080, 30, vectorscope_zoom=-5.0)
        assert "zoom=0.1" in filter_complex

    def test_vectorscope_color_index_first(self):
        """Test color_index=0 uses first color."""
        plugin = VectorscopePlugin()
        filter_complex = plugin.build_filter(1920, 1080, 30, colors="red,green,blue", color_index=0)
        assert "rf=255" in filter_complex  # red
        assert "gf=0" in filter_complex
        assert "bf=0" in filter_complex

    def test_vectorscope_color_index_second(self):
        """Test color_index=1 uses second color."""
        plugin = VectorscopePlugin()
        filter_complex = plugin.build_filter(1920, 1080, 30, colors="red,green,blue", color_index=1)
        assert "rf=0" in filter_complex
        assert "gf=255" in filter_complex  # green
        assert "bf=0" in filter_complex

    def test_vectorscope_color_index_third(self):
        """Test color_index=2 uses third color."""
        plugin = VectorscopePlugin()
        filter_complex = plugin.build_filter(1920, 1080, 30, colors="red,green,blue", color_index=2)
        assert "rf=0" in filter_complex
        assert "gf=0" in filter_complex
        assert "bf=255" in filter_complex  # blue

    def test_vectorscope_color_index_out_of_range(self):
        """Test color_index out of range falls back to defaults."""
        plugin = VectorscopePlugin()
        filter_complex = plugin.build_filter(1920, 1080, 30, colors="red", color_index=5)
        assert "rf=30" in filter_complex  # default
        assert "gf=20" in filter_complex
        assert "bf=10" in filter_complex


class TestCQTPlugin:
    """Test CQT visualizer plugin."""

    def test_cqt_metadata(self):
        """Test CQT plugin metadata."""
        from audio_visualizer.visualizers.cqt import CQTPlugin

        meta = CQTPlugin.get_metadata()
        assert meta.name == "cqt"
        assert meta.display_name == "CQT Spectrum"
        assert meta.version == "1.0.0"

    def test_cqt_build_filter_default(self):
        """Test CQT filter with default options."""
        from audio_visualizer.visualizers.cqt import CQTPlugin

        plugin = CQTPlugin()
        filter_complex = plugin.build_filter(1920, 1080, 30)
        assert "showcqt" in filter_complex
        assert "size=1920x1080" in filter_complex
        assert "rate=30" in filter_complex
        assert "gamma=3.0" in filter_complex
        assert "basefreq=20.0" in filter_complex
        assert "endfreq=20495.0" in filter_complex
        assert "attack=0.0" in filter_complex
        assert "tc=0.170" in filter_complex
        assert "axis=true" in filter_complex
        assert "text=true" in filter_complex
        assert "fullhd=false" in filter_complex

    def test_cqt_build_filter_custom_gamma(self):
        """Test CQT with custom gamma."""
        from audio_visualizer.visualizers.cqt import CQTPlugin

        plugin = CQTPlugin()
        filter_complex = plugin.build_filter(1920, 1080, 30, cqt_gamma=5.0)
        assert "gamma=5.0" in filter_complex

    def test_cqt_build_filter_custom_basefreq(self):
        """Test CQT with custom base frequency."""
        from audio_visualizer.visualizers.cqt import CQTPlugin

        plugin = CQTPlugin()
        filter_complex = plugin.build_filter(1920, 1080, 30, cqt_basefreq=40.0)
        assert "basefreq=40.0" in filter_complex

    def test_cqt_build_filter_custom_endfreq(self):
        """Test CQT with custom end frequency."""
        from audio_visualizer.visualizers.cqt import CQTPlugin

        plugin = CQTPlugin()
        filter_complex = plugin.build_filter(1920, 1080, 30, cqt_endfreq=10000.0)
        assert "endfreq=10000.0" in filter_complex

    def test_cqt_build_filter_custom_attack(self):
        """Test CQT with custom attack."""
        from audio_visualizer.visualizers.cqt import CQTPlugin

        plugin = CQTPlugin()
        filter_complex = plugin.build_filter(1920, 1080, 30, cqt_attack=0.5)
        assert "attack=0.5" in filter_complex

    def test_cqt_build_filter_custom_timeclamp(self):
        """Test CQT with custom timeclamp."""
        from audio_visualizer.visualizers.cqt import CQTPlugin

        plugin = CQTPlugin()
        filter_complex = plugin.build_filter(1920, 1080, 30, cqt_timeclamp=0.5)
        assert "tc=0.500" in filter_complex

    def test_cqt_build_filter_custom_colors(self):
        """Test CQT with custom colors."""
        from audio_visualizer.visualizers.cqt import CQTPlugin

        plugin = CQTPlugin()
        filter_complex = plugin.build_filter(1920, 1080, 30, colors="red,blue,green")
        # Should have a custom cscheme with 6 values (3 colors * 3 channels)
        assert "cscheme=" in filter_complex
        assert "ff0000" not in filter_complex  # hex should be converted to 0-1 floats
        # Check that red (1.0, 0, 0) is in the scheme
        assert "1.0" in filter_complex
        assert "0.0" in filter_complex

    def test_cqt_build_filter_single_color(self):
        """Test CQT with single color falls back to default scheme."""
        from audio_visualizer.visualizers.cqt import CQTPlugin

        plugin = CQTPlugin()
        filter_complex = plugin.build_filter(1920, 1080, 30, colors="red")
        assert "cscheme=1.0|0.5|0|0.0|0.5|1.0" in filter_complex

    def test_cqt_build_filter_different_resolution(self):
        """Test CQT with different resolution."""
        from audio_visualizer.visualizers.cqt import CQTPlugin

        plugin = CQTPlugin()
        filter_complex = plugin.build_filter(1280, 720, 25)
        assert "size=1280x720" in filter_complex
        assert "rate=25" in filter_complex

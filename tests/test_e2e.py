"""End-to-end integration tests for audio visualizer.

These tests run the actual CLI with different arguments and verify
that output files are created correctly with different plugins,
resolutions, formats, and options.
"""

import json
import os
import subprocess

import pytest

# Test audio files
TEST_AUDIO = os.path.join(os.path.dirname(__file__), "assets", "test.mp3")
TEST_STEREO = os.path.join(os.path.dirname(__file__), "assets", "test.wav")
TEST_MONO = os.path.join(os.path.dirname(__file__), "assets", "mono.mp3")
TEST_IMAGE = os.path.join(os.path.dirname(__file__), "assets", "album.jpg")


def _has_vpx_encoder() -> bool:
    """True if this ffmpeg build provides the libvpx-vp9 encoder (WebM)."""
    try:
        result = subprocess.run(
            ["ffmpeg", "-hide_banner", "-encoders"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        return "libvpx-vp9" in result.stdout
    except (OSError, subprocess.TimeoutExpired):
        return False


@pytest.mark.e2e
class TestE2ESpectrum:
    """End-to-end tests for spectrum visualizer."""

    def test_spectrum_default(self, tmp_path):
        """Test spectrum visualizer with default args."""
        from unittest.mock import patch

        from audio_visualizer.__main__ import main

        output = str(tmp_path / "output.mp4")
        with patch(
            "sys.argv", ["audio-visualizer", TEST_AUDIO, "-o", output, "--accel", "disabled"]
        ):
            main()
        assert os.path.exists(output)
        assert os.path.getsize(output) > 0

    def test_spectrum_1080p(self, tmp_path):
        """Test spectrum at 1920x1080 resolution."""
        from unittest.mock import patch

        from audio_visualizer.__main__ import main

        output = str(tmp_path / "output_1080p.mp4")
        with patch(
            "sys.argv",
            [
                "audio-visualizer",
                TEST_AUDIO,
                "-o",
                output,
                "-r",
                "1920x1080",
                "--accel",
                "disabled",
            ],
        ):
            main()
        assert os.path.exists(output)
        assert os.path.getsize(output) > 0

    def test_spectrum_colors(self, tmp_path):
        """Test spectrum with custom colors."""
        from unittest.mock import patch

        from audio_visualizer.__main__ import main

        output = str(tmp_path / "output_colors.mp4")
        with patch(
            "sys.argv",
            [
                "audio-visualizer",
                TEST_AUDIO,
                "-o",
                output,
                "--colors",
                "red,blue,green",
                "--accel",
                "disabled",
            ],
        ):
            main()
        assert os.path.exists(output)
        assert os.path.getsize(output) > 0

    def test_spectrum_mode_rainbow(self, tmp_path):
        """Test spectrum with rainbow color mode."""
        from unittest.mock import patch

        from audio_visualizer.__main__ import main

        output = str(tmp_path / "output_rainbow.mp4")
        with patch(
            "sys.argv",
            [
                "audio-visualizer",
                TEST_AUDIO,
                "-o",
                output,
                "--spectrum-mode",
                "rainbow",
                "--accel",
                "disabled",
            ],
        ):
            main()
        assert os.path.exists(output)
        assert os.path.getsize(output) > 0

    def test_spectrum_mode_fire(self, tmp_path):
        """Test spectrum with fire color mode."""
        from unittest.mock import patch

        from audio_visualizer.__main__ import main

        output = str(tmp_path / "output_fire.mp4")
        with patch(
            "sys.argv",
            [
                "audio-visualizer",
                TEST_AUDIO,
                "-o",
                output,
                "--spectrum-mode",
                "fire",
                "--accel",
                "disabled",
            ],
        ):
            main()
        assert os.path.exists(output)
        assert os.path.getsize(output) > 0

    def test_spectrum_mkv(self, tmp_path):
        """Test spectrum output as MKV."""
        from unittest.mock import patch

        from audio_visualizer.__main__ import main

        output = str(tmp_path / "output.mkv")
        with patch(
            "sys.argv",
            ["audio-visualizer", TEST_AUDIO, "-o", output, "-f", "mkv", "--accel", "disabled"],
        ):
            main()
        assert os.path.exists(output)
        assert os.path.getsize(output) > 0

    @pytest.mark.skipif(
        not _has_vpx_encoder(),
        reason="libvpx-vp9 encoder not available in this ffmpeg build",
    )
    def test_spectrum_webm(self, tmp_path):
        """Test spectrum output as WebM (VP9 video, Opus audio)."""
        from unittest.mock import patch

        from audio_visualizer.__main__ import main

        output = str(tmp_path / "output.webm")
        with patch(
            "sys.argv",
            [
                "audio-visualizer",
                TEST_AUDIO,
                "-o",
                output,
                "-f",
                "webm",
                "--accel",
                "disabled",
                # VP9 is slow; keep the encode small — this test checks the
                # container/codec wiring, not quality
                "--preset",
                "ultrafast",
                "-r",
                "320x180",
                "--fps",
                "10",
            ],
        ):
            main()
        assert os.path.exists(output)
        assert os.path.getsize(output) > 0

        probe = subprocess.run(
            [
                "ffprobe",
                "-v",
                "error",
                "-show_entries",
                "stream=codec_name",
                "-of",
                "csv=p=0",
                output,
            ],
            capture_output=True,
            text=True,
            timeout=10,
        )
        codecs = [line.strip() for line in probe.stdout.splitlines() if line.strip()]
        assert "vp9" in codecs, f"expected a VP9 video stream, got {codecs}"


@pytest.mark.e2e
class TestE2EWaveform:
    """End-to-end tests for waveform visualizer."""

    def test_waveform_default(self, tmp_path):
        """Test waveform visualizer with default args."""
        from unittest.mock import patch

        from audio_visualizer.__main__ import main

        output = str(tmp_path / "output.mp4")
        with patch(
            "sys.argv",
            [
                "audio-visualizer",
                TEST_AUDIO,
                "--mode",
                "waveform",
                "-o",
                output,
                "--accel",
                "disabled",
            ],
        ):
            main()
        assert os.path.exists(output)
        assert os.path.getsize(output) > 0

    def test_waveform_splits(self, tmp_path):
        """Test waveform with splits."""
        from unittest.mock import patch

        from audio_visualizer.__main__ import main

        output = str(tmp_path / "output_splits.mp4")
        with patch(
            "sys.argv",
            [
                "audio-visualizer",
                TEST_AUDIO,
                "--mode",
                "waveform",
                "-o",
                output,
                "--waveform-splits",
                "4",
                "--accel",
                "disabled",
            ],
        ):
            main()
        assert os.path.exists(output)
        assert os.path.getsize(output) > 0


@pytest.mark.e2e
class TestE2EComposite:
    """End-to-end tests for multi-mode compositing (--mode a b ...)."""

    def test_composite_hstack(self, tmp_path):
        """Two modes compose side by side into the requested frame."""
        import subprocess
        from unittest.mock import patch

        from audio_visualizer.__main__ import main

        output = str(tmp_path / "output_composite.mp4")
        with patch(
            "sys.argv",
            [
                "audio-visualizer",
                TEST_AUDIO,
                "--mode",
                "spectrum",
                "waveform",
                "-o",
                output,
                "--accel",
                "disabled",
            ],
        ):
            main()
        assert os.path.exists(output)
        assert os.path.getsize(output) > 0

        probe = subprocess.run(
            [
                "ffprobe",
                "-v",
                "quiet",
                "-show_entries",
                "stream=width,height",
                "-of",
                "csv=p=0",
                output,
            ],
            capture_output=True,
            text=True,
            timeout=10,
        )
        assert probe.returncode == 0
        assert probe.stdout.strip().splitlines()[0] == "1280,720"

    def test_composite_tile_layout(self, tmp_path):
        """Three modes tile into a 2x2 grid with a padded corner cell."""
        import subprocess
        from unittest.mock import patch

        from audio_visualizer.__main__ import main

        output = str(tmp_path / "output_tile.mp4")
        with patch(
            "sys.argv",
            [
                "audio-visualizer",
                TEST_AUDIO,
                "--mode",
                "spectrum",
                "waveform",
                "vectorscope",
                "--compose",
                "tile",
                "-o",
                output,
                "--accel",
                "disabled",
            ],
        ):
            main()
        assert os.path.exists(output)
        assert os.path.getsize(output) > 0

        probe = subprocess.run(
            [
                "ffprobe",
                "-v",
                "quiet",
                "-show_entries",
                "stream=width,height",
                "-of",
                "csv=p=0",
                output,
            ],
            capture_output=True,
            text=True,
            timeout=10,
        )
        assert probe.returncode == 0
        assert probe.stdout.strip().splitlines()[0] == "1280,720"

    def test_composite_unknown_mode_exits(self, tmp_path):
        """A bad second mode fails with the friendly unknown-mode error."""
        from unittest.mock import patch

        from audio_visualizer.__main__ import main

        output = str(tmp_path / "output.mp4")
        with patch(
            "sys.argv",
            [
                "audio-visualizer",
                TEST_AUDIO,
                "--mode",
                "spectrum",
                "bogus",
                "-o",
                output,
                "--accel",
                "disabled",
            ],
        ):
            with pytest.raises(SystemExit) as exc:
                main()
            assert exc.value.code == 1


@pytest.mark.e2e
class TestE2EVectorscope:
    """End-to-end tests for vectorscope visualizer."""

    def test_vectorscope_default(self, tmp_path):
        """Test vectorscope with default args."""
        from unittest.mock import patch

        from audio_visualizer.__main__ import main

        output = str(tmp_path / "output.mp4")
        with patch(
            "sys.argv",
            [
                "audio-visualizer",
                TEST_AUDIO,
                "--mode",
                "vectorscope",
                "-o",
                output,
                "--accel",
                "disabled",
            ],
        ):
            main()
        assert os.path.exists(output)
        assert os.path.getsize(output) > 0

    def test_vectorscope_colors(self, tmp_path):
        """Test vectorscope with custom colors."""
        from unittest.mock import patch

        from audio_visualizer.__main__ import main

        output = str(tmp_path / "output_colors.mp4")
        with patch(
            "sys.argv",
            [
                "audio-visualizer",
                TEST_AUDIO,
                "--mode",
                "vectorscope",
                "-o",
                output,
                "--colors",
                "cyan,magenta,yellow",
                "--accel",
                "disabled",
            ],
        ):
            main()
        assert os.path.exists(output)
        assert os.path.getsize(output) > 0


@pytest.mark.e2e
class TestE2ERadial:
    """End-to-end tests for radial visualizer."""

    def test_radial_default(self, tmp_path):
        """Test radial with default args."""
        from unittest.mock import patch

        from audio_visualizer.__main__ import main

        output = str(tmp_path / "output.mp4")
        with patch(
            "sys.argv",
            [
                "audio-visualizer",
                TEST_AUDIO,
                "--mode",
                "radial",
                "-o",
                output,
                "--accel",
                "disabled",
            ],
        ):
            main()
        assert os.path.exists(output)
        assert os.path.getsize(output) > 0

    def test_radial_mirror_x(self, tmp_path):
        """Test radial with horizontal mirror."""
        from unittest.mock import patch

        from audio_visualizer.__main__ import main

        output = str(tmp_path / "output_x.mp4")
        with patch(
            "sys.argv",
            [
                "audio-visualizer",
                TEST_AUDIO,
                "--mode",
                "radial",
                "-o",
                output,
                "--mirror-axis",
                "x",
                "--accel",
                "disabled",
            ],
        ):
            main()
        assert os.path.exists(output)
        assert os.path.getsize(output) > 0

    def test_radial_mirror_xy(self, tmp_path):
        """Test radial with both axes mirror."""
        from unittest.mock import patch

        from audio_visualizer.__main__ import main

        output = str(tmp_path / "output_xy.mp4")
        with patch(
            "sys.argv",
            [
                "audio-visualizer",
                TEST_AUDIO,
                "--mode",
                "radial",
                "-o",
                output,
                "--mirror-axis",
                "xy",
                "--accel",
                "disabled",
            ],
        ):
            main()
        assert os.path.exists(output)
        assert os.path.getsize(output) > 0

    def test_radial_mirror_gap(self, tmp_path):
        """Test radial with mirror gap."""
        from unittest.mock import patch

        from audio_visualizer.__main__ import main

        output = str(tmp_path / "output_gap.mp4")
        with patch(
            "sys.argv",
            [
                "audio-visualizer",
                TEST_AUDIO,
                "--mode",
                "radial",
                "-o",
                output,
                "--mirror-gap",
                "20",
                "--accel",
                "disabled",
            ],
        ):
            main()
        assert os.path.exists(output)
        assert os.path.getsize(output) > 0


@pytest.mark.e2e
class TestE2ESpectrogram:
    """End-to-end tests for spectrogram visualizer."""

    def test_spectrogram_default(self, tmp_path):
        """Test spectrogram with default args."""
        from unittest.mock import patch

        from audio_visualizer.__main__ import main

        output = str(tmp_path / "output.mp4")
        with patch(
            "sys.argv",
            [
                "audio-visualizer",
                TEST_AUDIO,
                "--mode",
                "spectrogram",
                "-o",
                output,
                "--accel",
                "disabled",
            ],
        ):
            main()
        assert os.path.exists(output)
        assert os.path.getsize(output) > 0

    def test_spectrogram_mode_fire(self, tmp_path):
        """Test spectrogram with fire mode."""
        from unittest.mock import patch

        from audio_visualizer.__main__ import main

        output = str(tmp_path / "output_fire.mp4")
        with patch(
            "sys.argv",
            [
                "audio-visualizer",
                TEST_AUDIO,
                "--mode",
                "spectrogram",
                "-o",
                output,
                "--spectrogram-mode",
                "fire",
                "--accel",
                "disabled",
            ],
        ):
            main()
        assert os.path.exists(output)
        assert os.path.getsize(output) > 0


@pytest.mark.e2e
class TestE2EBars:
    """End-to-end tests for bars visualizer."""

    def test_bars_default(self, tmp_path):
        """Test bars with default args."""
        from unittest.mock import patch

        from audio_visualizer.__main__ import main

        output = str(tmp_path / "output.mp4")
        with patch(
            "sys.argv",
            ["audio-visualizer", TEST_AUDIO, "--mode", "bars", "-o", output, "--accel", "disabled"],
        ):
            main()
        assert os.path.exists(output)
        assert os.path.getsize(output) > 0


@pytest.mark.e2e
class TestE2ECQT:
    """End-to-end tests for CQT visualizer."""

    def test_cqt_default(self, tmp_path):
        """Test CQT with default args."""
        from unittest.mock import patch

        from audio_visualizer.__main__ import main

        output = str(tmp_path / "output.mp4")
        with patch(
            "sys.argv",
            ["audio-visualizer", TEST_AUDIO, "--mode", "cqt", "-o", output, "--accel", "disabled"],
        ):
            main()
        assert os.path.exists(output)
        assert os.path.getsize(output) > 0


@pytest.mark.e2e
class TestE2EPeakbars:
    """End-to-end tests for peakbars visualizer."""

    def test_peakbars_default(self, tmp_path):
        """Test peakbars with default args (peak-hold layer active)."""
        from unittest.mock import patch

        from audio_visualizer.__main__ import main

        output = str(tmp_path / "output.mp4")
        with patch(
            "sys.argv",
            [
                "audio-visualizer",
                TEST_AUDIO,
                "--mode",
                "peakbars",
                "-o",
                output,
                "--accel",
                "disabled",
            ],
        ):
            main()
        assert os.path.exists(output)
        assert os.path.getsize(output) > 0

    def test_peakbars_custom_hold_decay(self, tmp_path):
        """Test peakbars with explicit hold/decay options."""
        from unittest.mock import patch

        from audio_visualizer.__main__ import main

        output = str(tmp_path / "output.mp4")
        with patch(
            "sys.argv",
            [
                "audio-visualizer",
                TEST_AUDIO,
                "--mode",
                "peakbars",
                "--peakbars-hold",
                "0.3",
                "--peakbars-decay",
                "1.0",
                "-o",
                output,
                "--accel",
                "disabled",
            ],
        ):
            main()
        assert os.path.exists(output)
        assert os.path.getsize(output) > 0


@pytest.mark.e2e
class TestE2EOscilloscope:
    """End-to-end tests for oscilloscope visualizer."""

    def test_oscilloscope_default(self, tmp_path):
        """Test oscilloscope with default args (grid + persistence)."""
        from unittest.mock import patch

        from audio_visualizer.__main__ import main

        output = str(tmp_path / "output.mp4")
        with patch(
            "sys.argv",
            [
                "audio-visualizer",
                TEST_AUDIO,
                "--mode",
                "oscilloscope",
                "-o",
                output,
                "--accel",
                "disabled",
            ],
        ):
            main()
        assert os.path.exists(output)
        assert os.path.getsize(output) > 0

    def test_oscilloscope_no_persist_no_grid(self, tmp_path):
        """Test oscilloscope with persistence and grid disabled."""
        from unittest.mock import patch

        from audio_visualizer.__main__ import main

        output = str(tmp_path / "output.mp4")
        with patch(
            "sys.argv",
            [
                "audio-visualizer",
                TEST_AUDIO,
                "--mode",
                "oscilloscope",
                "--oscilloscope-persist",
                "0",
                "--oscilloscope-grid",
                "0",
                "--oscilloscope-scale",
                "log",
                "-o",
                output,
                "--accel",
                "disabled",
            ],
        ):
            main()
        assert os.path.exists(output)
        assert os.path.getsize(output) > 0


@pytest.mark.e2e
class TestE2EAlbumArt:
    """End-to-end tests for album art visualizer."""

    def test_albumart_default(self, tmp_path):
        """Test album art with default args."""
        from unittest.mock import patch

        from audio_visualizer.__main__ import main

        output = str(tmp_path / "output.mp4")
        with patch(
            "sys.argv",
            [
                "audio-visualizer",
                TEST_AUDIO,
                "--mode",
                "albumart",
                "--image",
                TEST_IMAGE,
                "-o",
                output,
                "--accel",
                "disabled",
            ],
        ):
            main()
        assert os.path.exists(output)
        assert os.path.getsize(output) > 0

    def test_albumart_pulse(self, tmp_path):
        """Test album art with pulse effect."""
        from unittest.mock import patch

        from audio_visualizer.__main__ import main

        output = str(tmp_path / "output.mp4")
        with patch(
            "sys.argv",
            [
                "audio-visualizer",
                TEST_AUDIO,
                "--mode",
                "albumart",
                "--image",
                TEST_IMAGE,
                "-o",
                output,
                "--albumart-effect",
                "pulse",
                "--accel",
                "disabled",
            ],
        ):
            main()
        assert os.path.exists(output)
        assert os.path.getsize(output) > 0

    def test_albumart_zoom(self, tmp_path):
        """Test album art with zoom effect."""
        from unittest.mock import patch

        from audio_visualizer.__main__ import main

        output = str(tmp_path / "output.mp4")
        with patch(
            "sys.argv",
            [
                "audio-visualizer",
                TEST_AUDIO,
                "--mode",
                "albumart",
                "--image",
                TEST_IMAGE,
                "-o",
                output,
                "--albumart-effect",
                "zoom",
                "--accel",
                "disabled",
            ],
        ):
            main()
        assert os.path.exists(output)
        assert os.path.getsize(output) > 0


@pytest.mark.e2e
class TestE2EFormats:
    """End-to-end tests for different output formats."""

    @pytest.mark.parametrize(
        "fmt,ext",
        [
            ("mp4", ".mp4"),
            ("mkv", ".mkv"),
            ("mov", ".mov"),
        ],
    )
    def test_format(self, tmp_path, fmt, ext):
        """Test different output formats."""
        from unittest.mock import patch

        from audio_visualizer.__main__ import main

        output = str(tmp_path / f"output{ext}")
        with patch(
            "sys.argv",
            ["audio-visualizer", TEST_AUDIO, "-o", output, "-f", fmt, "--accel", "disabled"],
        ):
            main()
        assert os.path.exists(output)
        assert os.path.getsize(output) > 0


@pytest.mark.e2e
class TestE2EResolutions:
    """End-to-end tests for different resolutions."""

    @pytest.mark.parametrize(
        "resolution",
        [
            "320x240",  # QVGA
            "640x480",  # VGA
            "1280x720",  # HD
        ],
    )
    def test_resolution(self, tmp_path, resolution):
        """Test different output resolutions."""
        from unittest.mock import patch

        from audio_visualizer.__main__ import main

        output = str(tmp_path / "output.mp4")
        with patch(
            "sys.argv",
            ["audio-visualizer", TEST_AUDIO, "-o", output, "-r", resolution, "--accel", "disabled"],
        ):
            main()
        assert os.path.exists(output)
        assert os.path.getsize(output) > 0

    @pytest.mark.parametrize(
        ("preset", "expected_w", "expected_h"),
        [
            ("480p", 854, 480),
            ("1080p", 1920, 1080),
        ],
    )
    def test_resolution_preset(self, tmp_path, preset, expected_w, expected_h):
        """16:9 presets expand to WxH and the encode honors them."""
        from unittest.mock import patch

        from audio_visualizer.__main__ import main

        output = str(tmp_path / "output.mp4")
        with patch(
            "sys.argv",
            [
                "audio-visualizer",
                TEST_AUDIO,
                "-o",
                output,
                "-r",
                preset,
                "--accel",
                "disabled",
                "--preset",
                "ultrafast",
            ],
        ):
            main()
        probe = subprocess.run(
            [
                "ffprobe",
                "-v",
                "error",
                "-select_streams",
                "v:0",
                "-show_entries",
                "stream=width,height",
                "-of",
                "csv=p=0",
                output,
            ],
            capture_output=True,
            text=True,
            timeout=10,
        )
        width, height = (int(x) for x in probe.stdout.strip().split(","))
        assert (width, height) == (expected_w, expected_h)


@pytest.mark.e2e
class TestE2EBgColor:
    """End-to-end tests for background color."""

    def test_bg_color_named(self, tmp_path):
        """Test with named background color."""
        from unittest.mock import patch

        from audio_visualizer.__main__ import main

        output = str(tmp_path / "output.mp4")
        with patch(
            "sys.argv",
            [
                "audio-visualizer",
                TEST_AUDIO,
                "-o",
                output,
                "--bg-color",
                "navy",
                "--accel",
                "disabled",
            ],
        ):
            main()
        assert os.path.exists(output)
        assert os.path.getsize(output) > 0

    def test_bg_color_hex(self, tmp_path):
        """Test with hex background color."""
        from unittest.mock import patch

        from audio_visualizer.__main__ import main

        output = str(tmp_path / "output.mp4")
        with patch(
            "sys.argv",
            [
                "audio-visualizer",
                TEST_AUDIO,
                "-o",
                output,
                "--bg-color",
                "#1a1a2e",
                "--accel",
                "disabled",
            ],
        ):
            main()
        assert os.path.exists(output)
        assert os.path.getsize(output) > 0


@pytest.mark.e2e
class TestE2EAudioVariants:
    """End-to-end tests for different audio file types."""

    @pytest.mark.parametrize(
        "audio_file",
        [
            "test.mp3",
            "test.wav",
            "test.ogg",
            "test.flac",
            "test.aac",
            "test.m4a",
        ],
    )
    def test_audio_format(self, tmp_path, audio_file):
        """Test different audio input formats."""
        from unittest.mock import patch

        from audio_visualizer.__main__ import main

        audio_path = os.path.join(os.path.dirname(__file__), "assets", audio_file)
        output = str(tmp_path / "output.mp4")
        with patch(
            "sys.argv", ["audio-visualizer", audio_path, "-o", output, "--accel", "disabled"]
        ):
            main()
        assert os.path.exists(output)
        assert os.path.getsize(output) > 0

    def test_mono_audio(self, tmp_path):
        """Test with mono audio file."""
        from unittest.mock import patch

        from audio_visualizer.__main__ import main

        output = str(tmp_path / "output.mp4")
        with patch(
            "sys.argv", ["audio-visualizer", TEST_MONO, "-o", output, "--accel", "disabled"]
        ):
            main()
        assert os.path.exists(output)
        assert os.path.getsize(output) > 0


@pytest.mark.e2e
class TestE2EHighSampleRate:
    """End-to-end tests for high sample rate audio."""

    def test_48k_audio(self, tmp_path):
        """Test with 48kHz audio."""
        from unittest.mock import patch

        from audio_visualizer.__main__ import main

        audio_path = os.path.join(os.path.dirname(__file__), "assets", "test_48k.wav")
        output = str(tmp_path / "output.mp4")
        with patch(
            "sys.argv", ["audio-visualizer", audio_path, "-o", output, "--accel", "disabled"]
        ):
            main()
        assert os.path.exists(output)
        assert os.path.getsize(output) > 0

    def test_96k_audio(self, tmp_path):
        """Test with 96kHz audio."""
        from unittest.mock import patch

        from audio_visualizer.__main__ import main

        audio_path = os.path.join(os.path.dirname(__file__), "assets", "test_96k.wav")
        output = str(tmp_path / "output.mp4")
        with patch(
            "sys.argv", ["audio-visualizer", audio_path, "-o", output, "--accel", "disabled"]
        ):
            main()
        assert os.path.exists(output)
        assert os.path.getsize(output) > 0


class TestE2EErrorHandling:
    """End-to-end tests for error handling."""

    def test_missing_input(self, tmp_path):
        """Test error when input file doesn't exist."""
        from unittest.mock import patch

        from audio_visualizer.__main__ import main

        output = str(tmp_path / "output.mp4")
        with patch(
            "sys.argv",
            ["audio-visualizer", "/nonexistent/file.mp3", "-o", output, "--accel", "disabled"],
        ):
            with pytest.raises(SystemExit) as exc:
                main()
            assert exc.value.code == 1

    def test_missing_image(self, tmp_path):
        """Test error when album art image doesn't exist."""
        from unittest.mock import patch

        from audio_visualizer.__main__ import main

        output = str(tmp_path / "output.mp4")
        with patch(
            "sys.argv",
            [
                "audio-visualizer",
                TEST_AUDIO,
                "--mode",
                "albumart",
                "--image",
                "/nonexistent/image.jpg",
                "-o",
                output,
                "--accel",
                "disabled",
            ],
        ):
            with pytest.raises(SystemExit) as exc:
                main()
            assert exc.value.code == 1

    def test_invalid_mode(self, tmp_path):
        """Test error when mode doesn't exist."""
        from unittest.mock import patch

        from audio_visualizer.__main__ import main

        output = str(tmp_path / "output.mp4")
        with patch(
            "sys.argv",
            [
                "audio-visualizer",
                TEST_AUDIO,
                "--mode",
                "nonexistent",
                "-o",
                output,
                "--accel",
                "disabled",
            ],
        ):
            with pytest.raises(SystemExit) as exc:
                main()
            assert exc.value.code == 1


LONG_AUDIO = os.path.join(os.path.dirname(__file__), "assets", "long.mp3")


def _run_cli(tmp_path, *argv):
    """Run the CLI with the given argv and return the output path."""
    from unittest.mock import patch

    from audio_visualizer.__main__ import main

    output = str(tmp_path / "output.mp4")
    with patch("sys.argv", ["audio-visualizer", *argv, "-o", output]):
        main()
    assert os.path.exists(output)
    assert os.path.getsize(output) > 0
    return output


@pytest.mark.e2e
class TestE2EBugfixRound:
    """Regression tests for the v2.0.0 bugfix round.

    Each test exercises a code path that was broken before the fix:
    see the [Unreleased] CHANGELOG section.
    """

    def test_circular_spectrum_encodes(self, tmp_path):
        """Circular spectrum previously emitted an invalid filter graph
        (the [spectrum] label was consumed four times) and could never
        be encoded by ffmpeg."""
        _run_cli(
            tmp_path,
            TEST_AUDIO,
            "--mode",
            "circular-spectrum",
            "-r",
            "640x360",
            "--fps",
            "15",
            "--accel",
            "disabled",
        )

    def test_bars_vertical_matches_resolution(self, tmp_path):
        """Vertical bars previously produced an HxW video that did not
        match the requested WxH output resolution."""
        import subprocess

        output = _run_cli(
            tmp_path,
            TEST_AUDIO,
            "--mode",
            "bars",
            "--bar-orientation",
            "vertical",
            "-r",
            "640x360",
            "--fps",
            "15",
            "--accel",
            "disabled",
        )
        probe = subprocess.run(
            [
                "ffprobe",
                "-v",
                "error",
                "-select_streams",
                "v:0",
                "-show_entries",
                "stream=width,height",
                "-of",
                "csv=p=0",
                output,
            ],
            capture_output=True,
            text=True,
            timeout=10,
        )
        w, h = (int(x) for x in probe.stdout.strip().split(","))
        assert (w, h) == (640, 360)

    def test_vectorscope_border_encodes(self, tmp_path):
        """--vectorscope-border previously composed the border as a
        same-size underlay completely covered by the opaque scope."""
        _run_cli(
            tmp_path,
            TEST_AUDIO,
            "--mode",
            "vectorscope",
            "--vectorscope-border",
            "-r",
            "640x360",
            "--fps",
            "15",
            "--accel",
            "disabled",
        )

    def test_spectrum_style_forwarded(self, tmp_path):
        """Plugin options like --spectrum-style were dropped by the old
        curated args dict and never reached the encode."""
        import subprocess

        output = _run_cli(
            tmp_path,
            TEST_AUDIO,
            "--mode",
            "spectrum",
            "--spectrum-style",
            "replace",
            "--spectrum-opacity",
            "0.5",
            "-r",
            "640x360",
            "--fps",
            "15",
            "--accel",
            "disabled",
        )
        probe = subprocess.run(
            [
                "ffprobe",
                "-v",
                "error",
                "-show_entries",
                "format=duration",
                "-of",
                "csv=p=0",
                output,
            ],
            capture_output=True,
            text=True,
            timeout=10,
        )
        assert float(probe.stdout.strip()) > 9.0

    def test_batch_continues_after_failure(self, tmp_path):
        """A single file's ffmpeg failure (SystemExit) used to abort the
        whole batch; now the batch continues and reports the failure."""
        import subprocess

        batch_dir = tmp_path / "batch"
        batch_dir.mkdir()
        import shutil

        shutil.copy(TEST_AUDIO, batch_dir / "a_ok.mp3")
        shutil.copy(TEST_AUDIO, batch_dir / "b_fail.mp3")

        # Invalid border color makes ffmpeg fail on every file
        out = subprocess.run(
            [
                "python",
                "-m",
                "audio_visualizer",
                "--batch",
                str(batch_dir),
                "-o",
                str(tmp_path / "out"),
                "--mode",
                "spectrum",
                "-r",
                "320x240",
                "--fps",
                "10",
                "--border",
                "--border-color",
                "notacolor",
                "--accel",
                "disabled",
            ],
            capture_output=True,
            text=True,
            timeout=300,
        )
        # Both files were attempted and the batch completed with a summary
        combined = out.stdout + out.stderr
        assert "[1/2]" in combined
        assert "[2/2]" in combined
        assert "Batch complete: 0 succeeded, 2 failed, 0 skipped" in combined

    def test_unknown_mode_friendly_error(self, tmp_path):
        """An unknown --mode used to crash with a TypeError while joining
        plugin metadata dicts; now it exits with a clear message."""
        import subprocess

        out = subprocess.run(
            [
                "python",
                "-m",
                "audio_visualizer",
                TEST_AUDIO,
                "--mode",
                "bogus",
            ],
            capture_output=True,
            text=True,
            timeout=60,
        )
        assert out.returncode == 1
        assert "Unknown mode" in (out.stdout + out.stderr)
        assert "TypeError" not in (out.stdout + out.stderr)

    def test_measured_size_estimate_no_tmpdir_leak(self, tmp_path):
        """The test-encode size estimator previously raised a NameError
        (shutil only imported in the albumart branch) for every other
        plugin, silently falling back and leaking temp dirs."""
        import os as os_mod
        import tempfile

        from audio_visualizer.core import _estimate_output_size
        from audio_visualizer.visualizers.spectrum import SpectrumPlugin

        before = set(os_mod.listdir(tempfile.gettempdir()))
        est = _estimate_output_size(
            SpectrumPlugin,
            {
                "input": LONG_AUDIO,
                "width": 640,
                "height": 360,
                "fps": 15,
                "preset": "medium",
                "crf": 23,
                "format": "mp4",
            },
            30.0,
            "sw",
        )
        after = set(os_mod.listdir(tempfile.gettempdir()))
        assert est > 0
        assert not (after - before), f"leaked temp dirs: {after - before}"


class TestThemeE2E:
    """End-to-end tests for --theme (carried over from the v1.x checklist).

    Themes resolve to a color palette in merge_config(). These tests prove
    the resolved palette actually reaches the ffmpeg command, and that the
    precedence is CLI theme > env theme > config theme, with explicit
    --colors always winning over any theme.
    """

    MODE_ARGS = [
        "--mode",
        "spectrum",
        "--spectrum-mode",
        "colormapping",
        "--dry-run",
        "--accel",
        "disabled",
    ]

    @staticmethod
    def _palette(theme: str) -> str:
        """The colormapping string a theme should produce in the filter."""
        from audio_visualizer.config import COLOR_THEMES
        from audio_visualizer.visualizers.colors import ColorParser

        return ColorParser(COLOR_THEMES[theme]).as_colormapping()

    @staticmethod
    def _write_config(home, theme: str):
        """Write a config.yml with the given theme into an isolated home."""
        from pathlib import Path

        cfg_dir = Path(home) / ".audio_visualizer"
        cfg_dir.mkdir(parents=True, exist_ok=True)
        (cfg_dir / "config.yml").write_text(f"theme: {theme}\n")

    def test_cli_theme_reaches_ffmpeg_command(self, tmp_path, monkeypatch, caplog):
        """--theme from the CLI (not just a config file) resolves to the
        palette and lands in the filter graph."""
        from unittest.mock import patch

        from audio_visualizer.__main__ import main

        monkeypatch.setenv("HOME", str(tmp_path))
        monkeypatch.delenv("AUDIO_VISUALIZER_THEME", raising=False)
        with patch(
            "sys.argv",
            ["audio-visualizer", TEST_AUDIO, "-o", str(tmp_path / "out.mp4")]
            + self.MODE_ARGS
            + ["--theme", "neon"],
        ):
            main()
        assert f"colormapping={self._palette('neon')}" in caplog.text

    def test_cli_theme_beats_config_theme(self, tmp_path, monkeypatch, caplog):
        from unittest.mock import patch

        from audio_visualizer.__main__ import main

        self._write_config(tmp_path, "sunset")
        monkeypatch.setenv("HOME", str(tmp_path))
        monkeypatch.delenv("AUDIO_VISUALIZER_THEME", raising=False)
        with patch(
            "sys.argv",
            ["audio-visualizer", TEST_AUDIO, "-o", str(tmp_path / "out.mp4")]
            + self.MODE_ARGS
            + ["--theme", "neon"],
        ):
            main()
        assert f"colormapping={self._palette('neon')}" in caplog.text
        assert f"colormapping={self._palette('sunset')}" not in caplog.text

    def test_env_theme_beats_config_theme(self, tmp_path, monkeypatch, caplog):
        from unittest.mock import patch

        from audio_visualizer.__main__ import main

        self._write_config(tmp_path, "forest")
        monkeypatch.setenv("HOME", str(tmp_path))
        monkeypatch.setenv("AUDIO_VISUALIZER_THEME", "ocean")
        with patch(
            "sys.argv",
            ["audio-visualizer", TEST_AUDIO, "-o", str(tmp_path / "out.mp4")] + self.MODE_ARGS,
        ):
            main()
        assert f"colormapping={self._palette('ocean')}" in caplog.text
        assert f"colormapping={self._palette('forest')}" not in caplog.text

    def test_config_theme_used_without_cli_or_env(self, tmp_path, monkeypatch, caplog):
        from unittest.mock import patch

        from audio_visualizer.__main__ import main

        self._write_config(tmp_path, "forest")
        monkeypatch.setenv("HOME", str(tmp_path))
        monkeypatch.delenv("AUDIO_VISUALIZER_THEME", raising=False)
        with patch(
            "sys.argv",
            ["audio-visualizer", TEST_AUDIO, "-o", str(tmp_path / "out.mp4")] + self.MODE_ARGS,
        ):
            main()
        assert f"colormapping={self._palette('forest')}" in caplog.text

    def test_explicit_colors_beat_theme(self, tmp_path, monkeypatch, caplog):
        from unittest.mock import patch

        from audio_visualizer.__main__ import main

        monkeypatch.setenv("HOME", str(tmp_path))
        monkeypatch.delenv("AUDIO_VISUALIZER_THEME", raising=False)
        with patch(
            "sys.argv",
            ["audio-visualizer", TEST_AUDIO, "-o", str(tmp_path / "out.mp4")]
            + self.MODE_ARGS
            + ["--theme", "neon", "--colors", "red,blue"],
        ):
            main()
        explicit = self._palette_from("red,blue")
        assert f"colormapping={explicit}" in caplog.text
        assert f"colormapping={self._palette('neon')}" not in caplog.text

    @staticmethod
    def _palette_from(colors: str) -> str:
        from audio_visualizer.visualizers.colors import ColorParser

        return ColorParser(colors).as_colormapping()


@pytest.mark.e2e
class TestThemeRealEncode:
    """Regression: a themed encode must survive real ffmpeg (v2.2.0 sec.3.2).

    The dry-run tests above only check that the palette lands in the
    generated command; the showfreqs palette bug (commas in a
    pipe-separated option) could only be caught by a real encode.
    """

    def test_showfreqs_theme_real_encode(self, tmp_path, monkeypatch):
        from unittest.mock import patch

        from audio_visualizer.__main__ import main

        monkeypatch.setenv("HOME", str(tmp_path))
        monkeypatch.delenv("AUDIO_VISUALIZER_THEME", raising=False)
        output = str(tmp_path / "theme_showfreqs.mp4")
        with patch(
            "sys.argv",
            [
                "audio-visualizer", TEST_AUDIO, "-o", output,
                "--mode", "showfreqs", "--theme", "neon",
                "--accel", "disabled", "--resolution", "320x180",
                "--fps", "10", "--preset", "ultrafast",
            ],
        ):
            main()
        assert os.path.exists(output) and os.path.getsize(output) > 0


@pytest.mark.e2e
class TestComposeGridE2E:
    """v2.2.0 sec.2.2: --compose-grid survives a real encode."""

    def test_grid_encode(self, tmp_path):
        from unittest.mock import patch

        from audio_visualizer.__main__ import main

        output = str(tmp_path / "grid.mp4")
        with patch(
            "sys.argv",
            [
                "audio-visualizer", TEST_AUDIO, "-o", output,
                "--accel", "disabled", "--resolution", "640x360",
                "--fps", "10", "--preset", "ultrafast",
                "--compose", "tile", "--compose-grid", "2x2",
                "--mode", "spectrum", "waveform", "bars",
            ],
        ):
            main()
        assert os.path.exists(output) and os.path.getsize(output) > 0

    def test_overlay_opacity_encode(self, tmp_path):
        from unittest.mock import patch

        from audio_visualizer.__main__ import main

        output = str(tmp_path / "op.mp4")
        with patch(
            "sys.argv",
            [
                "audio-visualizer", TEST_AUDIO, "-o", output,
                "--accel", "disabled", "--resolution", "320x180",
                "--fps", "10", "--preset", "ultrafast",
                "--compose", "overlay",
                "--mode", "spectrum",
                "--mode", "vectorscope:opacity=0.5",
                "--mode", "bars",
            ],
        ):
            main()
        assert os.path.exists(output) and os.path.getsize(output) > 0


@pytest.mark.e2e
class TestE2EMetadata:
    """End-to-end tests for output container metadata (v2.1.0 sec.4)."""

    TAGS = {
        "title": "Test Song",
        "artist": "Test Artist",
        "album": "Test Album",
        "comment": "Test Comment",
    }

    @pytest.fixture(scope="class")
    def tagged_mp3(self, tmp_path_factory) -> str:
        """A short (~2s) MP3 with all four ID3 tags set (stream copy)."""
        out = str(tmp_path_factory.mktemp("tagged") / "tagged.mp3")
        result = subprocess.run(
            [
                "ffmpeg",
                "-y",
                "-v",
                "error",
                "-i",
                TEST_AUDIO,
                "-t",
                "2",
                "-metadata",
                "title=Test Song",
                "-metadata",
                "artist=Test Artist",
                "-metadata",
                "album=Test Album",
                "-metadata",
                "comment=Test Comment",
                "-c",
                "copy",
                out,
            ],
            capture_output=True,
            text=True,
            timeout=60,
        )
        assert result.returncode == 0, result.stderr
        assert os.path.getsize(out) > 0
        return out

    @staticmethod
    def _tags(path: str) -> dict:
        """Format-level tags of a file, via ffprobe."""
        result = subprocess.run(
            ["ffprobe", "-v", "quiet", "-print_format", "json", "-show_format", path],
            capture_output=True,
            text=True,
            timeout=30,
        )
        assert result.returncode == 0
        return (json.loads(result.stdout).get("format") or {}).get("tags") or {}

    def test_source_tags_copied(self, tmp_path, tagged_mp3):
        """Title/artist/album/comment from the source reach the video container."""
        out = _run_cli(
            tmp_path,
            tagged_mp3,
            "-r",
            "320x180",
            "--preset",
            "ultrafast",
            "--crf",
            "30",
            "--accel",
            "disabled",
        )
        tags = self._tags(out)
        for key, value in self.TAGS.items():
            assert tags.get(key) == value, f"{key}: {tags.get(key)!r} != {value!r}"

    def test_overrides_win_over_source_tags(self, tmp_path, tagged_mp3):
        """--title/--artist override the copied tags; the rest still copy."""
        out = _run_cli(
            tmp_path,
            tagged_mp3,
            "-r",
            "320x180",
            "--preset",
            "ultrafast",
            "--crf",
            "30",
            "--accel",
            "disabled",
            "--title",
            "Custom Title",
            "--artist",
            "Custom Artist",
        )
        tags = self._tags(out)
        assert tags.get("title") == "Custom Title"
        assert tags.get("artist") == "Custom Artist"
        assert tags.get("album") == self.TAGS["album"]
        assert tags.get("comment") == self.TAGS["comment"]

    def test_no_metadata_strips_all_tags(self, tmp_path, tagged_mp3):
        """--no-metadata yields a clean output (no source tags at all)."""
        out = _run_cli(
            tmp_path,
            tagged_mp3,
            "-r",
            "320x180",
            "--preset",
            "ultrafast",
            "--crf",
            "30",
            "--accel",
            "disabled",
            "--no-metadata",
        )
        tags = self._tags(out)
        for key in self.TAGS:
            assert key not in tags, f"{key} should be stripped: {tags}"


@pytest.mark.e2e
@pytest.mark.smoke
class TestSmoke:
    """PR smoke subset (v2.2.0 sec.4.1/4.2): one short encode per
    built-in visualizer plus one per output format (mp4/mkv/webm).

    Clips are ~1 s at 10 fps on a small frame; the peak-hold and
    oscilloscope encodes (the slowest tap chains) are capped at
    2 s @ 10 fps so their hold+decay window still runs while the
    graph stays small. Runs on pull requests (``pytest -m
    "smoke or not e2e"``) for fast green/red feedback; the
    full-length encodes stay in the push-only full suite.
    """

    RESOLUTION = "640x360"
    FPS = 10

    @classmethod
    def _encode(cls, tmp_path, name: str, audio: str, extra: list, fmt: str = "mp4") -> str:
        """Run one short encode through the real CLI and assert an output."""
        from unittest.mock import patch

        from audio_visualizer.__main__ import main

        output = str(tmp_path / f"smoke_{name}.{fmt}")
        with patch(
            "sys.argv",
            [
                "audio-visualizer",
                audio,
                "-o",
                output,
                "--resolution",
                cls.RESOLUTION,
                "--fps",
                str(cls.FPS),
                "--preset",
                "fast",
                "--accel",
                "disabled",
                "--format",
                fmt,
            ]
            + extra,
        ):
            main()
        assert os.path.exists(output), f"smoke encode produced no output: {output}"
        assert os.path.getsize(output) > 0

    def test_smoke_spectrum(self, tmp_path, smoke_audio):
        self._encode(tmp_path, "spectrum", smoke_audio["1s"], ["--mode", "spectrum"])

    def test_smoke_waveform(self, tmp_path, smoke_audio):
        self._encode(tmp_path, "waveform", smoke_audio["1s"], ["--mode", "waveform"])

    def test_smoke_vectorscope(self, tmp_path, smoke_audio):
        self._encode(tmp_path, "vectorscope", smoke_audio["1s"], ["--mode", "vectorscope"])

    def test_smoke_radial(self, tmp_path, smoke_audio):
        self._encode(tmp_path, "radial", smoke_audio["1s"], ["--mode", "radial"])

    def test_smoke_bars(self, tmp_path, smoke_audio):
        self._encode(tmp_path, "bars", smoke_audio["1s"], ["--mode", "bars"])

    def test_smoke_showfreqs(self, tmp_path, smoke_audio):
        self._encode(tmp_path, "showfreqs", smoke_audio["1s"], ["--mode", "showfreqs"])

    def test_smoke_showvolume(self, tmp_path, smoke_audio):
        self._encode(tmp_path, "showvolume", smoke_audio["1s"], ["--mode", "showvolume"])

    def test_smoke_cqt(self, tmp_path, smoke_audio):
        self._encode(tmp_path, "cqt", smoke_audio["1s"], ["--mode", "cqt"])

    def test_smoke_spectrogram(self, tmp_path, smoke_audio):
        self._encode(tmp_path, "spectrogram", smoke_audio["1s"], ["--mode", "spectrogram"])

    def test_smoke_circular_spectrum(self, tmp_path, smoke_audio):
        self._encode(
            tmp_path, "circular-spectrum", smoke_audio["1s"], ["--mode", "circular-spectrum"]
        )

    def test_smoke_peakbars(self, tmp_path, smoke_audio):
        # Capped at 2 s @ 10 fps: the 21-60 tap delay chains are the
        # slowest encodes (sec.4.2), so smoke keeps them short but long
        # enough for the default hold+decay window.
        self._encode(tmp_path, "peakbars", smoke_audio["2s"], ["--mode", "peakbars"])

    def test_smoke_oscilloscope(self, tmp_path, smoke_audio):
        self._encode(tmp_path, "oscilloscope", smoke_audio["2s"], ["--mode", "oscilloscope"])

    def test_smoke_albumart(self, tmp_path, smoke_audio):
        self._encode(
            tmp_path,
            "albumart",
            smoke_audio["1s"],
            ["--mode", "albumart", "--image", TEST_IMAGE],
        )

    @pytest.mark.parametrize("fmt", ["mkv", "webm"])
    def test_smoke_format(self, tmp_path, smoke_audio, fmt):
        """Smoke keeps at least one encode per output format (sec.4.2).

        mp4 is already covered by the per-visualizer encodes; WebM needs
        the libvpx-vp9 encoder, so it is skipped where the ffmpeg build
        lacks one (same guard as TestE2ESpectrum.test_spectrum_webm).
        """
        if fmt == "webm" and not _has_vpx_encoder():
            pytest.skip("ffmpeg build has no libvpx-vp9 encoder")
        self._encode(tmp_path, f"format_{fmt}", smoke_audio["1s"], ["--mode", "spectrum"], fmt=fmt)


@pytest.mark.e2e
class TestThemePreviews:
    """--list-themes --png DIR renders real preview PNGs (v2.2.0 sec.3.3)."""

    def test_renders_builtin_and_user_previews(self, tmp_path, monkeypatch):
        from unittest.mock import patch

        from audio_visualizer.__main__ import main

        monkeypatch.setenv("HOME", str(tmp_path))
        themes_dir = tmp_path / ".config" / "audio-visualizer" / "themes"
        themes_dir.mkdir(parents=True)
        (themes_dir / "e2emix.json").write_text('{"palette": ["red", "cyan"]}')

        out_dir = tmp_path / "previews"
        with patch(
            "sys.argv",
            ["audio-visualizer", "--list-themes", "--png", str(out_dir)],
        ):
            main()

        files = sorted(p.name for p in out_dir.glob("*.png"))
        # 6 built-ins + the user theme
        assert len(files) == 7, files
        assert "neon_preview.png" in files
        assert "e2emix_preview.png" in files
        for name in files:
            size = (out_dir / name).stat().st_size
            assert size > 500, f"preview {name} is suspiciously small: {size} B"

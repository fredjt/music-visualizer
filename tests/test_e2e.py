"""End-to-end integration tests for audio visualizer.

These tests run the actual CLI with different arguments and verify
that output files are created correctly with different plugins,
resolutions, formats, and options.
"""

import os

import pytest

# Test audio files
TEST_AUDIO = os.path.join(os.path.dirname(__file__), "assets", "test.mp3")
TEST_STEREO = os.path.join(os.path.dirname(__file__), "assets", "test.wav")
TEST_MONO = os.path.join(os.path.dirname(__file__), "assets", "mono.mp3")
TEST_IMAGE = os.path.join(os.path.dirname(__file__), "assets", "album.jpg")


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

    @pytest.mark.skip(reason="WebM requires VP8/VP9/AV1 which need different encoder setup")
    def test_spectrum_webm(self, tmp_path):
        """Test spectrum output as WebM."""
        from unittest.mock import patch

        from audio_visualizer.__main__ import main

        output = str(tmp_path / "output.webm")
        with patch(
            "sys.argv",
            ["audio-visualizer", TEST_AUDIO, "-o", output, "-f", "webm", "--accel", "disabled"],
        ):
            main()
        assert os.path.exists(output)
        assert os.path.getsize(output) > 0


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
            with pytest.raises(FileNotFoundError):
                main()

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

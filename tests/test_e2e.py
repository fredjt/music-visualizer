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

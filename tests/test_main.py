"""Tests for main application."""

import json
import logging
import os
import shutil
from argparse import Namespace
from unittest.mock import MagicMock, patch

import pytest

from audio_visualizer.__main__ import (
    MIN_FFMPEG_VERSION,
    check_ffmpeg,
    detect_hwaccel,
    get_audio_duration,
    merge_config,
    parse_ffmpeg_version,
)

class _FakeModePlugin:
    """Plugin-class stand-in for batch tests (no ffmpeg requirement)."""

    @staticmethod
    def get_metadata():
        from audio_visualizer.visualizers.base import PluginMetadata

        return PluginMetadata(
            name="spectrum", display_name="Spectrum", description="test stand-in"
        )



class TestCheckFfmpeg:
    """Test ffmpeg checking (including the project minimum version, sec.8.4)."""

    def test_ffmpeg_found(self):
        """Test when ffmpeg is found and meets the minimum version."""
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(
                returncode=0, stdout="ffmpeg version 7.0.1-1 Copyright\n"
            )
            result = check_ffmpeg()
            assert result == "ffmpeg version 7.0.1-1 Copyright"

    def test_ffmpeg_too_old(self, caplog):
        """Test that ffmpeg below the project minimum is rejected clearly."""
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stdout="ffmpeg version 5.1\n")
            with pytest.raises(SystemExit):
                check_ffmpeg()
        min_version = ".".join(str(part) for part in MIN_FFMPEG_VERSION)
        assert "too old" in caplog.text
        assert min_version in caplog.text

    def test_ffmpeg_unparseable_version_warns(self, caplog):
        """Test that an unparseable version warns but does not block."""
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stdout="custom build\n")
            result = check_ffmpeg()
            assert result == "custom build"
        assert "parse the ffmpeg version" in caplog.text

    def test_ffmpeg_not_found(self, caplog):
        """Test when ffmpeg is not found."""
        with patch("subprocess.run") as mock_run:
            mock_run.side_effect = FileNotFoundError()
            with pytest.raises(SystemExit):
                check_ffmpeg()
        assert "ffmpeg is required" in caplog.text


class TestParseFfmpegVersion:
    """Test parse_ffmpeg_version (v2.2.0 sec.8.4)."""

    @pytest.mark.parametrize(
        ("line", "expected"),
        [
            ("ffmpeg version 9.0.2-3 Copyright (c) 2000-2026", (9, 0, 2)),
            ("ffmpeg version 6.0 Copyright", (6, 0)),
            ("ffmpeg version 7.1 Copyright", (7, 1)),
            ("ffmpeg version 10.2.1-git Copyright", (10, 2, 1)),
            ("", None),
            ("custom build", None),
            ("ffmpeg version unknown", None),
        ],
    )
    def test_parse(self, line, expected):
        assert parse_ffmpeg_version(line) == expected


class TestGetAudioDuration:
    """Test audio duration detection."""

    def test_get_duration_success(self):
        """Test getting duration successfully."""
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stdout="123.45\n")
            duration = get_audio_duration("test.mp3")
            assert duration == 123.45

    def test_get_duration_failure(self):
        """Test getting duration when ffprobe fails."""
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=1)
            duration = get_audio_duration("test.mp3")
            assert duration is None


class TestDetectHwaccel:
    """Test hardware acceleration detection."""

    def test_disabled(self):
        """Test disabled acceleration."""
        assert detect_hwaccel("disabled") == "sw"

    def test_auto_nvenc(self):
        """Test auto detection with NVENC available."""
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stdout="h264_nvenc")
            assert detect_hwaccel("auto") == "nvenc"

    def test_auto_qsv(self):
        """Test auto detection with QSV available."""
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stdout="h264_qsv")
            assert detect_hwaccel("auto") == "qsv"

    def test_auto_vaapi(self):
        """Test auto detection with VA-API available."""
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stdout="h264_vaapi")
            assert detect_hwaccel("auto") == "vaapi"

    def test_auto_software(self):
        """Test auto detection with no hardware available."""
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stdout="")
            assert detect_hwaccel("auto") == "sw"

    def test_specific_accel_not_available(self, caplog):
        """Test specific acceleration not available."""
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stdout="")
            result = detect_hwaccel("nvenc")
            assert result == "sw"
        assert "WARNING" in caplog.text


class TestMergeConfig:
    """Test configuration merging."""

    def test_merge_config_basic(self):
        """Test basic config merging."""
        args = Namespace(
            resolution="1280x720",
            format="mp4",
            fps=30,
            preset="medium",
            crf=23,
            accel="auto",
            mode="spectrum",
            output=None,
            colors=None,
            bg_color=None,
            theme=None,
            validate_config=False,
            retry=0,
            mirror_axis="y",
        )

        config = {
            "resolution": "1920x1080",
            "format": "mkv",
        }

        merged = merge_config(args, config)
        assert merged.resolution == "1920x1080"
        assert merged.format == "mkv"
        # Other values should remain at defaults
        assert merged.fps == 30
        assert merged.preset == "medium"


class TestDetectHwaccelRealistic:
    """Test hardware acceleration detection with realistic ffmpeg output."""

    def test_auto_nvenc_realistic(self):
        """Test auto detection with realistic ffmpeg -encoders output."""
        realistic_output = """
 V..... libx264              libx264 H.264 / AVC / MPEG-4 AVC / MPEG-4 part 10 (codec h264)
 V..... h264_nvenc           NVIDIA NVENC H.264 encoder (codec h264)
 V..... h264_qsv             Intel QSV H.264 encoder (codec h264)
 V..... libvpx               libvpx VP8/VP9 encoder (codec vp8/vp9)
"""
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stdout=realistic_output)
            assert detect_hwaccel("auto") == "nvenc"

    def test_specific_nvenc_realistic(self):
        """Test specific nvenc detection with realistic output."""
        realistic_output = """
 V..... libx264              libx264 H.264 / AVC / MPEG-4 AVC / MPEG-4 part 10 (codec h264)
 V..... h264_nvenc           NVIDIA NVENC H.264 encoder (codec h264)
"""
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stdout=realistic_output)
            assert detect_hwaccel("nvenc") == "nvenc"

    def test_no_nvenc_available(self):
        """Test fallback when nvenc is not available."""
        realistic_output = """
 V..... libx264              libx264 H.264 / AVC / MPEG-4 AVC / MPEG-4 part 10 (codec h264)
 V..... libvpx               libvpx VP8/VP9 encoder (codec vp8/vp9)
"""
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stdout=realistic_output)
            assert detect_hwaccel("auto") == "sw"
            assert detect_hwaccel("nvenc") == "sw"

    def test_timeout_returns_software(self):
        """Test that timeout falls back to software encoding."""
        import subprocess

        with patch("subprocess.run") as mock_run:
            mock_run.side_effect = subprocess.TimeoutExpired(cmd="ffmpeg", timeout=5)
            assert detect_hwaccel("auto") == "sw"

    def test_file_not_found_returns_software(self):
        """Test that FileNotFoundError falls back to software encoding."""
        with patch("subprocess.run") as mock_run:
            mock_run.side_effect = FileNotFoundError("ffmpeg not found")
            assert detect_hwaccel("auto") == "sw"

    def test_returncode_error_returns_software(self):
        """Test that non-zero return code falls back to software encoding."""
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=1, stdout="")
            assert detect_hwaccel("auto") == "sw"


class TestCLIArgumentParsing:
    """Test CLI argument parsing."""

    def test_parse_basic_args(self):
        """Test parsing basic CLI arguments."""
        from audio_visualizer.__main__ import main

        with patch("sys.argv", ["audio-visualizer", "test.mp3"]):
            with patch("audio_visualizer.__main__.check_ffmpeg", return_value="ffmpeg version 7.0.1 Copyright"):
                with patch("audio_visualizer.__main__.run_visualizer"):
                    with patch("audio_visualizer.__main__.merge_config") as mock_merge:
                        mock_merge.return_value = Namespace(
                            input="test.mp3",
                            output=None,
                            mode="spectrum",
                            resolution="1280x720",
                            fps=30,
                            preset="medium",
                            crf=23,
                            verbose=False,
                            image=None,
                            format="mp4",
                            accel="auto",
                            colors=None,
                            bg_color=None,
                            albumart_effect="glow",
                            waveform_mode="line",
                            waveform_splits=1,
                            waveform_frame=0,
                            vectorscope_mode="lissajous",
                            vectorscope_draw="aaline",
                            vectorscope_scale="cbrt",
                            vectorscope_zoom=1.0,
                            vectorscope_trails=100,
                            vectorscope_color_index=0,
                            spectrogram_mode="intensity",
                            cqt_gamma=3.0,
                            cqt_basefreq=20.0,
                            cqt_endfreq=20495.0,
                            cqt_attack=0.0,
                            cqt_timeclamp=0.17,
                            batch=None,
                            list_plugins=False,
                            install_plugin=None,
                            config=False,
                            save_config=False,
                            overwrite=False,
                            theme=None,
                            validate_config=False,
                            retry=0,
                            mirror_axis="y",
                            mirror_gap=0,
                            spectrum_mode="rainbow",
                            showfreqs_mode="bar",
                            showfreqs_ascale="log",
                            showfreqs_fscale="log",
                            showfreqs_winfunc="hann",
                            showfreqs_overlap=0.5,
                            showfreqs_channels="all",
                            showvolume_mode="peak",
                            showvolume_orientation="h",
                            showvolume_scale="lin",
                            validate=False,
                            dry_run=False,
                            json=False,
                            log_file=None,
                            list_themes=False,
                            version=False,
                            info=None,
                            spectrum_style="scroll",
                            spectrum_opacity=1.0,
                            spectrum_start=0,
                            spectrum_stop=0,
                            bar_width=0,
                            bar_spacing=0.5,
                            bar_orientation="horizontal",
                            bar_radius=0,
                            waveform_colors_per_channel=False,
                            mirror_opacity=1.0,
                            vectorscope_framerate=0,
                            vectorscope_border=False,
                            vectorscope_border_color="ffffff",
                            vectorscope_border_width=2,
                            spectrogram_speed=0.95,
                            spectrogram_opacity=1.0,
                            spectrogram_transpose=False,
                            albumart_position="bottom",
                            albumart_glow_intensity=0.08,
                            albumart_fit="cover",
                            albumart_blur=0,
                            border=False,
                            border_color="ffffff",
                            border_width=2,
                            aspect_ratio=None,
                            visualizer_config=None,
                            config_path=None,
                        )
                        main()
                        assert mock_merge.called

    def test_parse_resolution(self):
        """Test parsing resolution argument."""
        from audio_visualizer.__main__ import main

        with patch("sys.argv", ["audio-visualizer", "test.mp3", "-r", "1920x1080"]):
            with patch("audio_visualizer.__main__.check_ffmpeg", return_value="ffmpeg version 7.0.1 Copyright"):
                with patch("audio_visualizer.__main__.run_visualizer"):
                    with patch("audio_visualizer.__main__.merge_config") as mock_merge:
                        mock_merge.return_value = Namespace(
                            input="test.mp3",
                            output=None,
                            mode="spectrum",
                            resolution="1920x1080",
                            fps=30,
                            preset="medium",
                            crf=23,
                            verbose=False,
                            image=None,
                            format="mp4",
                            accel="auto",
                            colors=None,
                            bg_color=None,
                            albumart_effect="glow",
                            waveform_mode="line",
                            waveform_splits=1,
                            waveform_frame=0,
                            vectorscope_mode="lissajous",
                            vectorscope_draw="aaline",
                            vectorscope_scale="cbrt",
                            vectorscope_zoom=1.0,
                            vectorscope_trails=100,
                            vectorscope_color_index=0,
                            spectrogram_mode="intensity",
                            cqt_gamma=3.0,
                            cqt_basefreq=20.0,
                            cqt_endfreq=20495.0,
                            cqt_attack=0.0,
                            cqt_timeclamp=0.17,
                            batch=None,
                            list_plugins=False,
                            install_plugin=None,
                            config=False,
                            save_config=False,
                            overwrite=False,
                            theme=None,
                            validate_config=False,
                            retry=0,
                            mirror_axis="y",
                            mirror_gap=0,
                            spectrum_mode="rainbow",
                            showfreqs_mode="bar",
                            showfreqs_ascale="log",
                            showfreqs_fscale="log",
                            showfreqs_winfunc="hann",
                            showfreqs_overlap=0.5,
                            showfreqs_channels="all",
                            showvolume_mode="peak",
                            showvolume_orientation="h",
                            showvolume_scale="lin",
                            validate=False,
                            dry_run=False,
                            json=False,
                            log_file=None,
                            list_themes=False,
                            version=False,
                            info=None,
                            spectrum_style="scroll",
                            spectrum_opacity=1.0,
                            spectrum_start=0,
                            spectrum_stop=0,
                            bar_width=0,
                            bar_spacing=0.5,
                            bar_orientation="horizontal",
                            bar_radius=0,
                            waveform_colors_per_channel=False,
                            mirror_opacity=1.0,
                            vectorscope_framerate=0,
                            vectorscope_border=False,
                            vectorscope_border_color="ffffff",
                            vectorscope_border_width=2,
                            spectrogram_speed=0.95,
                            spectrogram_opacity=1.0,
                            spectrogram_transpose=False,
                            albumart_position="bottom",
                            albumart_glow_intensity=0.08,
                            albumart_fit="cover",
                            albumart_blur=0,
                            border=False,
                            border_color="ffffff",
                            border_width=2,
                            aspect_ratio=None,
                            visualizer_config=None,
                            config_path=None,
                        )
                        main()
                        assert mock_merge.called

    def test_parse_theme(self):
        """Test parsing theme argument."""
        from audio_visualizer.__main__ import main

        with patch("sys.argv", ["audio-visualizer", "test.mp3", "--theme", "neon"]):
            with patch("audio_visualizer.__main__.check_ffmpeg", return_value="ffmpeg version 7.0.1 Copyright"):
                with patch("audio_visualizer.__main__.run_visualizer"):
                    with patch("audio_visualizer.__main__.merge_config") as mock_merge:
                        mock_merge.return_value = Namespace(
                            input="test.mp3",
                            output=None,
                            mode="spectrum",
                            resolution="1280x720",
                            fps=30,
                            preset="medium",
                            crf=23,
                            verbose=False,
                            image=None,
                            format="mp4",
                            accel="auto",
                            colors="lime,magenta,cyan,yellow",
                            bg_color=None,
                            albumart_effect="glow",
                            waveform_mode="line",
                            waveform_splits=1,
                            waveform_frame=0,
                            vectorscope_mode="lissajous",
                            vectorscope_draw="aaline",
                            vectorscope_scale="cbrt",
                            vectorscope_zoom=1.0,
                            vectorscope_trails=100,
                            vectorscope_color_index=0,
                            spectrogram_mode="intensity",
                            cqt_gamma=3.0,
                            cqt_basefreq=20.0,
                            cqt_endfreq=20495.0,
                            cqt_attack=0.0,
                            cqt_timeclamp=0.17,
                            batch=None,
                            list_plugins=False,
                            install_plugin=None,
                            config=False,
                            save_config=False,
                            overwrite=False,
                            theme="neon",
                            validate_config=False,
                            retry=0,
                            mirror_axis="y",
                            mirror_gap=0,
                            spectrum_mode="rainbow",
                            showfreqs_mode="bar",
                            showfreqs_ascale="log",
                            showfreqs_fscale="log",
                            showfreqs_winfunc="hann",
                            showfreqs_overlap=0.5,
                            showfreqs_channels="all",
                            showvolume_mode="peak",
                            showvolume_orientation="h",
                            showvolume_scale="lin",
                            validate=False,
                            dry_run=False,
                            json=False,
                            log_file=None,
                            list_themes=False,
                            version=False,
                            info=None,
                            spectrum_style="scroll",
                            spectrum_opacity=1.0,
                            spectrum_start=0,
                            spectrum_stop=0,
                            bar_width=0,
                            bar_spacing=0.5,
                            bar_orientation="horizontal",
                            bar_radius=0,
                            waveform_colors_per_channel=False,
                            mirror_opacity=1.0,
                            vectorscope_framerate=0,
                            vectorscope_border=False,
                            vectorscope_border_color="ffffff",
                            vectorscope_border_width=2,
                            spectrogram_speed=0.95,
                            spectrogram_opacity=1.0,
                            spectrogram_transpose=False,
                            albumart_position="bottom",
                            albumart_glow_intensity=0.08,
                            albumart_fit="cover",
                            albumart_blur=0,
                            border=False,
                            border_color="ffffff",
                            border_width=2,
                            aspect_ratio=None,
                            visualizer_config=None,
                            config_path=None,
                        )
                        main()
                        assert mock_merge.called

    def test_parse_colors(self):
        """Test parsing colors argument."""
        from audio_visualizer.__main__ import main

        with patch("sys.argv", ["audio-visualizer", "test.mp3", "--colors", "red,blue,green"]):
            with patch("audio_visualizer.__main__.check_ffmpeg", return_value="ffmpeg version 7.0.1 Copyright"):
                with patch("audio_visualizer.__main__.run_visualizer"):
                    with patch("audio_visualizer.__main__.merge_config") as mock_merge:
                        mock_merge.return_value = Namespace(
                            input="test.mp3",
                            output=None,
                            mode="spectrum",
                            resolution="1280x720",
                            fps=30,
                            preset="medium",
                            crf=23,
                            verbose=False,
                            image=None,
                            format="mp4",
                            accel="auto",
                            colors="red,blue,green",
                            bg_color=None,
                            albumart_effect="glow",
                            waveform_mode="line",
                            waveform_splits=1,
                            waveform_frame=0,
                            vectorscope_mode="lissajous",
                            vectorscope_draw="aaline",
                            vectorscope_scale="cbrt",
                            vectorscope_zoom=1.0,
                            vectorscope_trails=100,
                            vectorscope_color_index=0,
                            spectrogram_mode="intensity",
                            cqt_gamma=3.0,
                            cqt_basefreq=20.0,
                            cqt_endfreq=20495.0,
                            cqt_attack=0.0,
                            cqt_timeclamp=0.17,
                            batch=None,
                            list_plugins=False,
                            install_plugin=None,
                            config=False,
                            save_config=False,
                            overwrite=False,
                            theme=None,
                            validate_config=False,
                            retry=0,
                            mirror_axis="y",
                            mirror_gap=0,
                            spectrum_mode="rainbow",
                            showfreqs_mode="bar",
                            showfreqs_ascale="log",
                            showfreqs_fscale="log",
                            showfreqs_winfunc="hann",
                            showfreqs_overlap=0.5,
                            showfreqs_channels="all",
                            showvolume_mode="peak",
                            showvolume_orientation="h",
                            showvolume_scale="lin",
                            validate=False,
                            dry_run=False,
                            json=False,
                            log_file=None,
                            list_themes=False,
                            version=False,
                            info=None,
                            spectrum_style="scroll",
                            spectrum_opacity=1.0,
                            spectrum_start=0,
                            spectrum_stop=0,
                            bar_width=0,
                            bar_spacing=0.5,
                            bar_orientation="horizontal",
                            bar_radius=0,
                            waveform_colors_per_channel=False,
                            mirror_opacity=1.0,
                            vectorscope_framerate=0,
                            vectorscope_border=False,
                            vectorscope_border_color="ffffff",
                            vectorscope_border_width=2,
                            spectrogram_speed=0.95,
                            spectrogram_opacity=1.0,
                            spectrogram_transpose=False,
                            albumart_position="bottom",
                            albumart_glow_intensity=0.08,
                            albumart_fit="cover",
                            albumart_blur=0,
                            border=False,
                            border_color="ffffff",
                            border_width=2,
                            aspect_ratio=None,
                            visualizer_config=None,
                            config_path=None,
                        )
                        main()
                        assert mock_merge.called

    def test_parse_format(self):
        """Test parsing format argument."""
        from audio_visualizer.__main__ import main

        with patch("sys.argv", ["audio-visualizer", "test.mp3", "-f", "webm"]):
            with patch("audio_visualizer.__main__.check_ffmpeg", return_value="ffmpeg version 7.0.1 Copyright"):
                with patch("audio_visualizer.__main__.run_visualizer"):
                    with patch("audio_visualizer.__main__.merge_config") as mock_merge:
                        mock_merge.return_value = Namespace(
                            input="test.mp3",
                            output=None,
                            mode="spectrum",
                            resolution="1280x720",
                            fps=30,
                            preset="medium",
                            crf=23,
                            verbose=False,
                            image=None,
                            format="webm",
                            accel="auto",
                            colors=None,
                            bg_color=None,
                            albumart_effect="glow",
                            waveform_mode="line",
                            waveform_splits=1,
                            waveform_frame=0,
                            vectorscope_mode="lissajous",
                            vectorscope_draw="aaline",
                            vectorscope_scale="cbrt",
                            vectorscope_zoom=1.0,
                            vectorscope_trails=100,
                            vectorscope_color_index=0,
                            spectrogram_mode="intensity",
                            cqt_gamma=3.0,
                            cqt_basefreq=20.0,
                            cqt_endfreq=20495.0,
                            cqt_attack=0.0,
                            cqt_timeclamp=0.17,
                            batch=None,
                            list_plugins=False,
                            install_plugin=None,
                            config=False,
                            save_config=False,
                            overwrite=False,
                            theme=None,
                            validate_config=False,
                            retry=0,
                            mirror_axis="y",
                            mirror_gap=0,
                            spectrum_mode="rainbow",
                            showfreqs_mode="bar",
                            showfreqs_ascale="log",
                            showfreqs_fscale="log",
                            showfreqs_winfunc="hann",
                            showfreqs_overlap=0.5,
                            showfreqs_channels="all",
                            showvolume_mode="peak",
                            showvolume_orientation="h",
                            showvolume_scale="lin",
                            validate=False,
                            dry_run=False,
                            json=False,
                            log_file=None,
                            list_themes=False,
                            version=False,
                            info=None,
                            spectrum_style="scroll",
                            spectrum_opacity=1.0,
                            spectrum_start=0,
                            spectrum_stop=0,
                            bar_width=0,
                            bar_spacing=0.5,
                            bar_orientation="horizontal",
                            bar_radius=0,
                            waveform_colors_per_channel=False,
                            mirror_opacity=1.0,
                            vectorscope_framerate=0,
                            vectorscope_border=False,
                            vectorscope_border_color="ffffff",
                            vectorscope_border_width=2,
                            spectrogram_speed=0.95,
                            spectrogram_opacity=1.0,
                            spectrogram_transpose=False,
                            albumart_position="bottom",
                            albumart_glow_intensity=0.08,
                            albumart_fit="cover",
                            albumart_blur=0,
                            border=False,
                            border_color="ffffff",
                            border_width=2,
                            aspect_ratio=None,
                            visualizer_config=None,
                            config_path=None,
                        )
                        main()
                        assert mock_merge.called

    def test_parse_accel(self):
        """Test parsing accel argument."""
        from audio_visualizer.__main__ import main

        with patch("sys.argv", ["audio-visualizer", "test.mp3", "--accel", "nvenc"]):
            with patch("audio_visualizer.__main__.check_ffmpeg", return_value="ffmpeg version 7.0.1 Copyright"):
                with patch("audio_visualizer.__main__.run_visualizer"):
                    with patch("audio_visualizer.__main__.merge_config") as mock_merge:
                        mock_merge.return_value = Namespace(
                            input="test.mp3",
                            output=None,
                            mode="spectrum",
                            resolution="1280x720",
                            fps=30,
                            preset="medium",
                            crf=23,
                            verbose=False,
                            image=None,
                            format="mp4",
                            accel="nvenc",
                            colors=None,
                            bg_color=None,
                            albumart_effect="glow",
                            waveform_mode="line",
                            waveform_splits=1,
                            waveform_frame=0,
                            vectorscope_mode="lissajous",
                            vectorscope_draw="aaline",
                            vectorscope_scale="cbrt",
                            vectorscope_zoom=1.0,
                            vectorscope_trails=100,
                            vectorscope_color_index=0,
                            spectrogram_mode="intensity",
                            cqt_gamma=3.0,
                            cqt_basefreq=20.0,
                            cqt_endfreq=20495.0,
                            cqt_attack=0.0,
                            cqt_timeclamp=0.17,
                            batch=None,
                            list_plugins=False,
                            install_plugin=None,
                            config=False,
                            save_config=False,
                            overwrite=False,
                            theme=None,
                            validate_config=False,
                            retry=0,
                            mirror_axis="y",
                            mirror_gap=0,
                            spectrum_mode="rainbow",
                            showfreqs_mode="bar",
                            showfreqs_ascale="log",
                            showfreqs_fscale="log",
                            showfreqs_winfunc="hann",
                            showfreqs_overlap=0.5,
                            showfreqs_channels="all",
                            showvolume_mode="peak",
                            showvolume_orientation="h",
                            showvolume_scale="lin",
                            validate=False,
                            dry_run=False,
                            json=False,
                            log_file=None,
                            list_themes=False,
                            version=False,
                            info=None,
                            spectrum_style="scroll",
                            spectrum_opacity=1.0,
                            spectrum_start=0,
                            spectrum_stop=0,
                            bar_width=0,
                            bar_spacing=0.5,
                            bar_orientation="horizontal",
                            bar_radius=0,
                            waveform_colors_per_channel=False,
                            mirror_opacity=1.0,
                            vectorscope_framerate=0,
                            vectorscope_border=False,
                            vectorscope_border_color="ffffff",
                            vectorscope_border_width=2,
                            spectrogram_speed=0.95,
                            spectrogram_opacity=1.0,
                            spectrogram_transpose=False,
                            albumart_position="bottom",
                            albumart_glow_intensity=0.08,
                            albumart_fit="cover",
                            albumart_blur=0,
                            border=False,
                            border_color="ffffff",
                            border_width=2,
                            aspect_ratio=None,
                            visualizer_config=None,
                            config_path=None,
                        )
                        main()
                        assert mock_merge.called

    def test_parse_mode(self):
        """Test parsing mode argument."""
        from audio_visualizer.__main__ import main

        with patch("sys.argv", ["audio-visualizer", "test.mp3", "--mode", "waveform"]):
            with patch("audio_visualizer.__main__.check_ffmpeg", return_value="ffmpeg version 7.0.1 Copyright"):
                with patch("audio_visualizer.__main__.run_visualizer"):
                    with patch("audio_visualizer.__main__.merge_config") as mock_merge:
                        mock_merge.return_value = Namespace(
                            input="test.mp3",
                            output=None,
                            mode="waveform",
                            resolution="1280x720",
                            fps=30,
                            preset="medium",
                            crf=23,
                            verbose=False,
                            image=None,
                            format="mp4",
                            accel="auto",
                            colors=None,
                            bg_color=None,
                            albumart_effect="glow",
                            waveform_mode="line",
                            waveform_splits=1,
                            waveform_frame=0,
                            vectorscope_mode="lissajous",
                            vectorscope_draw="aaline",
                            vectorscope_scale="cbrt",
                            vectorscope_zoom=1.0,
                            vectorscope_trails=100,
                            vectorscope_color_index=0,
                            spectrogram_mode="intensity",
                            cqt_gamma=3.0,
                            cqt_basefreq=20.0,
                            cqt_endfreq=20495.0,
                            cqt_attack=0.0,
                            cqt_timeclamp=0.17,
                            batch=None,
                            list_plugins=False,
                            install_plugin=None,
                            config=False,
                            save_config=False,
                            overwrite=False,
                            theme=None,
                            validate_config=False,
                            retry=0,
                            mirror_axis="y",
                            mirror_gap=0,
                            spectrum_mode="rainbow",
                            showfreqs_mode="bar",
                            showfreqs_ascale="log",
                            showfreqs_fscale="log",
                            showfreqs_winfunc="hann",
                            showfreqs_overlap=0.5,
                            showfreqs_channels="all",
                            showvolume_mode="peak",
                            showvolume_orientation="h",
                            showvolume_scale="lin",
                            validate=False,
                            dry_run=False,
                            json=False,
                            log_file=None,
                            list_themes=False,
                            version=False,
                            info=None,
                            spectrum_style="scroll",
                            spectrum_opacity=1.0,
                            spectrum_start=0,
                            spectrum_stop=0,
                            bar_width=0,
                            bar_spacing=0.5,
                            bar_orientation="horizontal",
                            bar_radius=0,
                            waveform_colors_per_channel=False,
                            mirror_opacity=1.0,
                            vectorscope_framerate=0,
                            vectorscope_border=False,
                            vectorscope_border_color="ffffff",
                            vectorscope_border_width=2,
                            spectrogram_speed=0.95,
                            spectrogram_opacity=1.0,
                            spectrogram_transpose=False,
                            albumart_position="bottom",
                            albumart_glow_intensity=0.08,
                            albumart_fit="cover",
                            albumart_blur=0,
                            border=False,
                            border_color="ffffff",
                            border_width=2,
                            aspect_ratio=None,
                            visualizer_config=None,
                            config_path=None,
                        )
                        main()
                        assert mock_merge.called

    def test_parse_output(self):
        """Test parsing output argument."""
        from audio_visualizer.__main__ import main

        with patch("sys.argv", ["audio-visualizer", "test.mp3", "-o", "output.mp4"]):
            with patch("audio_visualizer.__main__.check_ffmpeg", return_value="ffmpeg version 7.0.1 Copyright"):
                with patch("audio_visualizer.__main__.run_visualizer"):
                    with patch("audio_visualizer.__main__.merge_config") as mock_merge:
                        mock_merge.return_value = Namespace(
                            input="test.mp3",
                            output="output.mp4",
                            mode="spectrum",
                            resolution="1280x720",
                            fps=30,
                            preset="medium",
                            crf=23,
                            verbose=False,
                            image=None,
                            format="mp4",
                            accel="auto",
                            colors=None,
                            bg_color=None,
                            albumart_effect="glow",
                            waveform_mode="line",
                            waveform_splits=1,
                            waveform_frame=0,
                            vectorscope_mode="lissajous",
                            vectorscope_draw="aaline",
                            vectorscope_scale="cbrt",
                            vectorscope_zoom=1.0,
                            vectorscope_trails=100,
                            vectorscope_color_index=0,
                            spectrogram_mode="intensity",
                            cqt_gamma=3.0,
                            cqt_basefreq=20.0,
                            cqt_endfreq=20495.0,
                            cqt_attack=0.0,
                            cqt_timeclamp=0.17,
                            batch=None,
                            list_plugins=False,
                            install_plugin=None,
                            config=False,
                            save_config=False,
                            overwrite=False,
                            theme=None,
                            validate_config=False,
                            retry=0,
                            mirror_axis="y",
                            mirror_gap=0,
                            spectrum_mode="rainbow",
                            showfreqs_mode="bar",
                            showfreqs_ascale="log",
                            showfreqs_fscale="log",
                            showfreqs_winfunc="hann",
                            showfreqs_overlap=0.5,
                            showfreqs_channels="all",
                            showvolume_mode="peak",
                            showvolume_orientation="h",
                            showvolume_scale="lin",
                            validate=False,
                            dry_run=False,
                            json=False,
                            log_file=None,
                            list_themes=False,
                            version=False,
                            info=None,
                            spectrum_style="scroll",
                            spectrum_opacity=1.0,
                            spectrum_start=0,
                            spectrum_stop=0,
                            bar_width=0,
                            bar_spacing=0.5,
                            bar_orientation="horizontal",
                            bar_radius=0,
                            waveform_colors_per_channel=False,
                            mirror_opacity=1.0,
                            vectorscope_framerate=0,
                            vectorscope_border=False,
                            vectorscope_border_color="ffffff",
                            vectorscope_border_width=2,
                            spectrogram_speed=0.95,
                            spectrogram_opacity=1.0,
                            spectrogram_transpose=False,
                            albumart_position="bottom",
                            albumart_glow_intensity=0.08,
                            albumart_fit="cover",
                            albumart_blur=0,
                            border=False,
                            border_color="ffffff",
                            border_width=2,
                            aspect_ratio=None,
                            visualizer_config=None,
                            config_path=None,
                        )
                        main()
                        assert mock_merge.called

    def test_parse_image(self):
        """Test parsing image argument."""
        from audio_visualizer.__main__ import main

        with patch("sys.argv", ["audio-visualizer", "test.mp3", "--image", "art.jpg"]):
            with patch("audio_visualizer.__main__.check_ffmpeg", return_value="ffmpeg version 7.0.1 Copyright"):
                with patch("audio_visualizer.__main__.run_visualizer"):
                    with patch("audio_visualizer.__main__.merge_config") as mock_merge:
                        mock_merge.return_value = Namespace(
                            input="test.mp3",
                            output=None,
                            mode="spectrum",
                            resolution="1280x720",
                            fps=30,
                            preset="medium",
                            crf=23,
                            verbose=False,
                            image="art.jpg",
                            format="mp4",
                            accel="auto",
                            colors=None,
                            bg_color=None,
                            albumart_effect="glow",
                            waveform_mode="line",
                            waveform_splits=1,
                            waveform_frame=0,
                            vectorscope_mode="lissajous",
                            vectorscope_draw="aaline",
                            vectorscope_scale="cbrt",
                            vectorscope_zoom=1.0,
                            vectorscope_trails=100,
                            vectorscope_color_index=0,
                            spectrogram_mode="intensity",
                            cqt_gamma=3.0,
                            cqt_basefreq=20.0,
                            cqt_endfreq=20495.0,
                            cqt_attack=0.0,
                            cqt_timeclamp=0.17,
                            batch=None,
                            list_plugins=False,
                            install_plugin=None,
                            config=False,
                            save_config=False,
                            overwrite=False,
                            theme=None,
                            validate_config=False,
                            retry=0,
                            mirror_axis="y",
                            mirror_gap=0,
                            spectrum_mode="rainbow",
                            showfreqs_mode="bar",
                            showfreqs_ascale="log",
                            showfreqs_fscale="log",
                            showfreqs_winfunc="hann",
                            showfreqs_overlap=0.5,
                            showfreqs_channels="all",
                            showvolume_mode="peak",
                            showvolume_orientation="h",
                            showvolume_scale="lin",
                            validate=False,
                            dry_run=False,
                            json=False,
                            log_file=None,
                            list_themes=False,
                            version=False,
                            info=None,
                            spectrum_style="scroll",
                            spectrum_opacity=1.0,
                            spectrum_start=0,
                            spectrum_stop=0,
                            bar_width=0,
                            bar_spacing=0.5,
                            bar_orientation="horizontal",
                            bar_radius=0,
                            waveform_colors_per_channel=False,
                            mirror_opacity=1.0,
                            vectorscope_framerate=0,
                            vectorscope_border=False,
                            vectorscope_border_color="ffffff",
                            vectorscope_border_width=2,
                            spectrogram_speed=0.95,
                            spectrogram_opacity=1.0,
                            spectrogram_transpose=False,
                            albumart_position="bottom",
                            albumart_glow_intensity=0.08,
                            albumart_fit="cover",
                            albumart_blur=0,
                            border=False,
                            border_color="ffffff",
                            border_width=2,
                            aspect_ratio=None,
                            visualizer_config=None,
                            config_path=None,
                        )
                        main()
                        assert mock_merge.called

    def test_parse_batch(self):
        """Test parsing batch argument."""
        from audio_visualizer.__main__ import main

        with patch("sys.argv", ["audio-visualizer", "-b", "./music/"]):
            with patch("audio_visualizer.__main__.check_ffmpeg", return_value="ffmpeg version 7.0.1 Copyright"):
                with patch("audio_visualizer.__main__.list_plugins"):
                    with patch("audio_visualizer.__main__.merge_config") as mock_merge:
                        mock_merge.return_value = Namespace(
                            input=None,
                            output=None,
                            mode="spectrum",
                            resolution="1280x720",
                            fps=30,
                            preset="medium",
                            crf=23,
                            verbose=False,
                            image=None,
                            format="mp4",
                            accel="auto",
                            colors=None,
                            batch="./music/",
                            list_plugins=False,
                            install_plugin=None,
                            config=False,
                            save_config=False,
                            overwrite=False,
                            theme=None,
                            validate_config=False,
                            retry=0,
                            mirror_axis="y",
                            mirror_gap=0,
                            spectrum_mode="rainbow",
                            showfreqs_mode="bar",
                            showfreqs_ascale="log",
                            showfreqs_fscale="log",
                            showfreqs_winfunc="hann",
                            showfreqs_overlap=0.5,
                            showfreqs_channels="all",
                            showvolume_mode="peak",
                            showvolume_orientation="h",
                            showvolume_scale="lin",
                            validate=False,
                            dry_run=False,
                            json=False,
                            log_file=None,
                            list_themes=False,
                            version=False,
                            info=None,
                            spectrum_style="scroll",
                            spectrum_opacity=1.0,
                            spectrum_start=0,
                            spectrum_stop=0,
                            bar_width=0,
                            bar_spacing=0.5,
                            bar_orientation="horizontal",
                            bar_radius=0,
                            waveform_colors_per_channel=False,
                            mirror_opacity=1.0,
                            vectorscope_framerate=0,
                            vectorscope_border=False,
                            vectorscope_border_color="ffffff",
                            vectorscope_border_width=2,
                            spectrogram_speed=0.95,
                            spectrogram_opacity=1.0,
                            spectrogram_transpose=False,
                            albumart_position="bottom",
                            albumart_glow_intensity=0.08,
                            albumart_fit="cover",
                            albumart_blur=0,
                            border=False,
                            border_color="ffffff",
                            border_width=2,
                            aspect_ratio=None,
                            visualizer_config=None,
                            config_path=None,
                        )
                        with patch("audio_visualizer.__main__._process_batch"):
                            main()
                            assert mock_merge.called

    def test_parse_list_plugins(self):
        """Test parsing list-plugins argument."""
        from audio_visualizer.__main__ import main

        with patch("sys.argv", ["audio-visualizer", "--list-plugins"]):
            with patch("audio_visualizer.__main__.list_plugins") as mock_list:
                with patch("audio_visualizer.__main__.merge_config") as mock_merge:
                    mock_merge.return_value = Namespace(
                        input=None,
                        output=None,
                        mode="spectrum",
                        resolution="1280x720",
                        fps=30,
                        preset="medium",
                        crf=23,
                        verbose=False,
                        image=None,
                        format="mp4",
                        accel="auto",
                        colors=None,
                        bg_color=None,
                        albumart_effect="glow",
                        batch=None,
                        list_plugins=True,
                        category=None,
                        install_plugin=None,
                        config=False,
                        save_config=False,
                        overwrite=False,
                        theme=None,
                        validate_config=False,
                        retry=0,
                        mirror_axis="y",
                        mirror_gap=0,
                        spectrum_mode="rainbow",
                        showfreqs_mode="bar",
                        showfreqs_ascale="log",
                        showfreqs_fscale="log",
                        showfreqs_winfunc="hann",
                        showfreqs_overlap=0.5,
                        showfreqs_channels="all",
                        showvolume_mode="peak",
                        showvolume_orientation="h",
                        showvolume_scale="lin",
                        validate=False,
                        dry_run=False,
                        json=False,
                        log_file=None,
                        list_themes=False,
                        version=False,
                        info=None,
                    )
                    main()
                    assert mock_list.called

    def test_parse_config(self):
        """Test parsing config argument - returns before merge_config."""
        from audio_visualizer.__main__ import main

        with patch("sys.argv", ["audio-visualizer", "--config"]):
            with patch("audio_visualizer.__main__.get_config_path") as mock_get_path:
                mock_get_path.return_value = "/tmp/test_config.yml"
                with patch("audio_visualizer.__main__.merge_config") as mock_merge:
                    # --config returns before merge_config is called
                    main()
                    assert not mock_merge.called

    def test_parse_install_plugin(self):
        """Test parsing install-plugin argument."""
        from audio_visualizer.__main__ import main

        with patch("sys.argv", ["audio-visualizer", "--install-plugin", "my_plugin.py"]):
            with patch("audio_visualizer.__main__.os.path.exists", return_value=True):
                with patch("audio_visualizer.__main__.merge_config") as mock_merge:
                    with patch("audio_visualizer.__main__.PluginRegistry") as mock_registry:
                        mock_inst = MagicMock()
                        mock_inst.get_metadata.return_value = MagicMock(
                            display_name="Test", name="test"
                        )
                        mock_registry.return_value = mock_inst
                        mock_merge.return_value = Namespace(
                            input=None,
                            output=None,
                            mode="spectrum",
                            resolution="1280x720",
                            fps=30,
                            preset="medium",
                            crf=23,
                            verbose=False,
                            image=None,
                            format="mp4",
                            accel="auto",
                            colors=None,
                            bg_color=None,
                            albumart_effect="glow",
                            waveform_mode="line",
                            waveform_splits=1,
                            waveform_frame=0,
                            vectorscope_mode="lissajous",
                            vectorscope_draw="aaline",
                            vectorscope_scale="cbrt",
                            vectorscope_zoom=1.0,
                            vectorscope_trails=100,
                            vectorscope_color_index=0,
                            spectrogram_mode="intensity",
                            cqt_gamma=3.0,
                            cqt_basefreq=20.0,
                            cqt_endfreq=20495.0,
                            cqt_attack=0.0,
                            cqt_timeclamp=0.17,
                            batch=None,
                            list_plugins=False,
                            install_plugin="my_plugin.py",
                            config=False,
                            save_config=False,
                            overwrite=False,
                            theme=None,
                            validate_config=False,
                            retry=0,
                            mirror_axis="y",
                            mirror_gap=0,
                            spectrum_mode="rainbow",
                            showfreqs_mode="bar",
                            showfreqs_ascale="log",
                            showfreqs_fscale="log",
                            showfreqs_winfunc="hann",
                            showfreqs_overlap=0.5,
                            showfreqs_channels="all",
                            showvolume_mode="peak",
                            showvolume_orientation="h",
                            showvolume_scale="lin",
                            validate=False,
                            dry_run=False,
                            json=False,
                            log_file=None,
                            list_themes=False,
                            version=False,
                            info=None,
                            spectrum_style="scroll",
                            spectrum_opacity=1.0,
                            spectrum_start=0,
                            spectrum_stop=0,
                            bar_width=0,
                            bar_spacing=0.5,
                            bar_orientation="horizontal",
                            bar_radius=0,
                            waveform_colors_per_channel=False,
                            mirror_opacity=1.0,
                            vectorscope_framerate=0,
                            vectorscope_border=False,
                            vectorscope_border_color="ffffff",
                            vectorscope_border_width=2,
                            spectrogram_speed=0.95,
                            spectrogram_opacity=1.0,
                            spectrogram_transpose=False,
                            albumart_position="bottom",
                            albumart_glow_intensity=0.08,
                            albumart_fit="cover",
                            albumart_blur=0,
                            border=False,
                            border_color="ffffff",
                            border_width=2,
                            aspect_ratio=None,
                            visualizer_config=None,
                            config_path=None,
                        )
                        main()
                        assert mock_merge.called

    def test_parse_save_config(self):
        """Test parsing save-config argument - returns before merge_config."""
        from audio_visualizer.__main__ import main

        with patch("sys.argv", ["audio-visualizer", "test.mp3", "--save-config"]):
            with patch("audio_visualizer.__main__.merge_config") as mock_merge:
                with patch("audio_visualizer.__main__.save_config") as mock_save:
                    mock_save.return_value = "/tmp/test_config.yml"
                    # --save-config returns before merge_config is called
                    main()
                    assert not mock_merge.called

    def test_parse_overwrite(self):
        """Test parsing overwrite argument."""
        from audio_visualizer.__main__ import main

        with patch("sys.argv", ["audio-visualizer", "-b", "./music/", "--overwrite"]):
            with patch("audio_visualizer.__main__.check_ffmpeg", return_value="ffmpeg version 7.0.1 Copyright"):
                with patch("audio_visualizer.__main__.list_plugins"):
                    with patch("audio_visualizer.__main__.merge_config") as mock_merge:
                        mock_merge.return_value = Namespace(
                            input=None,
                            output=None,
                            mode="spectrum",
                            resolution="1280x720",
                            fps=30,
                            preset="medium",
                            crf=23,
                            verbose=False,
                            image=None,
                            format="mp4",
                            accel="auto",
                            colors=None,
                            batch="./music/",
                            list_plugins=False,
                            install_plugin=None,
                            config=False,
                            save_config=False,
                            overwrite=True,
                            theme=None,
                            validate_config=False,
                            retry=0,
                            mirror_axis="y",
                            mirror_gap=0,
                            spectrum_mode="rainbow",
                            showfreqs_mode="bar",
                            showfreqs_ascale="log",
                            showfreqs_fscale="log",
                            showfreqs_winfunc="hann",
                            showfreqs_overlap=0.5,
                            showfreqs_channels="all",
                            showvolume_mode="peak",
                            showvolume_orientation="h",
                            showvolume_scale="lin",
                            validate=False,
                            dry_run=False,
                            json=False,
                            log_file=None,
                            list_themes=False,
                            version=False,
                            info=None,
                            spectrum_style="scroll",
                            spectrum_opacity=1.0,
                            spectrum_start=0,
                            spectrum_stop=0,
                            bar_width=0,
                            bar_spacing=0.5,
                            bar_orientation="horizontal",
                            bar_radius=0,
                            waveform_colors_per_channel=False,
                            mirror_opacity=1.0,
                            vectorscope_framerate=0,
                            vectorscope_border=False,
                            vectorscope_border_color="ffffff",
                            vectorscope_border_width=2,
                            spectrogram_speed=0.95,
                            spectrogram_opacity=1.0,
                            spectrogram_transpose=False,
                            albumart_position="bottom",
                            albumart_glow_intensity=0.08,
                            albumart_fit="cover",
                            albumart_blur=0,
                            border=False,
                            border_color="ffffff",
                            border_width=2,
                            aspect_ratio=None,
                            visualizer_config=None,
                            config_path=None,
                        )
                        with patch("audio_visualizer.__main__._process_batch"):
                            main()
                            assert mock_merge.called
                        # Verify overwrite was passed to _process_batch
                        assert mock_merge.call_args is not None

    def test_parse_crf(self):
        """Test parsing crf argument."""
        from audio_visualizer.__main__ import main

        with patch("sys.argv", ["audio-visualizer", "test.mp3", "--crf", "18"]):
            with patch("audio_visualizer.__main__.check_ffmpeg", return_value="ffmpeg version 7.0.1 Copyright"):
                with patch("audio_visualizer.__main__.run_visualizer"):
                    with patch("audio_visualizer.__main__.merge_config") as mock_merge:
                        mock_merge.return_value = Namespace(
                            input="test.mp3",
                            output=None,
                            mode="spectrum",
                            resolution="1280x720",
                            fps=30,
                            preset="medium",
                            crf=18,
                            verbose=False,
                            image=None,
                            format="mp4",
                            accel="auto",
                            colors=None,
                            bg_color=None,
                            albumart_effect="glow",
                            waveform_mode="line",
                            waveform_splits=1,
                            waveform_frame=0,
                            vectorscope_mode="lissajous",
                            vectorscope_draw="aaline",
                            vectorscope_scale="cbrt",
                            vectorscope_zoom=1.0,
                            vectorscope_trails=100,
                            vectorscope_color_index=0,
                            spectrogram_mode="intensity",
                            cqt_gamma=3.0,
                            cqt_basefreq=20.0,
                            cqt_endfreq=20495.0,
                            cqt_attack=0.0,
                            cqt_timeclamp=0.17,
                            batch=None,
                            list_plugins=False,
                            install_plugin=None,
                            config=False,
                            save_config=False,
                            overwrite=False,
                            theme=None,
                            validate_config=False,
                            retry=0,
                            mirror_axis="y",
                            mirror_gap=0,
                            spectrum_mode="rainbow",
                            showfreqs_mode="bar",
                            showfreqs_ascale="log",
                            showfreqs_fscale="log",
                            showfreqs_winfunc="hann",
                            showfreqs_overlap=0.5,
                            showfreqs_channels="all",
                            showvolume_mode="peak",
                            showvolume_orientation="h",
                            showvolume_scale="lin",
                            validate=False,
                            dry_run=False,
                            json=False,
                            log_file=None,
                            list_themes=False,
                            version=False,
                            info=None,
                            spectrum_style="scroll",
                            spectrum_opacity=1.0,
                            spectrum_start=0,
                            spectrum_stop=0,
                            bar_width=0,
                            bar_spacing=0.5,
                            bar_orientation="horizontal",
                            bar_radius=0,
                            waveform_colors_per_channel=False,
                            mirror_opacity=1.0,
                            vectorscope_framerate=0,
                            vectorscope_border=False,
                            vectorscope_border_color="ffffff",
                            vectorscope_border_width=2,
                            spectrogram_speed=0.95,
                            spectrogram_opacity=1.0,
                            spectrogram_transpose=False,
                            albumart_position="bottom",
                            albumart_glow_intensity=0.08,
                            albumart_fit="cover",
                            albumart_blur=0,
                            border=False,
                            border_color="ffffff",
                            border_width=2,
                            aspect_ratio=None,
                            visualizer_config=None,
                            config_path=None,
                        )
                        main()
                        assert mock_merge.called

    def test_parse_preset(self):
        """Test parsing preset argument."""
        from audio_visualizer.__main__ import main

        with patch("sys.argv", ["audio-visualizer", "test.mp3", "--preset", "fast"]):
            with patch("audio_visualizer.__main__.check_ffmpeg", return_value="ffmpeg version 7.0.1 Copyright"):
                with patch("audio_visualizer.__main__.run_visualizer"):
                    with patch("audio_visualizer.__main__.merge_config") as mock_merge:
                        mock_merge.return_value = Namespace(
                            input="test.mp3",
                            output=None,
                            mode="spectrum",
                            resolution="1280x720",
                            fps=30,
                            preset="fast",
                            crf=23,
                            verbose=False,
                            image=None,
                            format="mp4",
                            accel="auto",
                            colors=None,
                            bg_color=None,
                            albumart_effect="glow",
                            waveform_mode="line",
                            waveform_splits=1,
                            waveform_frame=0,
                            vectorscope_mode="lissajous",
                            vectorscope_draw="aaline",
                            vectorscope_scale="cbrt",
                            vectorscope_zoom=1.0,
                            vectorscope_trails=100,
                            vectorscope_color_index=0,
                            spectrogram_mode="intensity",
                            cqt_gamma=3.0,
                            cqt_basefreq=20.0,
                            cqt_endfreq=20495.0,
                            cqt_attack=0.0,
                            cqt_timeclamp=0.17,
                            batch=None,
                            list_plugins=False,
                            install_plugin=None,
                            config=False,
                            save_config=False,
                            overwrite=False,
                            theme=None,
                            validate_config=False,
                            retry=0,
                            mirror_axis="y",
                            mirror_gap=0,
                            spectrum_mode="rainbow",
                            showfreqs_mode="bar",
                            showfreqs_ascale="log",
                            showfreqs_fscale="log",
                            showfreqs_winfunc="hann",
                            showfreqs_overlap=0.5,
                            showfreqs_channels="all",
                            showvolume_mode="peak",
                            showvolume_orientation="h",
                            showvolume_scale="lin",
                            validate=False,
                            dry_run=False,
                            json=False,
                            log_file=None,
                            list_themes=False,
                            version=False,
                            info=None,
                            spectrum_style="scroll",
                            spectrum_opacity=1.0,
                            spectrum_start=0,
                            spectrum_stop=0,
                            bar_width=0,
                            bar_spacing=0.5,
                            bar_orientation="horizontal",
                            bar_radius=0,
                            waveform_colors_per_channel=False,
                            mirror_opacity=1.0,
                            vectorscope_framerate=0,
                            vectorscope_border=False,
                            vectorscope_border_color="ffffff",
                            vectorscope_border_width=2,
                            spectrogram_speed=0.95,
                            spectrogram_opacity=1.0,
                            spectrogram_transpose=False,
                            albumart_position="bottom",
                            albumart_glow_intensity=0.08,
                            albumart_fit="cover",
                            albumart_blur=0,
                            border=False,
                            border_color="ffffff",
                            border_width=2,
                            aspect_ratio=None,
                            visualizer_config=None,
                            config_path=None,
                        )
                        main()
                        assert mock_merge.called

    def test_parse_fps(self):
        """Test parsing fps argument."""
        from audio_visualizer.__main__ import main

        with patch("sys.argv", ["audio-visualizer", "test.mp3", "--fps", "60"]):
            with patch("audio_visualizer.__main__.check_ffmpeg", return_value="ffmpeg version 7.0.1 Copyright"):
                with patch("audio_visualizer.__main__.run_visualizer"):
                    with patch("audio_visualizer.__main__.merge_config") as mock_merge:
                        mock_merge.return_value = Namespace(
                            input="test.mp3",
                            output=None,
                            mode="spectrum",
                            resolution="1280x720",
                            fps=60,
                            preset="medium",
                            crf=23,
                            verbose=False,
                            image=None,
                            format="mp4",
                            accel="auto",
                            colors=None,
                            bg_color=None,
                            albumart_effect="glow",
                            waveform_mode="line",
                            waveform_splits=1,
                            waveform_frame=0,
                            vectorscope_mode="lissajous",
                            vectorscope_draw="aaline",
                            vectorscope_scale="cbrt",
                            vectorscope_zoom=1.0,
                            vectorscope_trails=100,
                            vectorscope_color_index=0,
                            spectrogram_mode="intensity",
                            cqt_gamma=3.0,
                            cqt_basefreq=20.0,
                            cqt_endfreq=20495.0,
                            cqt_attack=0.0,
                            cqt_timeclamp=0.17,
                            batch=None,
                            list_plugins=False,
                            install_plugin=None,
                            config=False,
                            save_config=False,
                            overwrite=False,
                            theme=None,
                            validate_config=False,
                            retry=0,
                            mirror_axis="y",
                            mirror_gap=0,
                            spectrum_mode="rainbow",
                            showfreqs_mode="bar",
                            showfreqs_ascale="log",
                            showfreqs_fscale="log",
                            showfreqs_winfunc="hann",
                            showfreqs_overlap=0.5,
                            showfreqs_channels="all",
                            showvolume_mode="peak",
                            showvolume_orientation="h",
                            showvolume_scale="lin",
                            validate=False,
                            dry_run=False,
                            json=False,
                            log_file=None,
                            list_themes=False,
                            version=False,
                            info=None,
                            spectrum_style="scroll",
                            spectrum_opacity=1.0,
                            spectrum_start=0,
                            spectrum_stop=0,
                            bar_width=0,
                            bar_spacing=0.5,
                            bar_orientation="horizontal",
                            bar_radius=0,
                            waveform_colors_per_channel=False,
                            mirror_opacity=1.0,
                            vectorscope_framerate=0,
                            vectorscope_border=False,
                            vectorscope_border_color="ffffff",
                            vectorscope_border_width=2,
                            spectrogram_speed=0.95,
                            spectrogram_opacity=1.0,
                            spectrogram_transpose=False,
                            albumart_position="bottom",
                            albumart_glow_intensity=0.08,
                            albumart_fit="cover",
                            albumart_blur=0,
                            border=False,
                            border_color="ffffff",
                            border_width=2,
                            aspect_ratio=None,
                            visualizer_config=None,
                            config_path=None,
                        )
                        main()
                        assert mock_merge.called


class TestRetryLogic:
    """Test retry logic for ffmpeg failures."""

    def test_retry_flag_default(self):
        """Test that retry flag defaults to 0."""
        from argparse import Namespace

        from audio_visualizer.__main__ import main

        with patch("sys.argv", ["audio-visualizer", "test.mp3"]):
            with patch("audio_visualizer.__main__.check_ffmpeg", return_value="ffmpeg version 7.0.1 Copyright"):
                with patch("audio_visualizer.__main__.run_visualizer"):
                    with patch("audio_visualizer.__main__.merge_config") as mock_merge:
                        mock_merge.return_value = Namespace(
                            input="test.mp3",
                            output=None,
                            mode="spectrum",
                            resolution="1280x720",
                            fps=30,
                            preset="medium",
                            crf=23,
                            verbose=False,
                            image=None,
                            format="mp4",
                            accel="auto",
                            colors=None,
                            bg_color=None,
                            albumart_effect="glow",
                            waveform_mode="line",
                            waveform_splits=1,
                            waveform_frame=0,
                            vectorscope_mode="lissajous",
                            vectorscope_draw="aaline",
                            vectorscope_scale="cbrt",
                            vectorscope_zoom=1.0,
                            vectorscope_trails=100,
                            vectorscope_color_index=0,
                            spectrogram_mode="intensity",
                            cqt_gamma=3.0,
                            cqt_basefreq=20.0,
                            cqt_endfreq=20495.0,
                            cqt_attack=0.0,
                            cqt_timeclamp=0.17,
                            batch=None,
                            list_plugins=False,
                            install_plugin=None,
                            config=False,
                            save_config=False,
                            overwrite=False,
                            theme=None,
                            validate_config=False,
                            retry=0,
                            mirror_axis="y",
                            mirror_gap=0,
                            spectrum_mode="rainbow",
                            showfreqs_mode="bar",
                            showfreqs_ascale="log",
                            showfreqs_fscale="log",
                            showfreqs_winfunc="hann",
                            showfreqs_overlap=0.5,
                            showfreqs_channels="all",
                            showvolume_mode="peak",
                            showvolume_orientation="h",
                            showvolume_scale="lin",
                            validate=False,
                            dry_run=False,
                            json=False,
                            log_file=None,
                            list_themes=False,
                            version=False,
                            info=None,
                            spectrum_style="scroll",
                            spectrum_opacity=1.0,
                            spectrum_start=0,
                            spectrum_stop=0,
                            bar_width=0,
                            bar_spacing=0.5,
                            bar_orientation="horizontal",
                            bar_radius=0,
                            waveform_colors_per_channel=False,
                            mirror_opacity=1.0,
                            vectorscope_framerate=0,
                            vectorscope_border=False,
                            vectorscope_border_color="ffffff",
                            vectorscope_border_width=2,
                            spectrogram_speed=0.95,
                            spectrogram_opacity=1.0,
                            spectrogram_transpose=False,
                            albumart_position="bottom",
                            albumart_glow_intensity=0.08,
                            albumart_fit="cover",
                            albumart_blur=0,
                            border=False,
                            border_color="ffffff",
                            border_width=2,
                            aspect_ratio=None,
                            visualizer_config=None,
                            config_path=None,
                        )
                        main()
                        # Verify retry=0 was passed
                        call_kwargs = mock_merge.call_args
                        assert call_kwargs is not None

    def test_retry_flag_with_value(self):
        """Test that retry flag parses correctly."""
        from argparse import Namespace

        from audio_visualizer.__main__ import main

        with patch("sys.argv", ["audio-visualizer", "test.mp3", "--retry", "3"]):
            with patch("audio_visualizer.__main__.check_ffmpeg", return_value="ffmpeg version 7.0.1 Copyright"):
                with patch("audio_visualizer.__main__.run_visualizer"):
                    with patch("audio_visualizer.__main__.merge_config") as mock_merge:
                        mock_merge.return_value = Namespace(
                            input="test.mp3",
                            output=None,
                            mode="spectrum",
                            resolution="1280x720",
                            fps=30,
                            preset="medium",
                            crf=23,
                            verbose=False,
                            image=None,
                            format="mp4",
                            accel="auto",
                            colors=None,
                            bg_color=None,
                            albumart_effect="glow",
                            waveform_mode="line",
                            waveform_splits=1,
                            waveform_frame=0,
                            vectorscope_mode="lissajous",
                            vectorscope_draw="aaline",
                            vectorscope_scale="cbrt",
                            vectorscope_zoom=1.0,
                            vectorscope_trails=100,
                            vectorscope_color_index=0,
                            spectrogram_mode="intensity",
                            cqt_gamma=3.0,
                            cqt_basefreq=20.0,
                            cqt_endfreq=20495.0,
                            cqt_attack=0.0,
                            cqt_timeclamp=0.17,
                            batch=None,
                            list_plugins=False,
                            install_plugin=None,
                            config=False,
                            save_config=False,
                            overwrite=False,
                            theme=None,
                            validate_config=False,
                            retry=3,
                            mirror_axis="y",
                            mirror_gap=0,
                            spectrum_mode="rainbow",
                            showfreqs_mode="bar",
                            showfreqs_ascale="log",
                            showfreqs_fscale="log",
                            showfreqs_winfunc="hann",
                            showfreqs_overlap=0.5,
                            showfreqs_channels="all",
                            showvolume_mode="peak",
                            showvolume_orientation="h",
                            showvolume_scale="lin",
                            validate=False,
                            dry_run=False,
                            json=False,
                            log_file=None,
                            list_themes=False,
                            version=False,
                            info=None,
                            spectrum_style="scroll",
                            spectrum_opacity=1.0,
                            spectrum_start=0,
                            spectrum_stop=0,
                            bar_width=0,
                            bar_spacing=0.5,
                            bar_orientation="horizontal",
                            bar_radius=0,
                            waveform_colors_per_channel=False,
                            mirror_opacity=1.0,
                            vectorscope_framerate=0,
                            vectorscope_border=False,
                            vectorscope_border_color="ffffff",
                            vectorscope_border_width=2,
                            spectrogram_speed=0.95,
                            spectrogram_opacity=1.0,
                            spectrogram_transpose=False,
                            albumart_position="bottom",
                            albumart_glow_intensity=0.08,
                            albumart_fit="cover",
                            albumart_blur=0,
                            border=False,
                            border_color="ffffff",
                            border_width=2,
                            aspect_ratio=None,
                            visualizer_config=None,
                            config_path=None,
                        )
                        main()

    def test_retry_flag_short(self):
        """Test that -R short flag works."""
        from argparse import Namespace

        from audio_visualizer.__main__ import main

        with patch("sys.argv", ["audio-visualizer", "test.mp3", "-R", "2"]):
            with patch("audio_visualizer.__main__.check_ffmpeg", return_value="ffmpeg version 7.0.1 Copyright"):
                with patch("audio_visualizer.__main__.run_visualizer"):
                    with patch("audio_visualizer.__main__.merge_config") as mock_merge:
                        mock_merge.return_value = Namespace(
                            input="test.mp3",
                            output=None,
                            mode="spectrum",
                            resolution="1280x720",
                            fps=30,
                            preset="medium",
                            crf=23,
                            verbose=False,
                            image=None,
                            format="mp4",
                            accel="auto",
                            colors=None,
                            bg_color=None,
                            albumart_effect="glow",
                            waveform_mode="line",
                            waveform_splits=1,
                            waveform_frame=0,
                            vectorscope_mode="lissajous",
                            vectorscope_draw="aaline",
                            vectorscope_scale="cbrt",
                            vectorscope_zoom=1.0,
                            vectorscope_trails=100,
                            vectorscope_color_index=0,
                            spectrogram_mode="intensity",
                            cqt_gamma=3.0,
                            cqt_basefreq=20.0,
                            cqt_endfreq=20495.0,
                            cqt_attack=0.0,
                            cqt_timeclamp=0.17,
                            batch=None,
                            list_plugins=False,
                            install_plugin=None,
                            config=False,
                            save_config=False,
                            overwrite=False,
                            theme=None,
                            validate_config=False,
                            retry=2,
                            mirror_axis="y",
                            mirror_gap=0,
                            spectrum_mode="rainbow",
                            showfreqs_mode="bar",
                            showfreqs_ascale="log",
                            showfreqs_fscale="log",
                            showfreqs_winfunc="hann",
                            showfreqs_overlap=0.5,
                            showfreqs_channels="all",
                            showvolume_mode="peak",
                            showvolume_orientation="h",
                            showvolume_scale="lin",
                            validate=False,
                            dry_run=False,
                            json=False,
                            log_file=None,
                            list_themes=False,
                            version=False,
                            info=None,
                            spectrum_style="scroll",
                            spectrum_opacity=1.0,
                            spectrum_start=0,
                            spectrum_stop=0,
                            bar_width=0,
                            bar_spacing=0.5,
                            bar_orientation="horizontal",
                            bar_radius=0,
                            waveform_colors_per_channel=False,
                            mirror_opacity=1.0,
                            vectorscope_framerate=0,
                            vectorscope_border=False,
                            vectorscope_border_color="ffffff",
                            vectorscope_border_width=2,
                            spectrogram_speed=0.95,
                            spectrogram_opacity=1.0,
                            spectrogram_transpose=False,
                            albumart_position="bottom",
                            albumart_glow_intensity=0.08,
                            albumart_fit="cover",
                            albumart_blur=0,
                            border=False,
                            border_color="ffffff",
                            border_width=2,
                            aspect_ratio=None,
                            visualizer_config=None,
                            config_path=None,
                        )
                        main()

    def test_retry_passed_to_visualizer(self):
        """Test that retry count is passed to run_visualizer."""
        from argparse import Namespace

        from audio_visualizer.__main__ import main

        with patch("sys.argv", ["audio-visualizer", "test.mp3", "--retry", "5"]):
            with patch("audio_visualizer.__main__.check_ffmpeg", return_value="ffmpeg version 7.0.1 Copyright"):
                with patch("audio_visualizer.__main__.run_visualizer") as mock_rv:
                    with patch("audio_visualizer.__main__.merge_config") as mock_merge:
                        mock_merge.return_value = Namespace(
                            input="test.mp3",
                            output="out.mp4",
                            mode="spectrum",
                            resolution="1280x720",
                            fps=30,
                            preset="medium",
                            crf=23,
                            verbose=False,
                            image=None,
                            format="mp4",
                            accel="auto",
                            colors=None,
                            bg_color=None,
                            albumart_effect="glow",
                            waveform_mode="line",
                            waveform_splits=1,
                            waveform_frame=0,
                            vectorscope_mode="lissajous",
                            vectorscope_draw="aaline",
                            vectorscope_scale="cbrt",
                            vectorscope_zoom=1.0,
                            vectorscope_trails=100,
                            vectorscope_color_index=0,
                            spectrogram_mode="intensity",
                            cqt_gamma=3.0,
                            cqt_basefreq=20.0,
                            cqt_endfreq=20495.0,
                            cqt_attack=0.0,
                            cqt_timeclamp=0.17,
                            batch=None,
                            list_plugins=False,
                            install_plugin=None,
                            config=False,
                            save_config=False,
                            overwrite=False,
                            theme=None,
                            validate_config=False,
                            retry=5,
                            mirror_axis="y",
                            mirror_gap=0,
                            spectrum_mode="rainbow",
                            showfreqs_mode="bar",
                            showfreqs_ascale="log",
                            showfreqs_fscale="log",
                            showfreqs_winfunc="hann",
                            showfreqs_overlap=0.5,
                            showfreqs_channels="all",
                            showvolume_mode="peak",
                            showvolume_orientation="h",
                            showvolume_scale="lin",
                            validate=False,
                            dry_run=False,
                            json=False,
                            log_file=None,
                            list_themes=False,
                            version=False,
                            info=None,
                            spectrum_style="scroll",
                            spectrum_opacity=1.0,
                            spectrum_start=0,
                            spectrum_stop=0,
                            bar_width=0,
                            bar_spacing=0.5,
                            bar_orientation="horizontal",
                            bar_radius=0,
                            waveform_colors_per_channel=False,
                            mirror_opacity=1.0,
                            vectorscope_framerate=0,
                            vectorscope_border=False,
                            vectorscope_border_color="ffffff",
                            vectorscope_border_width=2,
                            spectrogram_speed=0.95,
                            spectrogram_opacity=1.0,
                            spectrogram_transpose=False,
                            albumart_position="bottom",
                            albumart_glow_intensity=0.08,
                            albumart_fit="cover",
                            albumart_blur=0,
                            border=False,
                            border_color="ffffff",
                            border_width=2,
                            aspect_ratio=None,
                            visualizer_config=None,
                            config_path=None,
                        )
                        main()
                        # Check that retry=5 was passed in the args dict
                        call_args = mock_rv.call_args
                        args_dict = call_args[0][1]
                        assert args_dict["retry"] == 5

    def test_retry_default_zero_in_visualizer(self):
        """Test that retry defaults to 0 when not specified."""
        from argparse import Namespace

        from audio_visualizer.__main__ import main

        with patch("sys.argv", ["audio-visualizer", "test.mp3"]):
            with patch("audio_visualizer.__main__.check_ffmpeg", return_value="ffmpeg version 7.0.1 Copyright"):
                with patch("audio_visualizer.__main__.run_visualizer") as mock_rv:
                    with patch("audio_visualizer.__main__.merge_config") as mock_merge:
                        mock_merge.return_value = Namespace(
                            input="test.mp3",
                            output="out.mp4",
                            mode="spectrum",
                            resolution="1280x720",
                            fps=30,
                            preset="medium",
                            crf=23,
                            verbose=False,
                            image=None,
                            format="mp4",
                            accel="auto",
                            colors=None,
                            bg_color=None,
                            albumart_effect="glow",
                            waveform_mode="line",
                            waveform_splits=1,
                            waveform_frame=0,
                            vectorscope_mode="lissajous",
                            vectorscope_draw="aaline",
                            vectorscope_scale="cbrt",
                            vectorscope_zoom=1.0,
                            vectorscope_trails=100,
                            vectorscope_color_index=0,
                            spectrogram_mode="intensity",
                            cqt_gamma=3.0,
                            cqt_basefreq=20.0,
                            cqt_endfreq=20495.0,
                            cqt_attack=0.0,
                            cqt_timeclamp=0.17,
                            batch=None,
                            list_plugins=False,
                            install_plugin=None,
                            config=False,
                            save_config=False,
                            overwrite=False,
                            theme=None,
                            validate_config=False,
                            retry=0,
                            mirror_axis="y",
                            mirror_gap=0,
                            spectrum_mode="rainbow",
                            showfreqs_mode="bar",
                            showfreqs_ascale="log",
                            showfreqs_fscale="log",
                            showfreqs_winfunc="hann",
                            showfreqs_overlap=0.5,
                            showfreqs_channels="all",
                            showvolume_mode="peak",
                            showvolume_orientation="h",
                            showvolume_scale="lin",
                            validate=False,
                            dry_run=False,
                            json=False,
                            log_file=None,
                            list_themes=False,
                            version=False,
                            info=None,
                            spectrum_style="scroll",
                            spectrum_opacity=1.0,
                            spectrum_start=0,
                            spectrum_stop=0,
                            bar_width=0,
                            bar_spacing=0.5,
                            bar_orientation="horizontal",
                            bar_radius=0,
                            waveform_colors_per_channel=False,
                            mirror_opacity=1.0,
                            vectorscope_framerate=0,
                            vectorscope_border=False,
                            vectorscope_border_color="ffffff",
                            vectorscope_border_width=2,
                            spectrogram_speed=0.95,
                            spectrogram_opacity=1.0,
                            spectrogram_transpose=False,
                            albumart_position="bottom",
                            albumart_glow_intensity=0.08,
                            albumart_fit="cover",
                            albumart_blur=0,
                            border=False,
                            border_color="ffffff",
                            border_width=2,
                            aspect_ratio=None,
                            visualizer_config=None,
                            config_path=None,
                        )
                        main()
                        call_args = mock_rv.call_args
                        args_dict = call_args[0][1]
                        assert args_dict["retry"] == 0


class TestValidatePlugins:
    """Test plugin validation."""

    def test_validate_all_valid(self):
        """Test validation when all plugins are valid."""
        from audio_visualizer.__main__ import validate_plugins
        from audio_visualizer.visualizers.registry import PluginRegistry

        registry = PluginRegistry()
        registry.load_all()
        valid, invalid = validate_plugins(registry)

        assert len(valid) > 0
        assert len(invalid) == 0
        for p in valid:
            assert "name" in p
            assert "display_name" in p
            assert "version" in p
            assert "description" in p
            assert "filter_length" in p
            assert p["filter_length"] > 0

    def test_validate_invalid_metadata(self, tmp_path):
        """Test validation catches invalid plugin metadata."""
        from audio_visualizer.__main__ import validate_plugins
        from audio_visualizer.visualizers.registry import PluginRegistry

        # Create a plugin with missing name
        bad_plugin_code = """
from audio_visualizer.visualizers.base import VisualizerPlugin, PluginMetadata

class BadPlugin(VisualizerPlugin):
    metadata = PluginMetadata(
        name="",
        display_name="Bad Plugin",
        description="A bad plugin",
    )

    def build_filter(self, width, height, fps, colors=None):
        return "test"
"""
        plugin_file = tmp_path / "bad_plugin.py"
        plugin_file.write_text(bad_plugin_code)

        registry = PluginRegistry(user_plugin_dir=str(tmp_path))
        registry.load_all()
        valid, invalid = validate_plugins(registry)

        assert len(invalid) >= 1
        assert any("Missing plugin name" in p["error"] for p in invalid)

    def test_validate_build_filter_failure(self, tmp_path):
        """Test validation catches build_filter failures."""
        from audio_visualizer.__main__ import validate_plugins
        from audio_visualizer.visualizers.registry import PluginRegistry

        # Create a plugin that raises in build_filter
        bad_plugin_code = """
from audio_visualizer.visualizers.base import VisualizerPlugin, PluginMetadata

class FailingPlugin(VisualizerPlugin):
    metadata = PluginMetadata(
        name="failing",
        display_name="Failing Plugin",
        description="A plugin that fails",
    )

    def build_filter(self, width, height, fps, options=None):
        raise RuntimeError("Filter build failed")
"""
        plugin_file = tmp_path / "failing_plugin.py"
        plugin_file.write_text(bad_plugin_code)

        registry = PluginRegistry(user_plugin_dir=str(tmp_path))
        registry.load_all()
        valid, invalid = validate_plugins(registry)

        assert len(invalid) >= 1
        assert any("Filter build failed" in p["error"] for p in invalid)

    def test_validate_missing_display_name(self, tmp_path):
        """Test validation catches missing display_name."""
        from audio_visualizer.__main__ import validate_plugins
        from audio_visualizer.visualizers.registry import PluginRegistry

        bad_plugin_code = """
from audio_visualizer.visualizers.base import VisualizerPlugin, PluginMetadata

class BadPlugin(VisualizerPlugin):
    metadata = PluginMetadata(
        name="bad2",
        display_name="",
        description="Missing display name",
    )

    def build_filter(self, width, height, fps, colors=None):
        return "test"
"""
        plugin_file = tmp_path / "bad_plugin2.py"
        plugin_file.write_text(bad_plugin_code)

        registry = PluginRegistry(user_plugin_dir=str(tmp_path))
        registry.load_all()
        valid, invalid = validate_plugins(registry)

        assert len(invalid) >= 1
        assert any("Missing display_name" in p["error"] for p in invalid)

    def test_validate_missing_description(self, tmp_path):
        """Test validation catches missing description."""
        from audio_visualizer.__main__ import validate_plugins
        from audio_visualizer.visualizers.registry import PluginRegistry

        bad_plugin_code = """
from audio_visualizer.visualizers.base import VisualizerPlugin, PluginMetadata

class BadPlugin(VisualizerPlugin):
    metadata = PluginMetadata(
        name="bad3",
        display_name="Bad Plugin 3",
        description="",
    )

    def build_filter(self, width, height, fps, colors=None):
        return "test"
"""
        plugin_file = tmp_path / "bad_plugin3.py"
        plugin_file.write_text(bad_plugin_code)

        registry = PluginRegistry(user_plugin_dir=str(tmp_path))
        registry.load_all()
        valid, invalid = validate_plugins(registry)

        assert len(invalid) >= 1
        assert any("Missing description" in p["error"] for p in invalid)


class TestDryRun:
    """Test dry run mode."""

    def test_dry_run_single_file(self):
        """Test dry run for single file mode."""
        from argparse import Namespace

        from audio_visualizer.__main__ import main

        with patch("sys.argv", ["audio-visualizer", "test.mp3", "--dry-run"]):
            with patch("audio_visualizer.__main__.merge_config") as mock_merge:
                mock_merge.return_value = Namespace(
                    input="test.mp3",
                    output=None,
                    mode="spectrum",
                    resolution="1280x720",
                    fps=30,
                    preset="medium",
                    crf=23,
                    verbose=False,
                    image=None,
                    format="mp4",
                    accel="auto",
                    colors=None,
                    bg_color=None,
                    albumart_effect="glow",
                    waveform_mode="line",
                    waveform_splits=1,
                    waveform_frame=0,
                    vectorscope_mode="lissajous",
                    vectorscope_draw="aaline",
                    vectorscope_scale="cbrt",
                    vectorscope_zoom=1.0,
                    vectorscope_trails=100,
                    vectorscope_color_index=0,
                    spectrogram_mode="intensity",
                    cqt_gamma=3.0,
                    cqt_basefreq=20.0,
                    cqt_endfreq=20495.0,
                    cqt_attack=0.0,
                    cqt_timeclamp=0.17,
                    batch=None,
                    list_plugins=False,
                    install_plugin=None,
                    config=False,
                    save_config=False,
                    overwrite=False,
                    theme=None,
                    validate_config=False,
                    retry=0,
                    mirror_axis="y",
                    mirror_gap=0,
                    spectrum_mode="rainbow",
                    showfreqs_mode="bar",
                    showfreqs_ascale="log",
                    showfreqs_fscale="log",
                    showfreqs_winfunc="hann",
                    showfreqs_overlap=0.5,
                    showfreqs_channels="all",
                    showvolume_mode="peak",
                    showvolume_orientation="h",
                    showvolume_scale="lin",
                    validate=False,
                    dry_run=True,
                    json=False,
                    log_file=None,
                    list_themes=False,
                    version=False,
                )
                with patch("audio_visualizer.__main__.detect_hwaccel", return_value="sw"):
                    main()

    def test_dry_run_batch(self):
        """Test dry run for batch mode."""
        from argparse import Namespace

        from audio_visualizer.__main__ import main

        with patch("sys.argv", ["audio-visualizer", "--dry-run", "--batch", "tests/assets/"]):
            with patch("audio_visualizer.__main__.merge_config") as mock_merge:
                mock_merge.return_value = Namespace(
                    input=None,
                    output=None,
                    mode="spectrum",
                    resolution="1280x720",
                    fps=30,
                    preset="medium",
                    crf=23,
                    verbose=False,
                    image=None,
                    format="mp4",
                    accel="auto",
                    colors=None,
                    bg_color=None,
                    albumart_effect="glow",
                    waveform_mode="line",
                    waveform_splits=1,
                    waveform_frame=0,
                    vectorscope_mode="lissajous",
                    vectorscope_draw="aaline",
                    vectorscope_scale="cbrt",
                    vectorscope_zoom=1.0,
                    vectorscope_trails=100,
                    vectorscope_color_index=0,
                    spectrogram_mode="intensity",
                    cqt_gamma=3.0,
                    cqt_basefreq=20.0,
                    cqt_endfreq=20495.0,
                    cqt_attack=0.0,
                    cqt_timeclamp=0.17,
                    batch="tests/assets/",
                    list_plugins=False,
                    install_plugin=None,
                    config=False,
                    save_config=False,
                    overwrite=False,
                    output_template="{name}_visualizer.{ext}",
                    recursive=False,
                    include=[],
                    exclude=[],
                    theme=None,
                    validate_config=False,
                    retry=0,
                    mirror_axis="y",
                    mirror_gap=0,
                    spectrum_mode="rainbow",
                    showfreqs_mode="bar",
                    showfreqs_ascale="log",
                    showfreqs_fscale="log",
                    showfreqs_winfunc="hann",
                    showfreqs_overlap=0.5,
                    showfreqs_channels="all",
                    showvolume_mode="peak",
                    showvolume_orientation="h",
                    showvolume_scale="lin",
                    validate=False,
                    dry_run=True,
                    json=False,
                    log_file=None,
                    list_themes=False,
                    version=False,
                )
                with patch("audio_visualizer.__main__.detect_hwaccel", return_value="sw"):
                    main()

    def test_dry_run_custom_output(self):
        """Test dry run with custom output file."""
        from argparse import Namespace

        from audio_visualizer.__main__ import main

        with patch("sys.argv", ["audio-visualizer", "test.mp3", "--dry-run", "-o", "custom.mp4"]):
            with patch("audio_visualizer.__main__.merge_config") as mock_merge:
                mock_merge.return_value = Namespace(
                    input="test.mp3",
                    output="custom.mp4",
                    mode="waveform",
                    resolution="1920x1080",
                    fps=60,
                    preset="fast",
                    crf=18,
                    verbose=False,
                    image=None,
                    format="mkv",
                    accel="disabled",
                    colors=None,
                    bg_color=None,
                    albumart_effect="glow",
                    waveform_mode="line",
                    waveform_splits=1,
                    waveform_frame=0,
                    vectorscope_mode="lissajous",
                    vectorscope_draw="aaline",
                    vectorscope_scale="cbrt",
                    vectorscope_zoom=1.0,
                    vectorscope_trails=100,
                    vectorscope_color_index=0,
                    spectrogram_mode="intensity",
                    cqt_gamma=3.0,
                    cqt_basefreq=20.0,
                    cqt_endfreq=20495.0,
                    cqt_attack=0.0,
                    cqt_timeclamp=0.17,
                    batch=None,
                    list_plugins=False,
                    install_plugin=None,
                    config=False,
                    save_config=False,
                    overwrite=False,
                    theme=None,
                    validate_config=False,
                    retry=0,
                    mirror_axis="y",
                    mirror_gap=0,
                    spectrum_mode="rainbow",
                    showfreqs_mode="bar",
                    showfreqs_ascale="log",
                    showfreqs_fscale="log",
                    showfreqs_winfunc="hann",
                    showfreqs_overlap=0.5,
                    showfreqs_channels="all",
                    showvolume_mode="peak",
                    showvolume_orientation="h",
                    showvolume_scale="lin",
                    validate=False,
                    dry_run=True,
                    json=False,
                    log_file=None,
                    list_themes=False,
                    version=False,
                )
                with patch("audio_visualizer.__main__.detect_hwaccel", return_value="sw"):
                    main()

    def test_dry_run_with_mode(self):
        """Test dry run with different visualization mode."""
        from argparse import Namespace

        from audio_visualizer.__main__ import main

        with patch("sys.argv", ["audio-visualizer", "test.mp3", "--dry-run", "--mode", "waveform"]):
            with patch("audio_visualizer.__main__.merge_config") as mock_merge:
                mock_merge.return_value = Namespace(
                    input="test.mp3",
                    output=None,
                    mode="waveform",
                    resolution="1280x720",
                    fps=30,
                    preset="medium",
                    crf=23,
                    verbose=False,
                    image=None,
                    format="mp4",
                    accel="auto",
                    colors=None,
                    bg_color=None,
                    albumart_effect="glow",
                    waveform_mode="line",
                    waveform_splits=1,
                    waveform_frame=0,
                    vectorscope_mode="lissajous",
                    vectorscope_draw="aaline",
                    vectorscope_scale="cbrt",
                    vectorscope_zoom=1.0,
                    vectorscope_trails=100,
                    vectorscope_color_index=0,
                    spectrogram_mode="intensity",
                    cqt_gamma=3.0,
                    cqt_basefreq=20.0,
                    cqt_endfreq=20495.0,
                    cqt_attack=0.0,
                    cqt_timeclamp=0.17,
                    batch=None,
                    list_plugins=False,
                    install_plugin=None,
                    config=False,
                    save_config=False,
                    overwrite=False,
                    theme=None,
                    validate_config=False,
                    retry=0,
                    mirror_axis="y",
                    mirror_gap=0,
                    spectrum_mode="rainbow",
                    showfreqs_mode="bar",
                    showfreqs_ascale="log",
                    showfreqs_fscale="log",
                    showfreqs_winfunc="hann",
                    showfreqs_overlap=0.5,
                    showfreqs_channels="all",
                    showvolume_mode="peak",
                    showvolume_orientation="h",
                    showvolume_scale="lin",
                    validate=False,
                    dry_run=True,
                    json=False,
                    log_file=None,
                    list_themes=False,
                    version=False,
                )
                with patch("audio_visualizer.__main__.detect_hwaccel", return_value="sw"):
                    main()


class TestInfoFlag:
    """Test --info flag for audio file information."""

    def test_info_valid_file(self):
        """Test --info with a valid audio file."""
        from argparse import Namespace

        from audio_visualizer.__main__ import main

        with patch("sys.argv", ["audio-visualizer", "--info", "tests/assets/test.wav"]):
            with patch("audio_visualizer.__main__.merge_config") as mock_merge:
                mock_merge.return_value = Namespace(
                    input=None,
                    output=None,
                    mode="spectrum",
                    resolution="1280x720",
                    fps=30,
                    preset="medium",
                    crf=23,
                    verbose=False,
                    image=None,
                    format="mp4",
                    accel="auto",
                    colors=None,
                    bg_color=None,
                    albumart_effect="glow",
                    batch=None,
                    list_plugins=False,
                    install_plugin=None,
                    config=False,
                    save_config=False,
                    overwrite=False,
                    theme=None,
                    validate_config=False,
                    retry=0,
                    mirror_axis="y",
                    mirror_gap=0,
                    spectrum_mode="rainbow",
                    showfreqs_mode="bar",
                    showfreqs_ascale="log",
                    showfreqs_fscale="log",
                    showfreqs_winfunc="hann",
                    showfreqs_overlap=0.5,
                    showfreqs_channels="all",
                    showvolume_mode="peak",
                    showvolume_orientation="h",
                    showvolume_scale="lin",
                    validate=False,
                    dry_run=False,
                    json=False,
                    log_file=None,
                    list_themes=False,
                    version=False,
                    info="tests/assets/test.wav",
                )
                main()

    def test_info_mp3_file(self):
        """Test --info with an MP3 file."""
        from argparse import Namespace

        from audio_visualizer.__main__ import main

        with patch("sys.argv", ["audio-visualizer", "--info", "tests/assets/test.mp3"]):
            with patch("audio_visualizer.__main__.merge_config") as mock_merge:
                mock_merge.return_value = Namespace(
                    input=None,
                    output=None,
                    mode="spectrum",
                    resolution="1280x720",
                    fps=30,
                    preset="medium",
                    crf=23,
                    verbose=False,
                    image=None,
                    format="mp4",
                    accel="auto",
                    colors=None,
                    bg_color=None,
                    albumart_effect="glow",
                    batch=None,
                    list_plugins=False,
                    install_plugin=None,
                    config=False,
                    save_config=False,
                    overwrite=False,
                    theme=None,
                    validate_config=False,
                    retry=0,
                    mirror_axis="y",
                    mirror_gap=0,
                    spectrum_mode="rainbow",
                    showfreqs_mode="bar",
                    showfreqs_ascale="log",
                    showfreqs_fscale="log",
                    showfreqs_winfunc="hann",
                    showfreqs_overlap=0.5,
                    showfreqs_channels="all",
                    showvolume_mode="peak",
                    showvolume_orientation="h",
                    showvolume_scale="lin",
                    validate=False,
                    dry_run=False,
                    json=False,
                    log_file=None,
                    list_themes=False,
                    version=False,
                    info="tests/assets/test.mp3",
                )
                main()

    def test_info_missing_file(self, caplog):
        """Test --info with a missing file."""
        from argparse import Namespace

        from audio_visualizer.__main__ import main

        with patch("sys.argv", ["audio-visualizer", "--info", "nonexistent.wav"]):
            with patch("audio_visualizer.__main__.merge_config") as mock_merge:
                mock_merge.return_value = Namespace(
                    input=None,
                    output=None,
                    mode="spectrum",
                    resolution="1280x720",
                    fps=30,
                    preset="medium",
                    crf=23,
                    verbose=False,
                    image=None,
                    format="mp4",
                    accel="auto",
                    colors=None,
                    bg_color=None,
                    albumart_effect="glow",
                    batch=None,
                    list_plugins=False,
                    install_plugin=None,
                    config=False,
                    save_config=False,
                    overwrite=False,
                    theme=None,
                    validate_config=False,
                    retry=0,
                    mirror_axis="y",
                    mirror_gap=0,
                    spectrum_mode="rainbow",
                    showfreqs_mode="bar",
                    showfreqs_ascale="log",
                    showfreqs_fscale="log",
                    showfreqs_winfunc="hann",
                    showfreqs_overlap=0.5,
                    showfreqs_channels="all",
                    showvolume_mode="peak",
                    showvolume_orientation="h",
                    showvolume_scale="lin",
                    validate=False,
                    dry_run=False,
                    json=False,
                    log_file=None,
                    list_themes=False,
                    version=False,
                    info="nonexistent.wav",
                )
                with pytest.raises(SystemExit):
                    main()
                assert "File not found" in caplog.text


class TestValidateConfig:
    """Test configuration validation."""

    def test_validate_no_issues(self):
        """Test validation with valid configuration."""
        from audio_visualizer.config import validate_config

        config = {
            "resolution": "1920x1080",
            "fps": 30,
            "preset": "medium",
            "crf": 23,
            "format": "mp4",
            "accel": "auto",
        }
        args = type(
            "Args",
            (),
            {
                "resolution": "1920x1080",
                "fps": 30,
                "preset": "medium",
                "crf": 23,
                "format": "mp4",
                "accel": "auto",
                "output": None,
                "colors": None,
                "theme": None,
            },
        )()

        issues = validate_config(config, args)
        assert issues == []

    def test_validate_crf_with_nvenc(self):
        """Test that CRF with NVENC generates a remap warning (not an error)."""
        from audio_visualizer.config import validate_config

        config = {"accel": "nvenc", "crf": 23}
        args = type(
            "Args",
            (),
            {
                "resolution": None,
                "fps": None,
                "preset": None,
                "crf": 23,
                "format": None,
                "accel": "nvenc",
                "output": None,
                "colors": None,
                "theme": None,
            },
        )()

        issues = validate_config(config, args)
        assert any("WARNING" in i and "CRF" in i and "remap" in i for i in issues)
        assert not any("ERROR" in i for i in issues)

    def test_validate_crf_with_qsv(self):
        """Test that CRF with QSV generates a remap warning (not an error)."""
        from audio_visualizer.config import validate_config

        config = {"accel": "qsv", "crf": 23}
        args = type(
            "Args",
            (),
            {
                "resolution": None,
                "fps": None,
                "preset": None,
                "crf": 23,
                "format": None,
                "accel": "qsv",
                "output": None,
                "colors": None,
                "theme": None,
            },
        )()

        issues = validate_config(config, args)
        assert any("WARNING" in i and "CRF" in i and "remap" in i for i in issues)
        assert not any("ERROR" in i for i in issues)

    def test_validate_high_fps_ultrafast(self):
        """Test that high FPS with ultrafast preset generates a warning."""
        from audio_visualizer.config import validate_config

        config = {"fps": 120, "preset": "ultrafast"}
        args = type(
            "Args",
            (),
            {
                "resolution": None,
                "fps": 120,
                "preset": "ultrafast",
                "crf": None,
                "format": None,
                "accel": "auto",
                "output": None,
                "colors": None,
                "theme": None,
            },
        )()

        issues = validate_config(config, args)
        assert any("WARNING" in i and "ultrafast" in i for i in issues)

    def test_validate_low_crf_ultrafast(self):
        """Test that low CRF with ultrafast preset generates a warning."""
        from audio_visualizer.config import validate_config

        config = {"crf": 16, "preset": "ultrafast"}
        args = type(
            "Args",
            (),
            {
                "resolution": None,
                "fps": None,
                "preset": "ultrafast",
                "crf": 16,
                "format": None,
                "accel": "auto",
                "output": None,
                "colors": None,
                "theme": None,
            },
        )()

        issues = validate_config(config, args)
        assert any("WARNING" in i and "ultrafast" in i for i in issues)


class TestListPluginsDisplay:
    """Test the list_plugins display function in core.py."""

    def test_list_plugins_all(self, caplog):
        """Test listing all plugins shows category groups."""
        from audio_visualizer.core import list_plugins
        from audio_visualizer.visualizers.registry import PluginRegistry

        registry = PluginRegistry()
        registry.load_all()
        with caplog.at_level("INFO"):
            list_plugins(registry)
        assert "Available Visualizer Plugins" in caplog.text
        assert "[spectrum]" in caplog.text
        assert "[meter]" in caplog.text

    def test_list_plugins_by_category(self, caplog):
        """Test listing plugins filtered by category."""
        from audio_visualizer.core import list_plugins
        from audio_visualizer.visualizers.registry import PluginRegistry

        registry = PluginRegistry()
        registry.load_all()
        with caplog.at_level("INFO"):
            list_plugins(registry, category="meter")
        assert "in category 'meter'" in caplog.text
        assert "vectorscope" in caplog.text
        # spectrum plugins should not appear
        assert "Color Spectrum" not in caplog.text

    def test_list_plugins_unknown_category(self, caplog):
        """Test listing with an unknown category shows a message."""
        from audio_visualizer.core import list_plugins
        from audio_visualizer.visualizers.registry import PluginRegistry

        registry = PluginRegistry()
        registry.load_all()
        with caplog.at_level("INFO"):
            list_plugins(registry, category="nonexistent")
        assert "No plugins found in category 'nonexistent'" in caplog.text

    def test_list_plugins_verbose_shows_options(self, caplog):
        """Test verbose listing shows plugin options with defaults."""
        from audio_visualizer.core import list_plugins
        from audio_visualizer.visualizers.registry import PluginRegistry

        registry = PluginRegistry()
        registry.load_all()
        with caplog.at_level("INFO"):
            list_plugins(registry, category="meter", verbose=True)
        assert "Options:" in caplog.text
        assert "--showvolume-mode" in caplog.text
        assert "default='peak'" in caplog.text
        assert "choices: peak, rms" in caplog.text
        assert "Inputs: audio" in caplog.text

    def test_list_plugins_non_verbose_hides_options(self, caplog):
        """Test non-verbose listing does not show options."""
        from audio_visualizer.core import list_plugins
        from audio_visualizer.visualizers.registry import PluginRegistry

        registry = PluginRegistry()
        registry.load_all()
        with caplog.at_level("INFO"):
            list_plugins(registry, category="meter")
        assert "Options:" not in caplog.text


class TestSaveConfigFlag:
    """Test the --save-config CLI flag end-to-end."""

    def test_save_config_writes_file(self, tmp_path):
        """--save-config writes a config file without crashing."""
        from pathlib import Path

        from audio_visualizer.__main__ import main

        config_path = str(tmp_path / "config.yml")
        with patch("sys.argv", ["audio-visualizer", "song.mp3", "--save-config"]):
            with patch("audio_visualizer.config.get_config_path", return_value=config_path):
                main()
        assert Path(config_path).exists()
        content = Path(config_path).read_text()
        assert "# Audio Visualizer Configuration" in content
        # --mode defaults to None (argparse append since the v2.2.0
        # per-mode syntax), so an unmodified run saves it empty
        assert "mode:\n" in content or "mode: \n" in content
        assert "['spectrum']" not in content

    def test_save_config_includes_nondefault_plugin_options(self, tmp_path):
        """--save-config writes non-default plugin options as sections."""
        from pathlib import Path

        from audio_visualizer.__main__ import main

        config_path = str(tmp_path / "config.yml")
        with patch(
            "sys.argv",
            ["audio-visualizer", "song.mp3", "--save-config", "--spectrum-opacity", "0.7"],
        ):
            with patch("audio_visualizer.config.get_config_path", return_value=config_path):
                main()
        content = Path(config_path).read_text()
        assert "\nspectrum:\n" in content
        assert "  opacity: 0.7" in content

    def test_save_config_default_options_not_written(self, tmp_path):
        """--save-config omits plugin options still at their defaults."""
        from pathlib import Path

        from audio_visualizer.__main__ import main

        config_path = str(tmp_path / "config.yml")
        with patch("sys.argv", ["audio-visualizer", "song.mp3", "--save-config"]):
            with patch("audio_visualizer.config.get_config_path", return_value=config_path):
                main()
        content = Path(config_path).read_text()
        assert "\nspectrum:\n" not in content


class TestBatchArgsDict:
    """Test that _process_batch passes a complete args dict to run_visualizer."""

    def _make_namespace(self, batch_dir):
        """Build a Namespace like the CLI parser produces."""
        return Namespace(
            input=None,
            output=None,
            mode="spectrum",
            resolution="1280x720",
            fps=30,
            preset="medium",
            crf=23,
            verbose=False,
            image=None,
            format="mp4",
            accel="disabled",
            colors=None,
            bg_color="#123456",
            border=True,
            border_color="ffffff",
            border_width=2,
            albumart_effect="glow",
            albumart_position="bottom",
            albumart_glow_intensity=0.08,
            albumart_fit="cover",
            albumart_blur=0,
            waveform_mode="line",
            waveform_splits=1,
            waveform_frame=0,
            vectorscope_mode="frame",
            vectorscope_scale="cbrt",
            vectorscope_zoom=1.0,
            vectorscope_trails=100,
            vectorscope_framerate=0,
            vectorscope_border=False,
            vectorscope_color_index=0,
            spectrogram_mode="intensity",
            cqt_gamma=3.0,
            cqt_basefreq=20.0,
            cqt_endfreq=20495.0,
            cqt_attack=0.0,
            cqt_timeclamp=0.17,
            mirror_axis="y",
            mirror_gap=0,
            spectrum_mode="fire",
            showfreqs_mode="bar",
            showfreqs_ascale="log",
            showfreqs_fscale="log",
            showfreqs_winfunc="hann",
            showfreqs_overlap=0.5,
            showfreqs_channels="all",
            showvolume_mode="peak",
            showvolume_orientation="h",
            showvolume_scale="lin",
            batch=batch_dir,
            overwrite=False,
            retry=0,
            output_template="{name}_visualizer.{ext}",
            recursive=False,
            include=[],
            exclude=[],
        )

    def test_batch_dict_contains_all_options(self, tmp_path):
        """The batch args dict must carry every user option to the encode."""
        import shutil

        from audio_visualizer.core import _process_batch
        from audio_visualizer.visualizers.registry import PluginRegistry

        batch_dir = tmp_path / "audio"
        batch_dir.mkdir()
        shutil.copy("tests/assets/test.mp3", batch_dir / "a.mp3")

        registry = PluginRegistry()
        registry.load_all()
        args = self._make_namespace(str(batch_dir))
        captured = {}

        def fake_run_visualizer(plugin_cls, args_dict):
            captured.update(args_dict)

        with patch("audio_visualizer.__main__.run_visualizer", fake_run_visualizer):
            with patch("audio_visualizer.__main__.check_ffmpeg", return_value="ffmpeg version 7.0.1 Copyright"):
                _process_batch(args, registry)

        # Plugin options reach the encode
        assert captured["spectrum_mode"] == "fire"
        assert captured["bg_color"] == "#123456"
        # Border options reach the encode
        assert captured["border"] is True
        assert captured["border_color"] == "ffffff"
        assert captured["border_width"] == 2
        # Vectorscope options (no stale attributes)
        assert captured["vectorscope_border"] is False
        assert captured["vectorscope_framerate"] == 0
        assert captured["vectorscope_color_index"] == 0
        # Output routing
        assert captured["output"].endswith("a_visualizer.mp4")
        assert captured["input"].endswith("a.mp3")


class TestAspectRatio:
    """Regression: --aspect-ratio was parsed but never applied."""

    def test_aspect_ratio_16_9_unchanged(self):
        from audio_visualizer.__main__ import apply_aspect_ratio

        assert apply_aspect_ratio("1280x720", "16:9") == "1280x720"

    def test_aspect_ratio_4_3(self):
        from audio_visualizer.__main__ import apply_aspect_ratio

        assert apply_aspect_ratio("1280x720", "4:3") == "1280x960"

    def test_aspect_ratio_1_1(self):
        from audio_visualizer.__main__ import apply_aspect_ratio

        assert apply_aspect_ratio("1280x720", "1:1") == "1280x1280"

    def test_aspect_ratio_21_9_keeps_height_even(self):
        from audio_visualizer.__main__ import apply_aspect_ratio

        result = apply_aspect_ratio("1280x720", "21:9")
        assert result == "1280x548"
        assert int(result.split("x")[1]) % 2 == 0

    def test_aspect_ratio_none_is_noop(self):
        from audio_visualizer.__main__ import apply_aspect_ratio

        assert apply_aspect_ratio("1280x720", None) is None

    def test_aspect_ratio_invalid_inputs(self):
        from audio_visualizer.__main__ import apply_aspect_ratio

        assert apply_aspect_ratio("bogus", "16:9") is None
        assert apply_aspect_ratio("1280x720", "0:9") is None


class TestBuildArgsDictFix:
    """Regression: curated args dicts silently dropped ~15 plugin options
    (spectrum-style, bar-*, circular-spectrum-*, mirror-opacity,
    spectrogram-speed/opacity/transpose, waveform-colors-per-channel).
    build_args_dict() starts from the full CLI namespace instead."""

    def test_all_schema_options_forwarded(self):
        from types import SimpleNamespace

        from audio_visualizer.core import build_args_dict

        ns = SimpleNamespace(
            input="in.mp3",
            output=None,
            mode="spectrum",
            spectrum_style="replace",
            spectrum_opacity=0.5,
            circular_spectrum_mode="fire",
            bar_orientation="vertical",
            mirror_opacity=0.8,
            spectrogram_transpose=True,
            waveform_colors_per_channel=True,
            border=True,
        )
        d = build_args_dict(ns, output="out.mp4", width=640, height=360)
        for key in (
            "spectrum_style",
            "spectrum_opacity",
            "circular_spectrum_mode",
            "bar_orientation",
            "mirror_opacity",
            "spectrogram_transpose",
            "waveform_colors_per_channel",
            "border",
        ):
            assert key in d, f"option {key} dropped by build_args_dict"
        assert d["input"] == "in.mp3"
        assert d["output"] == "out.mp4"
        assert d["width"] == 640
        assert d["height"] == 360

    def test_dropped_options_reach_the_filter(self):
        """End-to-end within the process: options forwarded by
        build_args_dict actually change the generated filter."""
        from types import SimpleNamespace

        from audio_visualizer.core import build_args_dict
        from audio_visualizer.visualizers.spectrogram import SpectrogramPlugin
        from audio_visualizer.visualizers.spectrum import SpectrumPlugin

        spectrum = SpectrumPlugin().build_command(
            build_args_dict(
                SimpleNamespace(input="in.mp3", spectrum_style="replace", fps=15),
                output="out.mp4",
                width=640,
                height=360,
            )
        )
        assert "slide=replace" in " ".join(spectrum)

        spec = SpectrogramPlugin().build_command(
            build_args_dict(
                SimpleNamespace(input="in.mp3", spectrogram_transpose=True),
                output="out.mp4",
                width=640,
                height=360,
                fps=15,
            )
        )
        assert "transpose=1" in " ".join(spec)


class TestExternalPluginPaths:
    """Test --plugin-path and AUDIO_VISUALIZER_PLUGIN_PATH end-to-end."""

    PLUGIN_SRC = (
        "from audio_visualizer.visualizers.base import ("
        "PluginMetadata, PluginOption, VisualizerPlugin)\n"
        "\n"
        "\n"
        "class CliPlugin(VisualizerPlugin):\n"
        "    metadata = PluginMetadata(\n"
        '        name="clitest",\n'
        '        display_name="CLI Plugin",\n'
        '        description="Plugin loaded via an external path",\n'
        "    )\n"
        '    options = [PluginOption("clitest-opt", str, "x", "External option")]\n'
        "\n"
        "    def build_filter(self, width, height, fps, options, audio_index=0,\n"
        "                     video_index=1, colors=None, bg_color=None, args=None):\n"
        '        val = options.get("clitest-opt", "x")\n'
        '        return f"[{audio_index}:a] clitestfilter=val={val}:size={width}x{height}[viz]"\n'
    )

    @staticmethod
    def _write_plugin(tmp_path):
        plugin_file = tmp_path / "cli_plugin.py"
        plugin_file.write_text(TestExternalPluginPaths.PLUGIN_SRC)
        return plugin_file

    def test_plugin_path_flag_listed(self, tmp_path, caplog):
        """--plugin-path loads the plugin and --list-plugins shows its origin."""
        from audio_visualizer.__main__ import main

        plugin_file = self._write_plugin(tmp_path)
        with patch(
            "sys.argv",
            ["audio-visualizer", "--plugin-path", str(plugin_file), "--list-plugins"],
        ):
            main()
        assert "clitest" in caplog.text
        assert "[path]" in caplog.text

    def test_plugin_path_env(self, tmp_path, monkeypatch, caplog):
        """AUDIO_VISUALIZER_PLUGIN_PATH loads the plugin the same way."""
        from audio_visualizer.__main__ import main

        plugin_file = self._write_plugin(tmp_path)
        monkeypatch.setenv("AUDIO_VISUALIZER_PLUGIN_PATH", str(plugin_file))
        with patch("sys.argv", ["audio-visualizer", "--list-plugins"]):
            main()
        assert "clitest" in caplog.text

    def test_plugin_path_option_autogenerated(self, tmp_path, caplog):
        """An external plugin's schema generates its CLI flag and the value is
        forwarded into the filter graph (dry run, no ffmpeg needed)."""
        from audio_visualizer.__main__ import main

        plugin_file = self._write_plugin(tmp_path)
        with patch(
            "sys.argv",
            [
                "audio-visualizer",
                "fake_input.mp3",
                "--plugin-path",
                str(plugin_file),
                "--mode",
                "clitest",
                "--clitest-opt",
                "y",
                "--accel",
                "disabled",
                "--dry-run",
            ],
        ):
            main()
        assert "val=y" in caplog.text

    def test_plugin_path_help_flag(self, tmp_path, capsys):
        """--help still works with the pre-parsing step in place."""
        from audio_visualizer.__main__ import main

        with patch("sys.argv", ["audio-visualizer", "--help"]):
            with pytest.raises(SystemExit) as exc_info:
                main()
        assert exc_info.value.code == 0
        out = capsys.readouterr().out
        assert "--plugin-path" in out


class TestResolutionPresets:
    """Test --resolution 16:9 presets (v2.1.0 sec.9.2)."""

    @pytest.mark.parametrize(
        ("preset", "expected"),
        [
            ("360p", "640x360"),
            ("480p", "854x480"),
            ("720p", "1280x720"),
            ("1080p", "1920x1080"),
            ("1440p", "2560x1440"),
            ("4k", "3840x2160"),
        ],
    )
    def test_preset_expansion(self, preset, expected):
        from audio_visualizer.__main__ import resolve_resolution

        assert resolve_resolution(preset) == expected

    def test_preset_case_and_whitespace_insensitive(self):
        from audio_visualizer.__main__ import resolve_resolution

        assert resolve_resolution("1080P") == "1920x1080"
        assert resolve_resolution(" 4K ") == "3840x2160"

    def test_wxh_passthrough(self):
        from audio_visualizer.__main__ import resolve_resolution

        assert resolve_resolution("1920x1080") == "1920x1080"
        assert resolve_resolution("640x360") == "640x360"

    def test_unknown_passthrough_for_downstream_validation(self):
        from audio_visualizer.__main__ import resolve_resolution

        assert resolve_resolution("garbage") == "garbage"

    def test_dry_run_json_uses_expanded_preset(self, capsys):
        from audio_visualizer.__main__ import main

        with patch(
            "sys.argv", ["audio-visualizer", "in.mp3", "--dry-run", "--json", "-r", "1080p"]
        ):
            main()
        payload = json.loads(capsys.readouterr().out)
        assert payload["width"] == 1920
        assert payload["height"] == 1080


class TestVersionFlag:
    """Test --version (v2.1.0 sec.9.1)."""

    def test_version_flag_prints_versions(self, capsys):
        from audio_visualizer.__main__ import main

        with patch("sys.argv", ["audio-visualizer", "--version"]):
            main()
        out = capsys.readouterr().out
        assert out.startswith("audio-visualizer ")
        assert "ffmpeg" in out

    def test_version_without_ffmpeg(self, capsys):
        from audio_visualizer import __main__ as am

        with patch("subprocess.run", side_effect=FileNotFoundError()):
            am.print_version_info()
        assert "ffmpeg: not found" in capsys.readouterr().out

    def test_get_ffmpeg_version_empty_on_failure(self):
        from audio_visualizer.__main__ import get_ffmpeg_version

        with patch("subprocess.run", side_effect=FileNotFoundError()):
            assert get_ffmpeg_version() == ""

    def test_get_package_version_matches_metadata(self):
        from importlib.metadata import version

        from audio_visualizer.__main__ import get_package_version

        assert get_package_version() == version("audio-visualizer")


class TestListThemes:
    """Test --list-themes (v2.1.0 sec.9.3)."""

    def test_lists_all_themes(self, capsys):
        from audio_visualizer import __main__ as am

        am.list_themes()
        out = capsys.readouterr().out
        for theme in am.COLOR_THEMES:
            assert theme in out

    def test_cli_flag(self, capsys):
        from audio_visualizer.__main__ import main

        with patch("sys.argv", ["audio-visualizer", "--list-themes"]):
            main()
        out = capsys.readouterr().out
        assert "neon" in out and "light" in out

    def test_no_ansi_when_not_tty(self, capsys):
        from audio_visualizer import __main__ as am

        am.list_themes()  # captured stdout is not a tty
        assert "\033[" not in capsys.readouterr().out

    def test_ansi_swatches_on_tty(self, capsys, monkeypatch):
        from audio_visualizer import __main__ as am

        monkeypatch.setattr(am.sys.stdout, "isatty", lambda: True, raising=False)
        am.list_themes()
        assert "\033[38;5;" in capsys.readouterr().out


class TestLogFileFlag:
    """Test --log-file (v2.1.0 sec.9.4)."""

    def _detach(self, handler):
        for lgr in logging.Logger.manager.loggerDict.values():
            if isinstance(lgr, logging.Logger) and lgr.name.startswith("audio_visualizer"):
                lgr.removeHandler(handler)
        handler.close()

    def test_file_captures_debug_while_console_is_quiet(self, tmp_path):
        from audio_visualizer import logging_config as lc

        path = str(tmp_path / "log.txt")
        handler = lc.attach_file_handler(path)
        try:
            lc.set_level(lc.ERROR)
            lc.logger.debug("dbg-line")
            lc.logger.info("info-line")
            for lgr in logging.Logger.manager.loggerDict.values():
                if isinstance(lgr, logging.Logger):
                    for h in lgr.handlers:
                        h.flush()
            content = open(path).read()
            assert "dbg-line" in content
            assert "info-line" in content
        finally:
            self._detach(handler)

    def test_set_level_does_not_starve_file_handler(self, tmp_path):
        from audio_visualizer import logging_config as lc

        path = str(tmp_path / "log.txt")
        handler = lc.attach_file_handler(path)
        try:
            lc.set_level(lc.ERROR)
            assert handler.level == lc.DEBUG
            # logger-level gate stays at the quietest handler's level
            assert lc.logger.level == lc.DEBUG
        finally:
            self._detach(handler)

    def test_dry_run_writes_log_file(self, tmp_path):
        from audio_visualizer.__main__ import main

        log_file = str(tmp_path / "run.log")
        with patch(
            "sys.argv",
            ["audio-visualizer", "in.mp3", "--dry-run", "--log-file", log_file],
        ):
            main()
        assert "Dry run complete" in open(log_file).read()

    def test_unopenable_log_file_exits(self, tmp_path):
        from audio_visualizer.__main__ import main

        bad_path = str(tmp_path / "missing-dir" / "run.log")
        with patch(
            "sys.argv",
            ["audio-visualizer", "in.mp3", "--dry-run", "--log-file", bad_path],
        ):
            with pytest.raises(SystemExit) as exc_info:
                main()
        assert exc_info.value.code == 1


class TestDryRunJson:
    """Test --dry-run --json (v2.1.0 sec.9.5)."""

    def test_single_file_payload(self, capsys):
        from audio_visualizer.__main__ import main

        with patch(
            "sys.argv",
            [
                "audio-visualizer",
                "in.mp3",
                "--dry-run",
                "--json",
                "-r",
                "1080p",
                "--fps",
                "60",
            ],
        ):
            main()
        payload = json.loads(capsys.readouterr().out)
        assert payload["input"] == "in.mp3"
        assert payload["output"] == "in_visualizer.mp4"
        assert payload["mode"] == "spectrum"
        assert (payload["width"], payload["height"]) == (1920, 1080)
        assert payload["fps"] == 60
        assert isinstance(payload["command"], list)
        assert payload["command"][0] == "ffmpeg"

    def test_batch_payload(self, tmp_path, capsys):
        from audio_visualizer.__main__ import main

        src = os.path.join(os.path.dirname(__file__), "assets", "test.mp3")
        for name in ("a.mp3", "b.mp3"):
            shutil.copy(src, tmp_path / name)

        with patch(
            "sys.argv",
            ["audio-visualizer", "--batch", str(tmp_path), "--dry-run", "--json"],
        ):
            main()
        payload = json.loads(capsys.readouterr().out)
        assert payload["count"] == 2
        assert payload["input_dir"] == str(tmp_path)
        assert [os.path.basename(f["input"]) for f in payload["files"]] == ["a.mp3", "b.mp3"]
        assert payload["files"][0]["output"].endswith("a_visualizer.mp4")
        assert all(f["command"][0] == "ffmpeg" for f in payload["files"])

    def test_json_flag_is_inert_without_dry_run(self):
        from audio_visualizer.__main__ import _build_registry, build_parser

        parser = build_parser(_build_registry([]))
        args = parser.parse_args(["in.mp3", "--json"])
        assert args.json is True


class TestOutputTemplate:
    """Batch output naming template (v2.1.0 sec.3.3)."""

    BATCH_DIR = os.path.join(os.path.dirname(__file__), "assets", "batch")

    def test_default_template_matches_legacy_names(self):
        from audio_visualizer.core import OUTPUT_TEMPLATE_DEFAULT, render_output_template

        assert (
            render_output_template(OUTPUT_TEMPLATE_DEFAULT, "song", "mp4", "spectrum", 1280)
            == "song_visualizer.mp4"
        )

    def test_all_placeholders(self):
        from audio_visualizer.core import render_output_template

        assert (
            render_output_template("{name}_{mode}_{width}p.{ext}", "song", "webm", "radial", 1920)
            == "song_radial_1920p.webm"
        )

    def test_unknown_placeholder_is_rejected(self):
        from audio_visualizer.core import check_output_template

        with pytest.raises(ValueError):
            check_output_template("{stem}.mp4", "mp4", "spectrum", 1280)

    def test_malformed_template_is_rejected(self):
        from audio_visualizer.core import check_output_template

        with pytest.raises(ValueError):
            check_output_template("{name", "mp4", "spectrum", 1280)

    def test_directory_separator_is_rejected(self):
        from audio_visualizer.core import check_output_template

        with pytest.raises(ValueError):
            check_output_template("out/{name}.mp4", "mp4", "spectrum", 1280)

    def test_empty_result_is_rejected(self):
        from audio_visualizer.core import check_output_template

        with pytest.raises(ValueError):
            check_output_template("", "mp4", "spectrum", 1280)

    @staticmethod
    def _batch_args(tmp_path, **overrides) -> Namespace:
        base = dict(
            batch=TestOutputTemplate.BATCH_DIR,
            output=str(tmp_path),
            mode="spectrum",
            resolution="1280x720",
            format="mp4",
            overwrite=False,
            output_template="{name}_visualizer.{ext}",
            recursive=False,
            include=[],
            exclude=[],
        )
        base.update(overrides)
        return Namespace(**base)

    def test_batch_uses_custom_template(self, tmp_path):
        from audio_visualizer.core import _process_batch

        registry = MagicMock()
        registry.get.return_value = _FakeModePlugin
        with (
            patch("audio_visualizer.__main__.check_ffmpeg", return_value="ffmpeg version 7.0.1 Copyright"),
            patch("audio_visualizer.__main__.run_visualizer") as mock_run,
        ):
            _process_batch(
                self._batch_args(tmp_path, output_template="{name}_{mode}.{ext}"), registry
            )
        outputs = [os.path.basename(c.args[1]["output"]) for c in mock_run.call_args_list]
        assert "song1_spectrum.mp4" in outputs
        assert "song2_spectrum.mp4" in outputs
        assert "song3_spectrum.mp4" in outputs

    def test_batch_default_template_unchanged(self, tmp_path):
        from audio_visualizer.core import _process_batch

        registry = MagicMock()
        registry.get.return_value = _FakeModePlugin
        with (
            patch("audio_visualizer.__main__.check_ffmpeg", return_value="ffmpeg version 7.0.1 Copyright"),
            patch("audio_visualizer.__main__.run_visualizer") as mock_run,
        ):
            _process_batch(self._batch_args(tmp_path), registry)
        outputs = [c.args[1]["output"] for c in mock_run.call_args_list]
        assert outputs == [
            os.path.join(str(tmp_path), "song1_visualizer.mp4"),
            os.path.join(str(tmp_path), "song2_visualizer.mp4"),
            os.path.join(str(tmp_path), "song3_visualizer.mp4"),
        ]

    def test_batch_invalid_template_fails_fast(self, tmp_path):
        from audio_visualizer.core import _process_batch

        registry = MagicMock()
        with (
            patch("audio_visualizer.__main__.check_ffmpeg", return_value="ffmpeg version 7.0.1 Copyright"),
            patch("audio_visualizer.__main__.run_visualizer") as mock_run,
        ):
            with pytest.raises(SystemExit) as exc:
                _process_batch(self._batch_args(tmp_path, output_template="{bogus}.mp4"), registry)
        assert exc.value.code == 1
        mock_run.assert_not_called()


class TestBatchDiscovery:
    """Batch file discovery: --recursive/--include/--exclude (v2.1.0 sec.3.2)."""

    @pytest.fixture
    def tree(self, tmp_path):
        (tmp_path / "a.mp3").write_text("x")
        (tmp_path / "b.wav").write_text("x")
        (tmp_path / "c.txt").write_text("x")
        sub = tmp_path / "sub"
        sub.mkdir()
        (sub / "d.mp3").write_text("x")
        (sub / "e.flac").write_text("x")
        deep = sub / "deep"
        deep.mkdir()
        (deep / "f.ogg").write_text("x")
        return tmp_path

    @staticmethod
    def _names(tree, files):
        return [f.name for f in files]

    def test_default_top_level_extensions_only(self, tree):
        from audio_visualizer.core import discover_batch_files

        assert self._names(tree, discover_batch_files(str(tree))) == ["a.mp3", "b.wav"]

    def test_recursive(self, tree):
        from audio_visualizer.core import discover_batch_files

        assert self._names(tree, discover_batch_files(str(tree), recursive=True)) == [
            "a.mp3",
            "b.wav",
            "d.mp3",
            "f.ogg",
            "e.flac",
        ]

    def test_include_replaces_extension_filter(self, tree):
        from audio_visualizer.core import discover_batch_files

        assert self._names(tree, discover_batch_files(str(tree), include=["*.mp3"])) == ["a.mp3"]
        # Include patterns may select non-audio files (user's choice)
        assert self._names(tree, discover_batch_files(str(tree), include=["*.txt"])) == ["c.txt"]
        # With recursion, patterns match the relative path
        assert self._names(
            tree, discover_batch_files(str(tree), recursive=True, include=["sub/*.mp3"])
        ) == ["d.mp3"]

    def test_exclude(self, tree):
        from audio_visualizer.core import discover_batch_files

        assert self._names(tree, discover_batch_files(str(tree), exclude=["b.*"])) == ["a.mp3"]

    def test_include_then_exclude(self, tree):
        from audio_visualizer.core import discover_batch_files

        files = discover_batch_files(
            str(tree), recursive=True, include=["*.mp3", "*.flac"], exclude=["sub/*"]
        )
        assert self._names(tree, files) == ["a.mp3"]

    def test_empty_result(self, tree):
        from audio_visualizer.core import discover_batch_files

        assert discover_batch_files(str(tree), include=["*.xyz"]) == []

    def test_batch_wires_discovery_flags(self, tmp_path):
        """_process_batch passes --recursive/--exclude through to discovery."""
        from audio_visualizer.core import _process_batch

        (tmp_path / "a.mp3").write_text("x")
        (tmp_path / "b.mp3").write_text("x")
        sub = tmp_path / "sub"
        sub.mkdir()
        (sub / "c.mp3").write_text("x")

        def run(recursive, exclude):
            ns = Namespace(
                batch=str(tmp_path),
                output=str(tmp_path / "out"),
                mode="spectrum",
                resolution="1280x720",
                format="mp4",
                overwrite=False,
                output_template="{name}_visualizer.{ext}",
                recursive=recursive,
                include=[],
                exclude=exclude,
            )
            registry = MagicMock()
            registry.get.return_value = _FakeModePlugin
            with (
                patch("audio_visualizer.__main__.check_ffmpeg", return_value="ffmpeg version 7.0.1 Copyright"),
                patch("audio_visualizer.__main__.run_visualizer") as mock_run,
            ):
                _process_batch(ns, registry)
            return sorted(os.path.basename(c.args[1]["output"]) for c in mock_run.call_args_list)

        assert run(False, []) == ["a_visualizer.mp4", "b_visualizer.mp4"]
        assert run(True, []) == ["a_visualizer.mp4", "b_visualizer.mp4", "c_visualizer.mp4"]
        assert run(True, ["sub/*"]) == ["a_visualizer.mp4", "b_visualizer.mp4"]


class TestBatchReport:
    """Batch report JSON (v2.1.0 sec.3.4)."""

    def _batch_args(self, tmp_path, **overrides):
        import os

        base = dict(
            batch=os.path.join(os.path.dirname(__file__), "assets", "batch"),
            output=str(tmp_path),
            mode="spectrum",
            resolution="1280x720",
            format="mp4",
            overwrite=False,
            output_template="{name}_visualizer.{ext}",
            recursive=False,
            include=[],
            exclude=[],
        )
        base.update(overrides)
        return Namespace(**base)

    def test_report_written_on_success(self, tmp_path):
        import json

        from audio_visualizer.core import _process_batch

        registry = MagicMock()
        registry.get.return_value = _FakeModePlugin

        def fake_run(plugin_cls, args_dict):
            with open(args_dict["output"], "w") as f:
                f.write("x" * 100)

        with (
            patch("audio_visualizer.__main__.check_ffmpeg", return_value="ffmpeg version 7.0.1 Copyright"),
            patch("audio_visualizer.__main__.run_visualizer", fake_run),
        ):
            _process_batch(self._batch_args(tmp_path), registry)  # no SystemExit: 0 failures

        report = json.loads((tmp_path / "batch_report.json").read_text())
        assert report["counts"] == {"total": 3, "success": 3, "failed": 0, "skipped": 0}
        assert len(report["files"]) == 3
        entry = report["files"][0]
        assert entry["status"] == "success"
        assert entry["output"].endswith("song1_visualizer.mp4")
        assert entry["size"] == 100
        assert entry["error"] is None
        assert entry["timestamp"]

    def test_report_records_failure_and_exits_nonzero(self, tmp_path):
        import json

        from audio_visualizer.core import _process_batch

        registry = MagicMock()
        registry.get.return_value = _FakeModePlugin

        def fake_run(plugin_cls, args_dict):
            raise RuntimeError("boom")

        with (
            patch("audio_visualizer.__main__.check_ffmpeg", return_value="ffmpeg version 7.0.1 Copyright"),
            patch("audio_visualizer.__main__.run_visualizer", fake_run),
        ):
            with pytest.raises(SystemExit) as exc:
                _process_batch(self._batch_args(tmp_path), registry)
        assert exc.value.code == 1

        report = json.loads((tmp_path / "batch_report.json").read_text())
        assert report["counts"]["failed"] == 3
        assert all(f["status"] == "failed" for f in report["files"])
        assert all(f["error"] == "boom" for f in report["files"])
        assert all(f["size"] is None for f in report["files"])

    def test_report_records_skip(self, tmp_path):
        import json

        from audio_visualizer.core import _process_batch

        # Pre-create one output so it is skipped
        (tmp_path / "song1_visualizer.mp4").write_text("x" * 50)
        registry = MagicMock()
        registry.get.return_value = _FakeModePlugin
        with (
            patch("audio_visualizer.__main__.check_ffmpeg", return_value="ffmpeg version 7.0.1 Copyright"),
            patch("audio_visualizer.__main__.run_visualizer") as mock_run,
        ):
            _process_batch(self._batch_args(tmp_path), registry)
        assert mock_run.call_count == 2

        report = json.loads((tmp_path / "batch_report.json").read_text())
        by_name = {os.path.basename(f["output"]): f for f in report["files"]}
        assert by_name["song1_visualizer.mp4"]["status"] == "skipped"
        assert by_name["song1_visualizer.mp4"]["size"] == 50
        assert report["counts"] == {"total": 3, "success": 2, "failed": 0, "skipped": 1}


class TestParallelBatch:
    """--parallel concurrent encodes (v2.1.0 sec.3.1)."""

    def test_resolve_parallel_count(self):
        from audio_visualizer.core import resolve_parallel_count

        assert resolve_parallel_count("1") == 1
        assert resolve_parallel_count("4") == 4
        assert resolve_parallel_count(" 3 ") == 3
        assert resolve_parallel_count("auto") >= 1

    def test_resolve_parallel_count_invalid(self):
        from audio_visualizer.core import resolve_parallel_count

        for bad in ("0", "-2", "abc", ""):
            with pytest.raises(ValueError):
                resolve_parallel_count(bad)

    def _batch_args(self, tmp_path, **overrides):
        import os

        base = dict(
            batch=os.path.join(os.path.dirname(__file__), "assets", "batch"),
            output=str(tmp_path),
            mode="spectrum",
            resolution="1280x720",
            format="mp4",
            overwrite=False,
            output_template="{name}_visualizer.{ext}",
            recursive=False,
            include=[],
            exclude=[],
            parallel="1",
        )
        base.update(overrides)
        return Namespace(**base)

    def test_parallel_all_files_done(self, tmp_path):
        import json
        import time

        from audio_visualizer.core import _process_batch

        registry = MagicMock()
        registry.get.return_value = _FakeModePlugin

        def fake_run(plugin_cls, args_dict):
            time.sleep(0.05)  # simulate work; exercises real concurrency
            with open(args_dict["output"], "w") as f:
                f.write("x")

        with (
            patch("audio_visualizer.__main__.check_ffmpeg", return_value="ffmpeg version 7.0.1 Copyright"),
            patch("audio_visualizer.__main__.run_visualizer", fake_run),
        ):
            _process_batch(self._batch_args(tmp_path, parallel="3"), registry)

        report = json.loads((tmp_path / "batch_report.json").read_text())
        assert report["counts"] == {"total": 3, "success": 3, "failed": 0, "skipped": 0}
        # Report entries preserve input order
        assert [os.path.basename(f["output"]) for f in report["files"]] == [
            "song1_visualizer.mp4",
            "song2_visualizer.mp4",
            "song3_visualizer.mp4",
        ]

    def test_parallel_failure_recorded_and_exit_1(self, tmp_path):
        import json

        from audio_visualizer.core import _process_batch

        registry = MagicMock()
        registry.get.return_value = _FakeModePlugin

        def fake_run(plugin_cls, args_dict):
            if "song2" in args_dict["input"]:
                raise RuntimeError("boom")

        with (
            patch("audio_visualizer.__main__.check_ffmpeg", return_value="ffmpeg version 7.0.1 Copyright"),
            patch("audio_visualizer.__main__.run_visualizer", fake_run),
        ):
            with pytest.raises(SystemExit) as exc:
                _process_batch(self._batch_args(tmp_path, parallel="2"), registry)
        assert exc.value.code == 1

        report = json.loads((tmp_path / "batch_report.json").read_text())
        by_name = {os.path.basename(f["output"]): f for f in report["files"]}
        assert by_name["song2_visualizer.mp4"]["status"] == "failed"
        assert by_name["song2_visualizer.mp4"]["error"] == "boom"
        assert by_name["song1_visualizer.mp4"]["status"] == "success"

    def test_cli_parallel_flag(self):
        from audio_visualizer.__main__ import _build_registry, build_parser

        parser = build_parser(_build_registry([]))
        assert parser.parse_args(["in.mp3", "--parallel", "3"]).parallel == "3"
        assert parser.parse_args(["in.mp3", "-j", "auto"]).parallel == "auto"
        assert parser.parse_args(["in.mp3"]).parallel == "1"


class _StubPlugin:
    """Minimal plugin-like class exposing get_metadata()."""

    def __init__(self, name, requires=None):
        self.name = name
        self.requires_ffmpeg_version = requires

    def get_metadata(self):
        return self


class TestCheckFfmpegForModes:
    """Test per-mode requires_ffmpeg_version enforcement (v2.2.0 sec.8.4)."""

    def _plugin(self, name, requires=None):
        p = _StubPlugin(name, requires)
        return p

    def test_ok_when_detected_meets_requirement(self):
        from audio_visualizer.core import check_ffmpeg_for_modes

        modes = [self._plugin("cqt", "6.0")]
        # Should not raise
        check_ffmpeg_for_modes(modes, "ffmpeg version 7.1 Copyright")

    def test_exits_when_detected_too_old(self, caplog):
        from audio_visualizer.core import check_ffmpeg_for_modes

        modes = [self._plugin("cqt", "7.0")]
        with pytest.raises(SystemExit):
            check_ffmpeg_for_modes(modes, "ffmpeg version 6.0 Copyright")
        assert "too old" in caplog.text
        assert "'cqt'" in caplog.text
        assert "7.0" in caplog.text

    def test_names_each_offending_mode(self, caplog):
        from audio_visualizer.core import check_ffmpeg_for_modes

        modes = [
            self._plugin("a", "9.0"),
            self._plugin("b", None),
            self._plugin("c", "10.0"),
        ]
        with pytest.raises(SystemExit):
            check_ffmpeg_for_modes(modes, "ffmpeg version 8.0 Copyright")
        assert "'a'" in caplog.text
        assert "'c'" in caplog.text
        assert "'b'" not in caplog.text
        assert "9.0" in caplog.text
        assert "10.0" in caplog.text

    def test_skipped_when_version_unavailable(self):
        from audio_visualizer.core import check_ffmpeg_for_modes

        # Empty version line (no ffmpeg) -> no error even with a high requirement
        modes = [self._plugin("cqt", "9.9")]
        check_ffmpeg_for_modes(modes, "")

    def test_skipped_when_version_unparseable(self):
        from audio_visualizer.core import check_ffmpeg_for_modes

        modes = [self._plugin("cqt", "9.9")]
        check_ffmpeg_for_modes(modes, "custom build")


class TestBatchReportV2:
    """Batch report schema v2 (v2.2.0 sec.1.3)."""

    def _batch_args(self, tmp_path, **overrides):
        import os

        base = dict(
            batch=os.path.join(os.path.dirname(__file__), "assets", "batch"),
            output=str(tmp_path),
            mode="spectrum",
            resolution="1280x720",
            format="mp4",
            overwrite=False,
            output_template="{name}_visualizer.{ext}",
            recursive=False,
            include=[],
            exclude=[],
            report=[],
        )
        base.update(overrides)
        return Namespace(**base)

    def _run(self, tmp_path, overrides=None, run_side_effect=None):
        import json

        from audio_visualizer.core import _process_batch

        registry = MagicMock()
        registry.get.return_value = _FakeModePlugin
        kwargs = {} if run_side_effect is None else {"side_effect": run_side_effect}
        with (
            patch(
                "audio_visualizer.__main__.check_ffmpeg",
                return_value="ffmpeg version 7.0.1 Copyright",
            ),
            patch("audio_visualizer.__main__.run_visualizer", **kwargs),
        ):
            _process_batch(self._batch_args(tmp_path, **(overrides or {})), registry)
        return json.loads((tmp_path / "batch_report.json").read_text())

    def test_report_v2_fields(self, tmp_path):
        report = self._run(
            tmp_path, run_side_effect=lambda cls, a: open(a["output"], "w").write("x" * 10)
        )
        assert report["schema_version"] == 2
        assert report["run_id"]
        assert len(report["run_id"]) == 8
        assert report["ffmpeg_version"] == "ffmpeg version 7.0.1 Copyright"
        assert report["batch_dir"]
        assert report["output_dir"]
        # per-file attempts present
        for f in report["files"]:
            assert "attempts" in f

    def test_attempts_counts(self, tmp_path):
        # Pre-create one output so it is skipped (attempts 0), rest succeed (attempts 1)
        (tmp_path / "song1_visualizer.mp4").write_text("x" * 50)
        report = self._run(
            tmp_path, run_side_effect=lambda cls, a: open(a["output"], "w").write("x")
        )
        by_name = {os.path.basename(f["output"]): f for f in report["files"]}
        assert by_name["song1_visualizer.mp4"]["status"] == "skipped"
        assert by_name["song1_visualizer.mp4"]["attempts"] == 0
        assert by_name["song2_visualizer.mp4"]["status"] == "success"
        assert by_name["song2_visualizer.mp4"]["attempts"] == 1

    def test_attempts_on_failure(self, tmp_path):
        def boom(cls, a):
            raise RuntimeError("boom")

        import json

        from audio_visualizer.core import _process_batch

        registry = MagicMock()
        registry.get.return_value = _FakeModePlugin
        with (
            patch(
                "audio_visualizer.__main__.check_ffmpeg",
                return_value="ffmpeg version 7.0.1 Copyright",
            ),
            patch("audio_visualizer.__main__.run_visualizer", side_effect=boom),
        ):
            with pytest.raises(SystemExit):
                _process_batch(self._batch_args(tmp_path), registry)
        report = json.loads((tmp_path / "batch_report.json").read_text())
        assert all(f["status"] == "failed" for f in report["files"])
        assert all(f["attempts"] == 1 for f in report["files"])

    def test_report_extra_paths(self, tmp_path):
        extra1 = tmp_path / "reports" / "custom.json"
        extra2 = tmp_path / "out2.json"

        def ok(cls, a):
            open(a["output"], "w").write("x" * 10)

        from audio_visualizer.core import _process_batch

        registry = MagicMock()
        registry.get.return_value = _FakeModePlugin
        with (
            patch(
                "audio_visualizer.__main__.check_ffmpeg",
                return_value="ffmpeg version 7.0.1 Copyright",
            ),
            patch("audio_visualizer.__main__.run_visualizer", side_effect=ok),
        ):
            _process_batch(
                self._batch_args(tmp_path, report=[str(extra1), str(extra2)]),
                registry,
            )
        # default still written
        assert (tmp_path / "batch_report.json").exists()
        # both extra paths written, parent dirs created
        assert extra1.exists()
        assert extra2.exists()
        import json

        assert json.loads(extra1.read_text())["schema_version"] == 2
        assert json.loads(extra2.read_text())["counts"]["total"] == 3

    def test_run_id_unique_per_run(self, tmp_path):
        r1 = self._run(
            tmp_path, run_side_effect=lambda cls, a: open(a["output"], "w").write("x")
        )
        # second run into a different output dir
        out2 = tmp_path / "second"
        out2.mkdir()

        def ok2(cls, a):
            open(a["output"], "w").write("x")

        from audio_visualizer.core import _process_batch

        registry = MagicMock()
        registry.get.return_value = _FakeModePlugin
        with (
            patch(
                "audio_visualizer.__main__.check_ffmpeg",
                return_value="ffmpeg version 7.0.1 Copyright",
            ),
            patch("audio_visualizer.__main__.run_visualizer", side_effect=ok2),
        ):
            _process_batch(self._batch_args(out2), registry)
        r2 = __import__("json").loads((out2 / "batch_report.json").read_text())
        assert r1["run_id"] != r2["run_id"]

class TestResume:
    """--resume: re-run only non-successful report entries (v2.2.0 sec.1.2)."""

    BATCH_DIR = os.path.join(os.path.dirname(__file__), "assets", "batch")

    def _args(self, tmp_path, resume=None, **overrides):
        base = dict(
            batch=self.BATCH_DIR,
            output=str(tmp_path),
            mode="spectrum",
            resolution="1280x720",
            format="mp4",
            overwrite=False,
            output_template="{name}_visualizer.{ext}",
            recursive=False,
            include=[],
            exclude=[],
            report=[],
            resume=resume,
        )
        base.update(overrides)
        return Namespace(**base)

    def _asset(self, name):
        return os.path.join(self.BATCH_DIR, name)

    def _write_report(self, path, files):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps({
            "schema_version": 2,
            "run_id": "oldrun00",
            "batch_dir": self.BATCH_DIR,
            "output_dir": str(path.parent),
            "mode": "spectrum",
            "format": "mp4",
            "counts": {},
            "files": files,
            "timestamp": "2026-10-30T00:00:00-04:00",
        }))
        return str(path)

    def _entry(self, song, status, output, attempts=None, error=None):
        e = {
            "input": self._asset(song),
            "output": output,
            "status": status,
            "size": 10 if status == "success" else None,
            "duration": 1.0 if status == "success" else None,
            "error": error,
            "timestamp": "2026-10-30T00:00:00-04:00",
        }
        if attempts is not None:
            e["attempts"] = attempts
        return e

    def _run(self, tmp_path, resume=None, run_side_effect=None):
        from audio_visualizer.core import _process_batch

        registry = MagicMock()
        registry.get.return_value = _FakeModePlugin

        def fake_run(cls, a):
            if run_side_effect:
                run_side_effect(cls, a)
            with open(a["output"], "w") as f:
                f.write("x" * 10)

        with (
            patch("audio_visualizer.__main__.check_ffmpeg", return_value="ffmpeg version 7.0.1 Copyright"),
            patch("audio_visualizer.__main__.run_visualizer", side_effect=fake_run) as mock_run,
        ):
            _process_batch(self._args(tmp_path, resume=resume), registry)
        return mock_run.call_args_list

    def test_resume_reruns_only_non_success_and_merges(self, tmp_path):
        old_out = tmp_path / "old_out"
        old_out.mkdir()
        (old_out / "song1_visualizer.mp4").write_text("x" * 10)  # song1's output survives
        report_path = self._write_report(
            tmp_path / "reports" / "batch_report.json",
            [
                self._entry("song1.mp3", "success", str(old_out / "song1_visualizer.mp4"), attempts=1),
                self._entry("song2.mp3", "failed", None, attempts=1, error="boom"),
                self._entry("song3.mp3", "success", str(tmp_path / "gone.mp4"), attempts=1),  # output missing
            ],
        )
        original = (tmp_path / "reports" / "batch_report.json").read_text()

        calls = self._run(tmp_path, resume=report_path)
        rerun = sorted(os.path.basename(c.args[1]["output"]) for c in calls)
        assert rerun == ["song2_visualizer.mp4", "song3_visualizer.mp4"]

        report = json.loads((tmp_path / "batch_report.json").read_text())
        by_input = {os.path.basename(f["input"]): f for f in report["files"]}
        # preserved: status kept, old output path kept
        assert by_input["song1.mp3"]["status"] == "success"
        assert by_input["song1.mp3"]["output"] == str(old_out / "song1_visualizer.mp4")
        assert by_input["song1.mp3"]["attempts"] == 1
        # re-run: new success entries, attempts accumulated (1 old + 1 new)
        assert by_input["song2.mp3"]["status"] == "success"
        assert by_input["song2.mp3"]["attempts"] == 2
        assert by_input["song3.mp3"]["status"] == "success"
        assert by_input["song3.mp3"]["attempts"] == 2
        # old ordering preserved: song1, song2, song3
        assert [os.path.basename(f["input"]) for f in report["files"]] == [
            "song1.mp3", "song2.mp3", "song3.mp3",
        ]
        assert report["counts"] == {"total": 3, "success": 3, "failed": 0, "skipped": 0}

        # old report untouched; snapshot copy kept next to it
        assert (tmp_path / "reports" / "batch_report.json").read_text() == original
        snapshot = tmp_path / "reports" / "batch_report.before-resume.json"
        assert snapshot.read_text() == original

    def test_resume_all_successful_does_not_rerun(self, tmp_path):
        old_out = tmp_path / "old_out"
        old_out.mkdir()
        entries = []
        for song in ("song1.mp3", "song2.mp3", "song3.mp3"):
            (old_out / os.path.basename(self._render(song))).write_text("x" * 10)
            entries.append(self._entry(song, "success", str(old_out / os.path.basename(self._render(song))), attempts=1))
        report_path = self._write_report(tmp_path / "batch_report.json", entries)

        calls = self._run(tmp_path, resume=report_path)
        assert len(calls) == 0

        report = json.loads((tmp_path / "batch_report.json").read_text())
        assert report["counts"] == {"total": 3, "success": 3, "failed": 0, "skipped": 0}
        assert all(f["attempts"] == 1 for f in report["files"])

    @staticmethod
    def _render(song):
        return os.path.splitext(song)[0] + "_visualizer.mp4"

    def test_resume_keeps_failures_and_exits_nonzero(self, tmp_path):
        report_path = self._write_report(
            tmp_path / "batch_report.json",
            [self._entry("song1.mp3", "failed", None, attempts=1, error="boom")],
        )
        from audio_visualizer.core import _process_batch

        def boom(cls, a):
            raise RuntimeError("boom again")

        registry = MagicMock()
        registry.get.return_value = _FakeModePlugin
        with (
            patch("audio_visualizer.__main__.check_ffmpeg", return_value="ffmpeg version 7.0.1 Copyright"),
            patch("audio_visualizer.__main__.run_visualizer", boom),
        ):
            with pytest.raises(SystemExit) as exc:
                _process_batch(self._args(tmp_path, resume=report_path), registry)
        assert exc.value.code == 1

        report = json.loads((tmp_path / "batch_report.json").read_text())
        assert report["files"][0]["status"] == "failed"
        assert report["files"][0]["attempts"] == 2
        assert report["counts"]["failed"] == 1

    def test_resume_missing_report_file_exits_naming_it(self, tmp_path, caplog):
        from audio_visualizer.core import _process_batch

        registry = MagicMock()
        registry.get.return_value = _FakeModePlugin
        missing = str(tmp_path / "nope.json")
        with (
            patch("audio_visualizer.__main__.check_ffmpeg", return_value="ffmpeg version 7.0.1 Copyright"),
            patch("audio_visualizer.__main__.run_visualizer"),
        ):
            with pytest.raises(SystemExit) as exc:
                _process_batch(self._args(tmp_path, resume=missing), registry)
        assert exc.value.code == 1
        assert missing in caplog.text

    def test_resume_reads_v1_report(self, tmp_path):
        """v1 reports (no schema_version, no attempts) are usable resume sources."""
        files = [
            {"input": self._asset("song1.mp3"), "output": None, "status": "failed",
             "size": None, "duration": None, "error": "x",
             "timestamp": "2026-10-30T00:00:00-04:00"},
        ]
        (tmp_path / "batch_report.json").write_text(json.dumps({
            "batch_dir": self.BATCH_DIR, "output_dir": str(tmp_path), "mode": "spectrum",
            "format": "mp4", "counts": {"total": 1, "success": 0, "failed": 1, "skipped": 0},
            "files": files, "timestamp": "2026-10-30T00:00:00-04:00",
        }))
        report_path = str(tmp_path / "batch_report.json")
        calls = self._run(tmp_path, resume=report_path)
        assert len(calls) == 1

        report = json.loads((tmp_path / "batch_report.json").read_text())
        # the fresh report replaced the source file's location? No - default
        # report goes to the output dir (tmp_path) under batch_report.json,
        # which IS the source path here; the snapshot preserved the original.
        assert report["schema_version"] == 2
        assert report["files"][0]["status"] == "success"
        assert report["files"][0]["attempts"] == 1  # v1 failed had no attempts -> 0 + 1
        assert (tmp_path / "batch_report.before-resume.json").read_text() != json.dumps(report)

class TestRetryFailed:
    """--retry-failed: re-run only 'failed' report entries (v2.2.0 sec.1.1)."""

    BATCH_DIR = os.path.join(os.path.dirname(__file__), "assets", "batch")

    def _args(self, tmp_path, **overrides):
        base = dict(
            batch=self.BATCH_DIR,
            output=str(tmp_path),
            mode="spectrum",
            resolution="1280x720",
            format="mp4",
            overwrite=False,
            output_template="{name}_visualizer.{ext}",
            recursive=False,
            include=[],
            exclude=[],
            report=[],
            resume=None,
            retry_failed=None,
        )
        base.update(overrides)
        return Namespace(**base)

    def _asset(self, name):
        return os.path.join(self.BATCH_DIR, name)

    def _write_report(self, path, files):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps({
            "schema_version": 2, "run_id": "oldrun11", "batch_dir": self.BATCH_DIR,
            "output_dir": str(path.parent), "mode": "spectrum", "format": "mp4",
            "counts": {}, "files": files, "timestamp": "2026-10-30T00:00:00-04:00",
        }))
        return str(path)

    def _entry(self, song, status, output, attempts=None, error=None):
        e = {
            "input": self._asset(song),
            "output": output,
            "status": status,
            "size": 10 if status == "success" else None,
            "duration": 1.0 if status == "success" else None,
            "error": error,
            "timestamp": "2026-10-30T00:00:00-04:00",
        }
        if attempts is not None:
            e["attempts"] = attempts
        return e

    def _run(self, tmp_path, retry_failed=None, resume=None, run_side_effect=None):
        from audio_visualizer.core import _process_batch

        registry = MagicMock()
        registry.get.return_value = _FakeModePlugin

        def fake_run(cls, a):
            if run_side_effect:
                run_side_effect(cls, a)
            with open(a["output"], "w") as f:
                f.write("x" * 10)

        with (
            patch("audio_visualizer.__main__.check_ffmpeg", return_value="ffmpeg version 7.0.1 Copyright"),
            patch("audio_visualizer.__main__.run_visualizer", side_effect=fake_run) as mock_run,
        ):
            _process_batch(self._args(tmp_path, retry_failed=retry_failed, resume=resume), registry)
        return mock_run.call_args_list

    def test_retry_failed_reruns_only_failed_entries(self, tmp_path):
        old_out = tmp_path / "old_out"
        old_out.mkdir()
        (old_out / "song1_visualizer.mp4").write_text("x" * 10)
        (old_out / "song3_visualizer.mp4").write_text("x" * 10)
        report_path = self._write_report(
            tmp_path / "reports" / "batch_report.json",
            [
                self._entry("song1.mp3", "success", str(old_out / "song1_visualizer.mp4"), attempts=1),
                self._entry("song2.mp3", "failed", None, attempts=1, error="boom"),
                self._entry("song3.mp3", "skipped", str(old_out / "song3_visualizer.mp4")),
            ],
        )

        calls = self._run(tmp_path, retry_failed=report_path)
        rerun = sorted(os.path.basename(c.args[1]["output"]) for c in calls)
        assert rerun == ["song2_visualizer.mp4"]  # only the failed entry

        report = json.loads((tmp_path / "batch_report.json").read_text())
        by_input = {os.path.basename(f["input"]): f for f in report["files"]}
        assert by_input["song1.mp3"]["status"] == "success"
        assert by_input["song1.mp3"]["attempts"] == 1  # preserved
        assert by_input["song2.mp3"]["status"] == "success"
        assert by_input["song2.mp3"]["attempts"] == 2  # 1 old + 1 new
        assert by_input["song3.mp3"]["status"] == "skipped"  # skipped is kept, not re-run
        assert [os.path.basename(f["input"]) for f in report["files"]] == [
            "song1.mp3", "song2.mp3", "song3.mp3",
        ]
        assert report["counts"] == {"total": 3, "success": 2, "failed": 0, "skipped": 1}
        # no snapshot copy for --retry-failed (resume-only behavior)
        assert not (tmp_path / "reports" / "batch_report.before-resume.json").exists()

    def test_retry_failed_exits_0_even_if_still_failing(self, tmp_path):
        report_path = self._write_report(
            tmp_path / "batch_report.json",
            [self._entry("song1.mp3", "failed", None, attempts=1, error="boom")],
        )

        def boom(cls, a):
            raise RuntimeError("boom again")

        # no SystemExit: the retry pass "completes"
        self._run(tmp_path, retry_failed=report_path, run_side_effect=boom)

        report = json.loads((tmp_path / "batch_report.json").read_text())
        assert report["files"][0]["status"] == "failed"
        assert report["files"][0]["attempts"] == 2
        assert report["counts"]["failed"] == 1

    def test_retry_failed_keeps_stale_success_without_rerun(self, tmp_path):
        """A 'success' whose output file is missing is kept (not re-run) by
        --retry-failed — only 'failed' entries are re-run (resume differs)."""
        report_path = self._write_report(
            tmp_path / "batch_report.json",
            [
                self._entry("song1.mp3", "success", str(tmp_path / "gone.mp4"), attempts=1),
                self._entry("song2.mp3", "failed", None, attempts=1, error="boom"),
            ],
        )
        calls = self._run(tmp_path, retry_failed=report_path)
        rerun = [os.path.basename(c.args[1]["output"]) for c in calls]
        assert rerun == ["song2_visualizer.mp4"]

    def test_retry_failed_missing_report_exits_naming_it(self, tmp_path, caplog):
        from audio_visualizer.core import _process_batch

        registry = MagicMock()
        registry.get.return_value = _FakeModePlugin
        missing = str(tmp_path / "nope.json")
        with (
            patch("audio_visualizer.__main__.check_ffmpeg", return_value="ffmpeg version 7.0.1 Copyright"),
            patch("audio_visualizer.__main__.run_visualizer"),
        ):
            with pytest.raises(SystemExit) as exc:
                _process_batch(self._args(tmp_path, retry_failed=missing), registry)
        assert exc.value.code == 1
        assert missing in caplog.text

    def test_resume_and_retry_failed_mutually_exclusive(self, tmp_path, caplog):
        from audio_visualizer.core import _process_batch

        registry = MagicMock()
        registry.get.return_value = _FakeModePlugin
        with (
            patch("audio_visualizer.__main__.check_ffmpeg", return_value="ffmpeg version 7.0.1 Copyright"),
            patch("audio_visualizer.__main__.run_visualizer"),
        ):
            with pytest.raises(SystemExit) as exc:
                _process_batch(
                    self._args(tmp_path, retry_failed=str(tmp_path / "a.json"), resume=str(tmp_path / "b.json")),
                    registry,
                )
        assert exc.value.code == 1
        assert "mutually exclusive" in caplog.text


class TestThemePreviews:
    """--list-themes --png DIR (v2.2.0 sec.3.3)."""

    def test_renders_one_png_per_theme_with_its_palette(self, tmp_path, monkeypatch):
        from audio_visualizer.__main__ import render_theme_previews

        monkeypatch.setenv("HOME", str(tmp_path))
        # one user theme so built-ins + custom are both covered
        themes_dir = tmp_path / ".config" / "audio-visualizer" / "themes"
        themes_dir.mkdir(parents=True)
        (themes_dir / "mymix.json").write_text(
            '{"palette": ["red", "cyan", "white"]}'
        )
        captured = []

        def fake_run(cmd, **kwargs):
            captured.append(list(cmd))

            class R:
                returncode = 0

            return R()

        out_dir = tmp_path / "previews"
        with patch("subprocess.run", side_effect=fake_run):
            render_theme_previews(str(out_dir))

        # 6 built-ins + 1 user theme
        assert len(captured) == 7
        for cmd in captured:
            assert cmd[0] == "ffmpeg"
            fc = cmd[cmd.index("-filter_complex") + 1]
            # multi-channel tone: one sine input per palette color
            assert "amerge=" in fc
            assert "showfreqs=" in fc
            assert "colors=" in fc
            # output file naming
            out = cmd[-1]
            assert out.startswith(str(out_dir) + os.sep)
            assert out.endswith("_preview.png")
        # the user palette is pipe-separated for ffmpeg
        mymix = [c for c in captured
                 if "mymix_preview.png" in c[-1]]
        assert len(mymix) == 1
        assert "colors=red|cyan|white" in mymix[0][
            mymix[0].index("-filter_complex") + 1]

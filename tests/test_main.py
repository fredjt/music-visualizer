"""Tests for main application."""

from argparse import Namespace
from unittest.mock import MagicMock, patch

import pytest

from audio_visualizer.__main__ import (
    check_ffmpeg,
    detect_hwaccel,
    get_audio_duration,
    merge_config,
)


class TestCheckFfmpeg:
    """Test ffmpeg checking."""

    def test_ffmpeg_found(self):
        """Test when ffmpeg is found."""
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stdout="ffmpeg version 5.0\n")
            result = check_ffmpeg()
            assert result is True

    def test_ffmpeg_not_found(self, capsys):
        """Test when ffmpeg is not found."""
        with patch("subprocess.run") as mock_run:
            mock_run.side_effect = FileNotFoundError()
            with pytest.raises(SystemExit):
                check_ffmpeg()
            captured = capsys.readouterr()
            assert "ERROR: ffmpeg is required" in captured.err or captured.out


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

    def test_specific_accel_not_available(self, capsys):
        """Test specific acceleration not available."""
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stdout="")
            result = detect_hwaccel("nvenc")
            assert result == "sw"
            captured = capsys.readouterr()
            assert "WARNING" in captured.out


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
            theme=None,
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

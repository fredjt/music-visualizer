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

    def test_ffmpeg_not_found(self, caplog):
        """Test when ffmpeg is not found."""
        with patch("subprocess.run") as mock_run:
            mock_run.side_effect = FileNotFoundError()
            with pytest.raises(SystemExit):
                check_ffmpeg()
        assert "ffmpeg is required" in caplog.text


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
            theme=None,
            validate_config=False,
            retry=0,
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
            with patch("audio_visualizer.__main__.check_ffmpeg"):
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
                            batch=None,
                            list_plugins=False,
                            install_plugin=None,
                            config=False,
                            save_config=False,
                            overwrite=False,
                            theme=None,
                            validate_config=False,
                            retry=0,
                            validate=False,
                            dry_run=False,
                        )
                        main()
                        assert mock_merge.called

    def test_parse_resolution(self):
        """Test parsing resolution argument."""
        from audio_visualizer.__main__ import main

        with patch("sys.argv", ["audio-visualizer", "test.mp3", "-r", "1920x1080"]):
            with patch("audio_visualizer.__main__.check_ffmpeg"):
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
                            batch=None,
                            list_plugins=False,
                            install_plugin=None,
                            config=False,
                            save_config=False,
                            overwrite=False,
                            theme=None,
                            validate_config=False,
                            retry=0,
                            validate=False,
                            dry_run=False,
                        )
                        main()
                        assert mock_merge.called

    def test_parse_theme(self):
        """Test parsing theme argument."""
        from audio_visualizer.__main__ import main

        with patch("sys.argv", ["audio-visualizer", "test.mp3", "--theme", "neon"]):
            with patch("audio_visualizer.__main__.check_ffmpeg"):
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
                            batch=None,
                            list_plugins=False,
                            install_plugin=None,
                            config=False,
                            save_config=False,
                            overwrite=False,
                            theme="neon",
                            validate_config=False,
                            retry=0,
                            validate=False,
                            dry_run=False,
                        )
                        main()
                        assert mock_merge.called

    def test_parse_colors(self):
        """Test parsing colors argument."""
        from audio_visualizer.__main__ import main

        with patch("sys.argv", ["audio-visualizer", "test.mp3", "--colors", "red,blue,green"]):
            with patch("audio_visualizer.__main__.check_ffmpeg"):
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
                            batch=None,
                            list_plugins=False,
                            install_plugin=None,
                            config=False,
                            save_config=False,
                            overwrite=False,
                            theme=None,
                            validate_config=False,
                            retry=0,
                            validate=False,
                            dry_run=False,
                        )
                        main()
                        assert mock_merge.called

    def test_parse_format(self):
        """Test parsing format argument."""
        from audio_visualizer.__main__ import main

        with patch("sys.argv", ["audio-visualizer", "test.mp3", "-f", "webm"]):
            with patch("audio_visualizer.__main__.check_ffmpeg"):
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
                            batch=None,
                            list_plugins=False,
                            install_plugin=None,
                            config=False,
                            save_config=False,
                            overwrite=False,
                            theme=None,
                            validate_config=False,
                            retry=0,
                            validate=False,
                            dry_run=False,
                        )
                        main()
                        assert mock_merge.called

    def test_parse_accel(self):
        """Test parsing accel argument."""
        from audio_visualizer.__main__ import main

        with patch("sys.argv", ["audio-visualizer", "test.mp3", "--accel", "nvenc"]):
            with patch("audio_visualizer.__main__.check_ffmpeg"):
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
                            batch=None,
                            list_plugins=False,
                            install_plugin=None,
                            config=False,
                            save_config=False,
                            overwrite=False,
                            theme=None,
                            validate_config=False,
                            retry=0,
                            validate=False,
                            dry_run=False,
                        )
                        main()
                        assert mock_merge.called

    def test_parse_mode(self):
        """Test parsing mode argument."""
        from audio_visualizer.__main__ import main

        with patch("sys.argv", ["audio-visualizer", "test.mp3", "--mode", "waveform"]):
            with patch("audio_visualizer.__main__.check_ffmpeg"):
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
                            batch=None,
                            list_plugins=False,
                            install_plugin=None,
                            config=False,
                            save_config=False,
                            overwrite=False,
                            theme=None,
                            validate_config=False,
                            retry=0,
                            validate=False,
                            dry_run=False,
                        )
                        main()
                        assert mock_merge.called

    def test_parse_output(self):
        """Test parsing output argument."""
        from audio_visualizer.__main__ import main

        with patch("sys.argv", ["audio-visualizer", "test.mp3", "-o", "output.mp4"]):
            with patch("audio_visualizer.__main__.check_ffmpeg"):
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
                            batch=None,
                            list_plugins=False,
                            install_plugin=None,
                            config=False,
                            save_config=False,
                            overwrite=False,
                            theme=None,
                            validate_config=False,
                            retry=0,
                            validate=False,
                            dry_run=False,
                        )
                        main()
                        assert mock_merge.called

    def test_parse_image(self):
        """Test parsing image argument."""
        from audio_visualizer.__main__ import main

        with patch("sys.argv", ["audio-visualizer", "test.mp3", "--image", "art.jpg"]):
            with patch("audio_visualizer.__main__.check_ffmpeg"):
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
                            batch=None,
                            list_plugins=False,
                            install_plugin=None,
                            config=False,
                            save_config=False,
                            overwrite=False,
                            theme=None,
                            validate_config=False,
                            retry=0,
                            validate=False,
                            dry_run=False,
                        )
                        main()
                        assert mock_merge.called

    def test_parse_batch(self):
        """Test parsing batch argument."""
        from audio_visualizer.__main__ import main

        with patch("sys.argv", ["audio-visualizer", "-b", "./music/"]):
            with patch("audio_visualizer.__main__.check_ffmpeg"):
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
                            validate=False,
                            dry_run=False,
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
                        batch=None,
                        list_plugins=True,
                        install_plugin=None,
                        config=False,
                        save_config=False,
                        overwrite=False,
                        theme=None,
                        validate_config=False,
                        retry=0,
                        validate=False,
                        dry_run=False,
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
                            batch=None,
                            list_plugins=False,
                            install_plugin="my_plugin.py",
                            config=False,
                            save_config=False,
                            overwrite=False,
                            theme=None,
                            validate_config=False,
                            retry=0,
                            validate=False,
                            dry_run=False,
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
            with patch("audio_visualizer.__main__.check_ffmpeg"):
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
                            validate=False,
                            dry_run=False,
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
            with patch("audio_visualizer.__main__.check_ffmpeg"):
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
                            batch=None,
                            list_plugins=False,
                            install_plugin=None,
                            config=False,
                            save_config=False,
                            overwrite=False,
                            theme=None,
                            validate_config=False,
                            retry=0,
                            validate=False,
                            dry_run=False,
                        )
                        main()
                        assert mock_merge.called

    def test_parse_preset(self):
        """Test parsing preset argument."""
        from audio_visualizer.__main__ import main

        with patch("sys.argv", ["audio-visualizer", "test.mp3", "--preset", "fast"]):
            with patch("audio_visualizer.__main__.check_ffmpeg"):
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
                            batch=None,
                            list_plugins=False,
                            install_plugin=None,
                            config=False,
                            save_config=False,
                            overwrite=False,
                            theme=None,
                            validate_config=False,
                            retry=0,
                            validate=False,
                            dry_run=False,
                        )
                        main()
                        assert mock_merge.called

    def test_parse_fps(self):
        """Test parsing fps argument."""
        from audio_visualizer.__main__ import main

        with patch("sys.argv", ["audio-visualizer", "test.mp3", "--fps", "60"]):
            with patch("audio_visualizer.__main__.check_ffmpeg"):
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
                            batch=None,
                            list_plugins=False,
                            install_plugin=None,
                            config=False,
                            save_config=False,
                            overwrite=False,
                            theme=None,
                            validate_config=False,
                            retry=0,
                            validate=False,
                            dry_run=False,
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
            with patch("audio_visualizer.__main__.check_ffmpeg"):
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
                            batch=None,
                            list_plugins=False,
                            install_plugin=None,
                            config=False,
                            save_config=False,
                            overwrite=False,
                            theme=None,
                            validate_config=False,
                            retry=0,
                            validate=False,
                            dry_run=False,
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
            with patch("audio_visualizer.__main__.check_ffmpeg"):
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
                            batch=None,
                            list_plugins=False,
                            install_plugin=None,
                            config=False,
                            save_config=False,
                            overwrite=False,
                            theme=None,
                            validate_config=False,
                            retry=3,
                            validate=False,
                            dry_run=False,
                        )
                        main()

    def test_retry_flag_short(self):
        """Test that -R short flag works."""
        from argparse import Namespace

        from audio_visualizer.__main__ import main

        with patch("sys.argv", ["audio-visualizer", "test.mp3", "-R", "2"]):
            with patch("audio_visualizer.__main__.check_ffmpeg"):
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
                            batch=None,
                            list_plugins=False,
                            install_plugin=None,
                            config=False,
                            save_config=False,
                            overwrite=False,
                            theme=None,
                            validate_config=False,
                            retry=2,
                            validate=False,
                            dry_run=False,
                        )
                        main()

    def test_retry_passed_to_visualizer(self):
        """Test that retry count is passed to run_visualizer."""
        from argparse import Namespace

        from audio_visualizer.__main__ import main

        with patch("sys.argv", ["audio-visualizer", "test.mp3", "--retry", "5"]):
            with patch("audio_visualizer.__main__.check_ffmpeg"):
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
                            batch=None,
                            list_plugins=False,
                            install_plugin=None,
                            config=False,
                            save_config=False,
                            overwrite=False,
                            theme=None,
                            validate_config=False,
                            retry=5,
                            validate=False,
                            dry_run=False,
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
            with patch("audio_visualizer.__main__.check_ffmpeg"):
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
                            batch=None,
                            list_plugins=False,
                            install_plugin=None,
                            config=False,
                            save_config=False,
                            overwrite=False,
                            theme=None,
                            validate_config=False,
                            retry=0,
                            validate=False,
                            dry_run=False,
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

    def build_filter(self, width, height, fps, colors=None):
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
                    batch=None,
                    list_plugins=False,
                    install_plugin=None,
                    config=False,
                    save_config=False,
                    overwrite=False,
                    theme=None,
                    validate_config=False,
                    retry=0,
                    validate=False,
                    dry_run=True,
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
                    batch="tests/assets/",
                    list_plugins=False,
                    install_plugin=None,
                    config=False,
                    save_config=False,
                    overwrite=False,
                    theme=None,
                    validate_config=False,
                    retry=0,
                    validate=False,
                    dry_run=True,
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
                    batch=None,
                    list_plugins=False,
                    install_plugin=None,
                    config=False,
                    save_config=False,
                    overwrite=False,
                    theme=None,
                    validate_config=False,
                    retry=0,
                    validate=False,
                    dry_run=True,
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
                    batch=None,
                    list_plugins=False,
                    install_plugin=None,
                    config=False,
                    save_config=False,
                    overwrite=False,
                    theme=None,
                    validate_config=False,
                    retry=0,
                    validate=False,
                    dry_run=True,
                )
                with patch("audio_visualizer.__main__.detect_hwaccel", return_value="sw"):
                    main()

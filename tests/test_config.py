"""Tests for configuration management."""

import os
from pathlib import Path
from unittest.mock import patch

import pytest

from audio_visualizer.config import (
    CONFIG_VALIDATORS,
    DEFAULT_CONFIG,
    load_config,
    load_env_vars,
    merge_config,
    save_config,
)


class TestConfigValidators:
    """Test configuration value validators."""

    def test_resolution_validator_valid(self):
        assert CONFIG_VALIDATORS["resolution"]("1920x1080") is True
        assert CONFIG_VALIDATORS["resolution"]("1280x720") is True

    def test_resolution_validator_invalid(self):
        assert CONFIG_VALIDATORS["resolution"]("invalid") is False
        assert CONFIG_VALIDATORS["resolution"]("1920") is False
        assert CONFIG_VALIDATORS["resolution"]("") is False

    def test_format_validator_valid(self):
        for fmt in ["mp4", "mkv", "webm", "avi", "mov", "flv"]:
            assert CONFIG_VALIDATORS["format"](fmt) is True

    def test_format_validator_invalid(self):
        assert CONFIG_VALIDATORS["format"]("invalid") is False
        assert CONFIG_VALIDATORS["format"]("mp3") is False

    def test_fps_validator_valid(self):
        assert CONFIG_VALIDATORS["fps"](30) is True
        assert CONFIG_VALIDATORS["fps"](60) is True
        assert CONFIG_VALIDATORS["fps"](1) is True
        assert CONFIG_VALIDATORS["fps"](240) is True

    def test_fps_validator_invalid(self):
        assert CONFIG_VALIDATORS["fps"](0) is False
        assert CONFIG_VALIDATORS["fps"](241) is False
        assert CONFIG_VALIDATORS["fps"](-1) is False

    def test_crf_validator_valid(self):
        assert CONFIG_VALIDATORS["crf"](0) is True
        assert CONFIG_VALIDATORS["crf"](23) is True
        assert CONFIG_VALIDATORS["crf"](51) is True

    def test_crf_validator_invalid(self):
        assert CONFIG_VALIDATORS["crf"](-1) is False
        assert CONFIG_VALIDATORS["crf"](52) is False

    def test_accel_validator_valid(self):
        for accel in ["auto", "nvenc", "qsv", "vaapi", "disabled"]:
            assert CONFIG_VALIDATORS["accel"](accel) is True

    def test_accel_validator_invalid(self):
        assert CONFIG_VALIDATORS["accel"]("invalid") is False


class TestLoadConfig:
    """Test configuration loading."""

    def test_load_default_config_no_file(self, tmp_path):
        """Test loading default config when no file exists."""
        with patch("audio_visualizer.config.get_config_path") as mock_path:
            mock_path.return_value = str(tmp_path / "nonexistent.yml")
            config = load_config()
            assert {k: v for k, v in config.items() if k != "plugins"} == DEFAULT_CONFIG
            assert config["plugins"] == {}

    def test_load_config_with_valid_values(self, tmp_path):
        """Test loading config with valid values."""
        config_file = tmp_path / "config.yml"
        config_file.write_text("""
resolution: 1920x1080
format: mkv
fps: 60
preset: fast
crf: 18
accel: nvenc
mode: waveform
""")
        with patch("audio_visualizer.config.get_config_path") as mock_path:
            mock_path.return_value = str(config_file)
            config = load_config()
            assert config["resolution"] == "1920x1080"
            assert config["format"] == "mkv"
            assert config["fps"] == 60
            assert config["preset"] == "fast"
            assert config["crf"] == 18
            assert config["accel"] == "nvenc"
            assert config["mode"] == "waveform"

    def test_load_config_with_invalid_values(self, tmp_path, capsys):
        """Test loading config with invalid values shows warnings."""
        config_file = tmp_path / "config.yml"
        config_file.write_text("""
resolution: invalid
format: mkv
fps: 300
crf: 60
""")
        with patch("audio_visualizer.config.get_config_path") as mock_path:
            mock_path.return_value = str(config_file)
            config = load_config()
            # Invalid values should fall back to defaults
            assert config["resolution"] == DEFAULT_CONFIG["resolution"]
            assert config["crf"] == DEFAULT_CONFIG["crf"]
            # FPS should be clamped to default since 300 is invalid
            # Actually, let's check if it's validated
            # fps=300 is invalid (>240), so it should use default
            assert config["fps"] == DEFAULT_CONFIG["fps"]

    def test_load_config_with_comments(self, tmp_path):
        """Test loading config with comments."""
        config_file = tmp_path / "config.yml"
        config_file.write_text("""
# This is a comment
resolution: 1920x1080
# Another comment
format: mp4
""")
        with patch("audio_visualizer.config.get_config_path") as mock_path:
            mock_path.return_value = str(config_file)
            config = load_config()
            assert config["resolution"] == "1920x1080"
            assert config["format"] == "mp4"


class TestSaveConfig:
    """Test configuration saving."""

    def test_save_config(self, tmp_path):
        """Test saving configuration to file."""
        config_path = str(tmp_path / "config.yml")
        with patch("audio_visualizer.config.get_config_path") as mock_path:
            mock_path.return_value = config_path
            save_config({"resolution": "1920x1080", "format": "mkv"})
            assert os.path.exists(config_path)
            content = Path(config_path).read_text()
            assert "resolution: 1920x1080" in content
            assert "format: mkv" in content

    def test_save_config_preserves_comments(self, tmp_path):
        """Test that save_config preserves comments."""
        config_path = str(tmp_path / "config.yml")
        with patch("audio_visualizer.config.get_config_path") as mock_path:
            mock_path.return_value = config_path
            save_config()
            content = Path(config_path).read_text()
            assert "# Audio Visualizer Configuration" in content


class TestMergeConfig:
    """Test configuration merging."""

    def test_merge_config_uses_defaults(self):
        """Test that merge_config uses config values when args are at defaults."""
        from argparse import Namespace

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
            "fps": 60,
            "preset": "fast",
            "crf": 18,
            "accel": "nvenc",
            "mode": "waveform",
        }

        merged = merge_config(args, config)
        assert merged.resolution == "1920x1080"
        assert merged.format == "mkv"
        assert merged.fps == 60

    def test_merge_config_respects_cli_args(self):
        """Test that CLI args override config values."""
        from argparse import Namespace

        args = Namespace(
            resolution="3840x2160",  # Explicitly set
            format="mp4",
            fps=30,
            preset="medium",
            crf=23,
            accel="auto",
            mode="spectrum",
            output=None,
        )

        config = {
            "resolution": "1920x1080",
            "format": "mkv",
            "fps": 60,
        }

        merged = merge_config(args, config)
        # CLI resolution should be kept
        assert merged.resolution == "3840x2160"
        # Other values should come from config
        assert merged.format == "mkv"
        assert merged.fps == 60

    def test_merge_config_output_dir(self):
        """Test output_dir from config is used."""
        from argparse import Namespace

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
            "output_dir": "/custom/output",
        }

        merged = merge_config(args, config)
        assert merged.output == "/custom/output"

    def test_merge_config_mode_from_config(self):
        """Test mode from config is used when args are at default."""
        from argparse import Namespace

        args = Namespace(
            resolution="1280x720",
            format="mp4",
            fps=30,
            preset="medium",
            crf=23,
            accel="auto",
            mode=["spectrum"],
            output=None,
            colors=None,
            theme=None,
        )

        config = {
            "mode": "waveform",
        }

        merged = merge_config(args, config)
        # Config values stay as written (string); the CLI layer
        # (resolve_mode_classes) normalizes them to a list
        assert merged.mode == "waveform"

    def test_merge_config_mode_cli_overrides(self):
        """Test CLI mode overrides config mode."""
        from argparse import Namespace

        args = Namespace(
            resolution="1280x720",
            format="mp4",
            fps=30,
            preset="medium",
            crf=23,
            accel="auto",
            mode=["radial"],  # Explicitly set on CLI
            output=None,
            colors=None,
            theme=None,
        )

        config = {
            "mode": "waveform",
        }

        merged = merge_config(args, config)
        assert merged.mode == ["radial"]

    def test_merge_config_theme_resolves_to_colors(self):
        """Test theme from config resolves to colors."""
        from argparse import Namespace

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
            "theme": "neon",
        }

        merged = merge_config(args, config)
        assert merged.colors == "lime,magenta,cyan,yellow"

    def test_merge_config_theme_cli_overrides(self):
        """Test CLI colors override config theme."""
        from argparse import Namespace

        args = Namespace(
            resolution="1280x720",
            format="mp4",
            fps=30,
            preset="medium",
            crf=23,
            accel="auto",
            mode="spectrum",
            output=None,
            colors="red,blue",  # Explicitly set on CLI
            theme=None,
        )

        config = {
            "theme": "neon",
        }

        merged = merge_config(args, config)
        assert merged.colors == "red,blue"

    def test_merge_config_invalid_theme(self):
        """Test invalid theme in config doesn't crash."""
        from argparse import Namespace

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
            "theme": "nonexistent",
        }

        merged = merge_config(args, config)
        assert merged.colors is None

    def test_merge_config_cli_theme_resolves(self):
        """Test CLI theme resolves to colors."""
        from argparse import Namespace

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
            theme="sunset",
        )

        config = {}

        merged = merge_config(args, config)
        assert merged.colors == "red,orange,yellow,white"

    def test_merge_config_cli_theme_overrides_config(self):
        """Test CLI theme overrides config theme."""
        from argparse import Namespace

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
            theme="ocean",  # CLI theme
        )

        config = {
            "theme": "neon",  # Config theme
        }

        merged = merge_config(args, config)
        # CLI theme should take precedence
        assert merged.colors == "blue,cyan,teal,white"

    def test_merge_config_cli_colors_overrides_theme(self):
        """Test CLI colors overrides both CLI and config theme."""
        from argparse import Namespace

        args = Namespace(
            resolution="1280x720",
            format="mp4",
            fps=30,
            preset="medium",
            crf=23,
            accel="auto",
            mode="spectrum",
            output=None,
            colors="red,blue",  # Explicit colors
            theme="neon",
        )

        config = {
            "theme": "sunset",
        }

        merged = merge_config(args, config)
        # Explicit colors should not be overridden
        assert merged.colors == "red,blue"

    def test_load_config_float_parsing(self, tmp_path):
        """Test loading config with float values."""
        config_file = tmp_path / "config.yml"
        config_file.write_text("fps: 30\n")
        with patch("audio_visualizer.config.get_config_path") as mock_path:
            mock_path.return_value = str(config_file)
            config = load_config()
            assert config["fps"] == 30

    def test_load_config_invalid_mode(self, tmp_path, capsys):
        """Test loading config with empty mode shows warning."""
        config_file = tmp_path / "config.yml"
        config_file.write_text("mode: \n")
        with patch("audio_visualizer.config.get_config_path") as mock_path:
            mock_path.return_value = str(config_file)
            config = load_config()
            # Empty mode fails the len(v) > 0 validator
            assert config["mode"] == DEFAULT_CONFIG["mode"]


class TestLoadEnvVars:
    """Test environment variable loading."""

    def test_load_env_vars_empty(self, monkeypatch):
        """Test loading env vars when none are set."""
        # Clear all AUDIO_VISUALIZER_ vars
        keys_to_remove = [k for k in os.environ if k.startswith("AUDIO_VISUALIZER_")]
        for k in keys_to_remove:
            monkeypatch.delenv(k)
        env_config = load_env_vars()
        assert env_config == {}

    def test_load_env_vars_resolution(self, monkeypatch):
        """Test loading resolution from env var."""
        monkeypatch.setenv("AUDIO_VISUALIZER_RESOLUTION", "1920x1080")
        env_config = load_env_vars()
        assert env_config["resolution"] == "1920x1080"

    def test_load_env_vars_fps_int(self, monkeypatch):
        """Test loading fps as integer from env var."""
        monkeypatch.setenv("AUDIO_VISUALIZER_FPS", "60")
        env_config = load_env_vars()
        assert env_config["fps"] == 60
        assert isinstance(env_config["fps"], int)

    def test_load_env_vars_crf_int(self, monkeypatch):
        """Test loading crf as integer from env var."""
        monkeypatch.setenv("AUDIO_VISUALIZER_CRF", "18")
        env_config = load_env_vars()
        assert env_config["crf"] == 18

    def test_load_env_vars_accel(self, monkeypatch):
        """Test loading accel from env var."""
        monkeypatch.setenv("AUDIO_VISUALIZER_ACCEL", "nvenc")
        env_config = load_env_vars()
        assert env_config["accel"] == "nvenc"

    def test_load_env_vars_mode(self, monkeypatch):
        """Test loading mode from env var."""
        monkeypatch.setenv("AUDIO_VISUALIZER_MODE", "waveform")
        env_config = load_env_vars()
        assert env_config["mode"] == "waveform"

    def test_load_env_vars_colors(self, monkeypatch):
        """Test loading colors from env var."""
        monkeypatch.setenv("AUDIO_VISUALIZER_COLORS", "red,blue,green")
        env_config = load_env_vars()
        assert env_config["colors"] == "red,blue,green"

    def test_load_env_vars_theme(self, monkeypatch):
        """Test loading theme from env var."""
        monkeypatch.setenv("AUDIO_VISUALIZER_THEME", "neon")
        env_config = load_env_vars()
        assert env_config["theme"] == "neon"

    def test_load_env_vars_multiple(self, monkeypatch):
        """Test loading multiple env vars at once."""
        monkeypatch.setenv("AUDIO_VISUALIZER_RESOLUTION", "3840x2160")
        monkeypatch.setenv("AUDIO_VISUALIZER_FPS", "24")
        monkeypatch.setenv("AUDIO_VISUALIZER_PRESET", "slow")
        monkeypatch.setenv("AUDIO_VISUALIZER_CRF", "20")
        env_config = load_env_vars()
        assert env_config["resolution"] == "3840x2160"
        assert env_config["fps"] == 24
        assert env_config["preset"] == "slow"
        assert env_config["crf"] == 20

    def test_load_env_vars_invalid_resolution(self, monkeypatch, capsys):
        """Test that invalid resolution is rejected."""
        monkeypatch.setenv("AUDIO_VISUALIZER_RESOLUTION", "invalid")
        env_config = load_env_vars()
        assert "resolution" not in env_config

    def test_load_env_vars_invalid_fps(self, monkeypatch, capsys):
        """Test that invalid fps is rejected."""
        monkeypatch.setenv("AUDIO_VISUALIZER_FPS", "999")
        env_config = load_env_vars()
        assert "fps" not in env_config

    def test_load_env_vars_invalid_theme(self, monkeypatch, capsys):
        """Test that invalid theme is rejected."""
        monkeypatch.setenv("AUDIO_VISUALIZER_THEME", "nonexistent")
        env_config = load_env_vars()
        assert "theme" not in env_config

    def test_load_env_vars_invalid_accel(self, monkeypatch, capsys):
        """Test that invalid accel is rejected."""
        monkeypatch.setenv("AUDIO_VISUALIZER_ACCEL", "cuda")
        env_config = load_env_vars()
        assert "accel" not in env_config

    def test_load_env_vars_format(self, monkeypatch):
        """Test loading format from env var."""
        monkeypatch.setenv("AUDIO_VISUALIZER_FORMAT", "mkv")
        env_config = load_env_vars()
        assert env_config["format"] == "mkv"

    def test_load_env_vars_output_dir(self, monkeypatch):
        """Test loading output_dir from env var."""
        monkeypatch.setenv("AUDIO_VISUALIZER_OUTPUT_DIR", "/custom/output")
        env_config = load_env_vars()
        assert env_config["output_dir"] == "/custom/output"


class TestMergeConfigEnvVars:
    """Test environment variable merging in merge_config."""

    def test_env_vars_applied_when_no_cli(self):
        """Test env vars are applied when CLI args are at defaults."""
        from argparse import Namespace

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
            "fps": 60,
            "format": "mkv",
        }

        env_vars = {
            "resolution": "2560x1440",
            "fps": 120,
            "preset": "fast",
        }

        merged = merge_config(args, config, env_vars)
        # Env vars should override config
        assert merged.resolution == "2560x1440"
        assert merged.fps == 120
        assert merged.preset == "fast"
        # Config values not in env vars
        assert merged.format == "mkv"

    def test_cli_overrides_env_vars(self):
        """Test CLI args override env vars."""
        from argparse import Namespace

        args = Namespace(
            resolution="3840x2160",  # CLI explicitly set
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
        }

        env_vars = {
            "resolution": "2560x1440",  # Env var
        }

        merged = merge_config(args, config, env_vars)
        # CLI should win
        assert merged.resolution == "3840x2160"

    def test_env_overrides_config(self):
        """Test env vars override config file values."""
        from argparse import Namespace

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
            "fps": 60,
            "preset": "slow",
        }

        env_vars = {
            "fps": 120,  # Env overrides config
        }

        merged = merge_config(args, config, env_vars)
        assert merged.resolution == "1920x1080"  # From config
        assert merged.fps == 120  # From env
        assert merged.preset == "slow"  # From config

    def test_env_theme_resolves_to_colors(self):
        """Test env var theme resolves to colors."""
        from argparse import Namespace

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

        config = {}
        env_vars = {"theme": "ocean"}

        merged = merge_config(args, config, env_vars)
        assert merged.colors == "blue,cyan,teal,white"

    def test_cli_theme_overrides_env_theme(self):
        """Test CLI theme overrides env theme."""
        from argparse import Namespace

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
            theme="sunset",
        )

        config = {}
        env_vars = {"theme": "neon"}

        merged = merge_config(args, config, env_vars)
        assert merged.colors == "red,orange,yellow,white"

    def test_cli_colors_overrides_env_theme(self):
        """Test CLI colors overrides env theme."""
        from argparse import Namespace

        args = Namespace(
            resolution="1280x720",
            format="mp4",
            fps=30,
            preset="medium",
            crf=23,
            accel="auto",
            mode="spectrum",
            output=None,
            colors="red,blue",
            theme=None,
        )

        config = {}
        env_vars = {"theme": "neon"}

        merged = merge_config(args, config, env_vars)
        assert merged.colors == "red,blue"

    def test_env_output_dir(self):
        """Test env var output_dir is applied."""
        from argparse import Namespace

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
            "output_dir": "/config/output",
        }

        env_vars = {
            "output_dir": "/env/output",
        }

        merged = merge_config(args, config, env_vars)
        assert merged.output == "/env/output"

    def test_env_overrides_config_output_dir(self):
        """Test env output_dir overrides config output_dir."""
        from argparse import Namespace

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
            "output_dir": "/config/output",
        }

        env_vars = {
            "output_dir": "/env/output",
        }

        merged = merge_config(args, config, env_vars)
        assert merged.output == "/env/output"

    def test_no_env_vars_falls_back_to_config(self):
        """Test that without env vars, config values are used."""
        from argparse import Namespace

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
            "fps": 60,
        }

        # Pass empty env vars
        merged = merge_config(args, config, {})
        assert merged.resolution == "1920x1080"
        assert merged.fps == 60

    def test_merge_config_auto_loads_env_vars(self):
        """Test that merge_config loads env vars when env_vars=None."""
        import os
        from argparse import Namespace

        os.environ["AUDIO_VISUALIZER_RESOLUTION"] = "1920x1080"
        os.environ["AUDIO_VISUALIZER_FPS"] = "60"

        try:
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
                "resolution": "2560x1440",
                "fps": 120,
            }

            merged = merge_config(args, config)  # env_vars=None
            # Env vars should be loaded automatically
            assert merged.resolution == "1920x1080"
            assert merged.fps == 60
        finally:
            del os.environ["AUDIO_VISUALIZER_RESOLUTION"]
            del os.environ["AUDIO_VISUALIZER_FPS"]


class TestPluginConfigSections:
    """Test schema-aware per-plugin config sections (release goal section 10)."""

    @pytest.fixture
    def registry(self):
        from audio_visualizer.visualizers.registry import PluginRegistry

        reg = PluginRegistry()
        reg.load_all()
        return reg

    def _write(self, tmp_path, text):
        cfg = tmp_path / "config.yml"
        cfg.write_text(text)
        return str(cfg)

    def test_load_plugin_sections_valid(self, tmp_path, registry):
        """Plugin sections are parsed and validated against schemas."""
        path = self._write(
            tmp_path,
            """
resolution: 1920x1080
spectrum:
  mode: rainbow
  opacity: 0.8
waveform:
  mode: line
  splits: 2
""",
        )
        with patch("audio_visualizer.config.get_config_path") as mock_path:
            mock_path.return_value = path
            config = load_config(registry)
        assert config["resolution"] == "1920x1080"
        assert config["plugins"]["spectrum"] == {
            "spectrum-mode": "rainbow",
            "spectrum-opacity": 0.8,
        }
        assert config["plugins"]["waveform"] == {"waveform-mode": "line", "waveform-splits": 2}

    def test_load_plugin_section_types_coerced(self, tmp_path, registry):
        """Values are coerced to schema types (int/float/bool)."""
        path = self._write(
            tmp_path,
            """
spectrogram:
  speed: 0.95
  transpose: true
waveform:
  splits: 3
""",
        )
        with patch("audio_visualizer.config.get_config_path") as mock_path:
            mock_path.return_value = path
            config = load_config(registry)
        assert config["plugins"]["spectrogram"]["spectrogram-speed"] == 0.95
        assert config["plugins"]["spectrogram"]["spectrogram-transpose"] is True
        assert config["plugins"]["waveform"]["waveform-splits"] == 3

    def test_load_plugin_section_bool_false_string(self, tmp_path, registry):
        """Boolean 'false' strings coerce to False, not True."""
        path = self._write(tmp_path, "spectrogram:\n  transpose: false\n")
        with patch("audio_visualizer.config.get_config_path") as mock_path:
            mock_path.return_value = path
            config = load_config(registry)
        assert config["plugins"]["spectrogram"]["spectrogram-transpose"] is False

    def test_load_plugin_section_invalid_type_skipped(self, tmp_path, registry):
        """Values failing schema validation are skipped with a warning."""
        path = self._write(tmp_path, "waveform:\n  splits: notanint\n")
        with patch("audio_visualizer.config.get_config_path") as mock_path:
            mock_path.return_value = path
            config = load_config(registry)
        assert config["plugins"].get("waveform", {}) == {}

    def test_load_plugin_section_invalid_choice_skipped(self, tmp_path, registry):
        """Values outside the choices list are skipped with a warning."""
        path = self._write(tmp_path, "spectrum:\n  mode: notamode\n")
        with patch("audio_visualizer.config.get_config_path") as mock_path:
            mock_path.return_value = path
            config = load_config(registry)
        assert config["plugins"].get("spectrum", {}) == {}

    def test_load_plugin_section_unknown_option_skipped(self, tmp_path, registry, caplog):
        """Unknown options inside a plugin section are skipped with a warning."""
        path = self._write(tmp_path, "spectrum:\n  bogus: 12\n  opacity: 0.5\n")
        with patch("audio_visualizer.config.get_config_path") as mock_path:
            mock_path.return_value = path
            config = load_config(registry)
        assert config["plugins"]["spectrum"] == {"spectrum-opacity": 0.5}
        assert any("unknown option 'bogus'" in r.message for r in caplog.records)

    def test_load_plugin_section_unknown_plugin_skipped(self, tmp_path, registry):
        """Unknown plugin sections are skipped with a warning."""
        path = self._write(tmp_path, "notaplugin:\n  mode: x\n")
        with patch("audio_visualizer.config.get_config_path") as mock_path:
            mock_path.return_value = path
            config = load_config(registry)
        assert config["plugins"] == {}

    def test_load_plugin_section_full_option_names(self, tmp_path, registry):
        """Full option names (with plugin prefix) are accepted in sections."""
        path = self._write(tmp_path, "spectrum:\n  spectrum-mode: rainbow\n")
        with patch("audio_visualizer.config.get_config_path") as mock_path:
            mock_path.return_value = path
            config = load_config(registry)
        assert config["plugins"]["spectrum"] == {"spectrum-mode": "rainbow"}

    def test_empty_global_value_not_treated_as_section(self, tmp_path, registry):
        """A global key with an empty value is not a section header."""
        path = self._write(tmp_path, "colors: \nfps: 60\n")
        with patch("audio_visualizer.config.get_config_path") as mock_path:
            mock_path.return_value = path
            config = load_config(registry)
        assert config["fps"] == 60
        assert config["plugins"] == {}

    def test_multiple_sections_and_globals_interleaved(self, tmp_path, registry):
        """Sections and global keys can be interleaved."""
        path = self._write(
            tmp_path,
            """
fps: 60
spectrum:
  opacity: 0.5
format: mkv
waveform:
  mode: line
""",
        )
        with patch("audio_visualizer.config.get_config_path") as mock_path:
            mock_path.return_value = path
            config = load_config(registry)
        assert config["fps"] == 60
        assert config["format"] == "mkv"
        assert config["plugins"]["spectrum"] == {"spectrum-opacity": 0.5}
        assert config["plugins"]["waveform"] == {"waveform-mode": "line"}

    def test_save_config_namespace_writes_plugin_sections(self, tmp_path, registry):
        """--save-config writes non-default plugin option values as sections."""
        from argparse import Namespace

        ns = Namespace(
            resolution="1920x1080",
            format="mkv",
            fps=60,
            preset="medium",
            crf=23,
            accel="auto",
            mode="spectrum",
            output=None,
            colors=None,
            theme=None,
            spectrum_mode="rainbow",  # default -> not written
            spectrum_opacity=0.8,  # non-default -> written
            waveform_mode="line",  # default -> not written
            waveform_splits=2,  # non-default -> written
        )
        path = str(tmp_path / "config.yml")
        with patch("audio_visualizer.config.get_config_path") as mock_path:
            mock_path.return_value = path
            save_config(ns, registry)
        content = Path(path).read_text()
        assert "\nspectrum:\n" in content
        assert "  opacity: 0.8" in content
        assert "  mode: rainbow" not in content
        assert "\nwaveform:\n" in content
        assert "  splits: 2" in content

    def test_save_config_dict_with_plugins(self, tmp_path):
        """Dictionaries with a 'plugins' key round-trip through save/load."""
        path = str(tmp_path / "config.yml")
        with patch("audio_visualizer.config.get_config_path") as mock_path:
            mock_path.return_value = path
            save_config({"fps": 60, "plugins": {"spectrum": {"opacity": 0.5}}})
        content = Path(path).read_text()
        assert "fps: 60" in content
        assert "\nspectrum:\n" in content
        assert "  opacity: 0.5" in content

    def test_save_config_roundtrip(self, tmp_path, registry):
        """Saved plugin sections load back with the same values."""
        from argparse import Namespace

        ns = Namespace(
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
            spectrum_opacity=0.7,
            waveform_splits=3,
        )
        path = str(tmp_path / "config.yml")
        with patch("audio_visualizer.config.get_config_path") as mock_path:
            mock_path.return_value = path
            save_config(ns, registry)
            config = load_config(registry)
        assert config["plugins"]["spectrum"] == {"spectrum-opacity": 0.7}
        assert config["plugins"]["waveform"] == {"waveform-splits": 3}

    def test_merge_config_applies_plugin_sections(self, tmp_path, registry):
        """Config plugin values apply when CLI args are at defaults."""
        from argparse import Namespace

        args = Namespace(
            output=None,
            colors=None,
            theme=None,
            spectrum_mode="rainbow",
            spectrum_opacity=1.0,
            waveform_mode="line",
            waveform_splits=1,
        )
        config = {
            "plugins": {
                "spectrum": {"spectrum-opacity": 0.8},
                "waveform": {"waveform-splits": 2},
            }
        }
        merged = merge_config(args, config, registry=registry)
        assert merged.spectrum_opacity == 0.8
        assert merged.waveform_splits == 2

    def test_merge_config_cli_overrides_plugin_sections(self, tmp_path, registry):
        """Explicit CLI values win over config plugin sections."""
        from argparse import Namespace

        args = Namespace(
            output=None,
            colors=None,
            theme=None,
            spectrum_opacity=0.3,
        )
        config = {"plugins": {"spectrum": {"spectrum-opacity": 0.8}}}
        merged = merge_config(args, config, registry=registry)
        assert merged.spectrum_opacity == 0.3

    def test_merge_config_without_registry_skips_sections(self, tmp_path):
        """Without a registry, plugin sections are ignored (no crash)."""
        from argparse import Namespace

        args = Namespace(output=None, colors=None, theme=None, spectrum_opacity=1.0)
        config = {"plugins": {"spectrum": {"spectrum-opacity": 0.8}}}
        merged = merge_config(args, config)
        assert merged.spectrum_opacity == 1.0


class TestUserThemes:
    """User-defined themes (v2.2.0 sec.3.1)."""

    def _write_theme(self, tmp_path, name, palette):
        import json
        from pathlib import Path

        d = Path(tmp_path) / ".config" / "audio-visualizer" / "themes"
        d.mkdir(parents=True, exist_ok=True)
        (d / f"{name}.json").write_text(json.dumps({"palette": palette}))

    def test_load_user_themes_valid(self, tmp_path, monkeypatch):
        from audio_visualizer.config import load_user_themes

        monkeypatch.setenv("HOME", str(tmp_path))
        self._write_theme(tmp_path, "custom", ["red", "blue", "#123456"])
        assert load_user_themes() == {"custom": "red,blue,#123456"}

    def test_load_missing_dir_returns_empty(self, tmp_path, monkeypatch):
        from audio_visualizer.config import load_user_themes

        monkeypatch.setenv("HOME", str(tmp_path))
        assert load_user_themes() == {}

    def test_resolve_theme_user_overrides_builtin(self, tmp_path, monkeypatch):
        from audio_visualizer.config import resolve_theme

        monkeypatch.setenv("HOME", str(tmp_path))
        self._write_theme(tmp_path, "neon", ["red", "orange"])
        assert resolve_theme("neon") == "red,orange"
        assert resolve_theme("ocean") == "blue,cyan,teal,white"
        assert resolve_theme("nope") is None

    def test_load_skips_invalid_files(self, tmp_path, monkeypatch, caplog):
        from audio_visualizer.config import load_user_themes

        monkeypatch.setenv("HOME", str(tmp_path))
        self._write_theme(tmp_path, "good", ["red"])
        self._write_theme(tmp_path, "toolong", list("rgbycwmkpgoblr"))
        self._write_theme(tmp_path, "notalist", "red")
        themes = load_user_themes()
        assert set(themes) == {"good"}
        assert "Ignoring invalid theme file 'toolong.json'" in caplog.text
        assert "Ignoring invalid theme file 'notalist.json'" in caplog.text

    def test_load_skips_broken_json_and_non_json(
        self, tmp_path, monkeypatch, caplog
    ):
        from audio_visualizer.config import load_user_themes

        monkeypatch.setenv("HOME", str(tmp_path))
        self._write_theme(tmp_path, "good", ["red"])
        d = tmp_path / ".config" / "audio-visualizer" / "themes"
        (d / "broken.json").write_text("{not json")
        (d / "notes.txt").write_text("ignore me")
        themes = load_user_themes()
        assert set(themes) == {"good"}
        assert "Ignoring invalid theme file 'broken.json'" in caplog.text

    def test_merge_config_resolves_user_theme(self, tmp_path, monkeypatch):
        from argparse import Namespace

        monkeypatch.setenv("HOME", str(tmp_path))
        self._write_theme(tmp_path, "custom", ["red", "blue"])
        args = Namespace(output=None, colors=None, theme="custom")
        merged = merge_config(args, {})
        assert merged.colors == "red,blue"

    def test_merge_config_unknown_theme_warns(self, tmp_path, monkeypatch, caplog):
        from argparse import Namespace

        monkeypatch.setenv("HOME", str(tmp_path))
        args = Namespace(output=None, colors=None, theme="bogus")
        merged = merge_config(args, {})
        assert merged.colors is None
        assert "Unknown theme 'bogus'" in caplog.text


class TestListThemes:
    """--list-themes output (v2.2.0 sec.3.1/3.2)."""

    def _write_theme(self, tmp_path, name, palette):
        import json
        from pathlib import Path

        d = Path(tmp_path) / ".config" / "audio-visualizer" / "themes"
        d.mkdir(parents=True, exist_ok=True)
        (d / f"{name}.json").write_text(json.dumps({"palette": palette}))

    def test_shows_builtin_and_user_sections(self, tmp_path, monkeypatch, capsys):
        from audio_visualizer.__main__ import list_themes

        monkeypatch.setenv("HOME", str(tmp_path))
        self._write_theme(tmp_path, "custom", ["red", "blue"])
        list_themes()
        out = capsys.readouterr().out
        assert "Built-in color themes" in out
        assert "neon" in out
        assert "User themes" in out
        assert "custom" in out

"""v2.2.0 sec.8.1: --doctor environment report tests."""

import json

from audio_visualizer.doctor import (
    config_report,
    doctor,
    ffmpeg_report,
    hwaccel_report,
    run_doctor,
)
from audio_visualizer.visualizers.registry import PluginRegistry


def _registry():
    registry = PluginRegistry()
    registry.load_all()
    return registry


class TestDoctorReport:
    def test_report_sections(self):
        report = doctor(_registry())
        for key in (
            "core_version",
            "ffmpeg",
            "visualizers",
            "hwaccel",
            "config",
            "plugins",
            "problems",
            "ok",
        ):
            assert key in report
        assert report["ffmpeg"]["version"] is not None
        assert report["config"]["path"]
        assert report["plugins"]["loaded"]

    def test_all_visualizer_rows_present(self):
        report = doctor(_registry())
        names = {row["name"] for row in report["visualizers"]}
        assert {"spectrum", "beatpulse", "lissajous"} <= names

    def test_ok_exit_zero(self, capsys):
        rc = run_doctor(_registry(), as_json=False)
        assert rc == 0
        out = capsys.readouterr().out
        assert "ffmpeg" in out and "Plugins:" in out

    def test_json_exit_zero(self, capsys):
        rc = run_doctor(_registry(), as_json=True)
        assert rc == 0
        payload = json.loads(capsys.readouterr().out)
        assert payload["ok"] is True
        assert payload["problems"] == []


class TestDoctorFailurePaths:
    def test_missing_ffmpeg_flagged(self, monkeypatch):
        import audio_visualizer.doctor as mod

        monkeypatch.setattr(mod, "_run", lambda cmd, timeout=10: None)
        report = ffmpeg_report()
        assert report["ok"] is False
        assert "not found" in report["problem"]

    def test_failed_plugin_reported(self, tmp_path, monkeypatch):
        # A syntactically broken plugin file in the discovery path
        bad = tmp_path / "badplug.py"
        bad.write_text("def broken(:\\n    pass\\n")
        registry = PluginRegistry(plugin_paths=[str(tmp_path)])
        registry.load_all()
        report = doctor(registry)
        assert any("badplug" in p for p in report["problems"])
        assert report["ok"] is False
        assert report["plugins"]["failed"]

    def test_run_doctor_nonzero_on_problems(self, tmp_path, capsys, monkeypatch):
        bad = tmp_path / "badplug.py"
        bad.write_text("def broken(:\\n    pass\\n")
        registry = PluginRegistry(plugin_paths=[str(tmp_path)])
        registry.load_all()
        rc = run_doctor(registry, as_json=False)
        assert rc == 1
        assert "PROBLEMS" in capsys.readouterr().out


class TestDoctorHelpers:
    def test_config_report_shapes(self):
        report = config_report()
        assert "path" in report and "valid" in report
        assert isinstance(report["problems"], list)

    def test_hwaccel_report(self):
        report = hwaccel_report()
        assert "available" in report and "checked" in report

    def test_graph_filter_names_neutralizes_quotes(self):
        from audio_visualizer.doctor import _graph_filter_names

        names = _graph_filter_names("nullsrc=s=8x8:r=30,format=gray,geq=lum='clip(1-a/2,0,1)' [x]")
        assert names == {"nullsrc", "format", "geq"}

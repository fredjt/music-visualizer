"""
`audio-visualizer --doctor` environment report (v2.2.0 sec.8.1).

One command reports: the ffmpeg version (against the project minimum),
the presence of every filter each loaded visualizer's default graph
needs, the hardware accelerators ffmpeg exposes, the config file path
and validity, and the plugin load report (including failures with
reasons). `--doctor --json` emits the same report as JSON; the process
exits non-zero when anything is wrong.
"""

from __future__ import annotations

import json
import os
import re
import subprocess
from typing import Any

_MIN_FFMPEG = (6, 0)
_FILTER_LINE = re.compile(r"^[\sA-Z.]*\s+(\S+)\s")


def _run(cmd: list[str], timeout: int = 10) -> str | None:
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        if result.returncode == 0:
            return result.stdout
    except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
        pass
    return None


def _parse_version(line: str) -> tuple[int, ...] | None:
    for chunk in line.split():
        parts = [p for p in chunk.split(".") if p.isdigit()]
        if parts:
            try:
                return tuple(int(p) for p in parts[:3])
            except ValueError:
                continue
    return None


def ffmpeg_report() -> dict[str, Any]:
    out: dict[str, Any] = {
        "version": None,
        "version_line": None,
        "minimum": ".".join(map(str, _MIN_FFMPEG)),
        "ok": False,
        "problem": None,
    }
    stdout = _run(["ffmpeg", "-version"])
    if stdout is None:
        out["problem"] = "ffmpeg not found on PATH"
        return out
    out["version_line"] = stdout.split("\n")[0]
    ver = _parse_version(out["version_line"])
    out["version"] = ".".join(map(str, ver)) if ver else None
    if ver is None:
        out["problem"] = f"unparseable ffmpeg version: {out['version_line']!r}"
    elif ver < _MIN_FFMPEG:
        out["problem"] = (
            f"ffmpeg {out['version']} is below the project "
            f"minimum {_MIN_FFMPEG[0]}.{_MIN_FFMPEG[1]}"
        )
    else:
        out["ok"] = True
    return out


def _available_filters() -> set[str] | None:
    stdout = _run(["ffmpeg", "-hide_banner", "-filters"])
    if stdout is None:
        return None
    names = set()
    for line in stdout.split("\n"):
        m = _FILTER_LINE.match(line)
        if m:
            names.add(m.group(1))
    return names


def _graph_filter_names(graph: str) -> set[str]:
    """Extract the filter names used by a filter graph string.

    Quoted option values are neutralized first (a geq expression may
    contain commas and brackets of its own).
    """
    graph = re.sub(r"'[^']*'", "Q", graph)
    graph = re.sub(r'"[^"]*"', "Q", graph)
    names: set[str] = set()
    for chain in graph.split(";"):
        c = re.sub(r"^\s*(?:\[[^\]\[\]]+\]\s*)+", "", chain.strip())
        for seg in c.split(","):
            seg = re.sub(r"(?:\[[^\]\[\]]+\]\s*)+$", "", seg.strip())
            seg = seg.strip()
            if not seg or seg.startswith("["):
                continue
            name = seg.split("=")[0].strip()
            if name:
                names.add(name)
    return names


def visualizer_filters_report(registry, available: set[str] | None) -> list[dict[str, Any]]:
    """Per-visualizer filter requirements vs. the detected ffmpeg build."""
    rows = []
    for name, cls in sorted(registry.get_all().items()):
        row: dict[str, Any] = {"name": name}
        try:
            opts = cls.validate_options({})
            graph = cls().build_filter(640, 360, 30, opts, audio_index=0)
        except Exception as e:
            row["ok"] = False
            row["problem"] = f"default graph does not build: {e}"
            rows.append(row)
            continue
        needed = _graph_filter_names(graph)
        row["filters"] = sorted(needed)
        if available is None:
            row["ok"] = True  # unknown; ffmpeg presence already flagged
        else:
            missing = sorted(needed - available)
            row["missing"] = missing
            row["ok"] = not missing
            if missing:
                row["problem"] = f"missing ffmpeg filter(s): {', '.join(missing)}"
        rows.append(row)
    return rows


_HWACCEL_ENCODERS = {
    "nvenc": "h264_nvenc",
    "qsv": "h264_qsv",
    "vaapi": "h264_vaapi",
    "videotoolbox": "h264_videotoolbox",
}


def hwaccel_report() -> dict[str, Any]:
    stdout = _run(["ffmpeg", "-hide_banner", "-encoders"])
    found = {k: (v in (stdout or "")) for k, v in _HWACCEL_ENCODERS.items()}
    return {
        "available": {k: v for k, v in found.items() if v},
        "checked": sorted(_HWACCEL_ENCODERS),
    }


def config_report() -> dict[str, Any]:
    from audio_visualizer.config import (
        _parse_config_file,
        get_config_path,
        validate_config_only,
    )

    path = get_config_path()
    out: dict[str, Any] = {
        "path": path,
        "exists": os.path.exists(path),
        "valid": None,
        "problems": [],
    }
    if not out["exists"]:
        out["valid"] = True  # no config file is a fine state
        return out
    try:
        raw_globals, raw_plugins = _parse_config_file(path)
        config: dict = dict(raw_globals)
        config["plugins"] = raw_plugins
        out["problems"] = validate_config_only(config)
    except Exception as e:
        out["problems"] = [f"config file could not be parsed: {e}"]
    out["valid"] = not out["problems"]
    return out


def plugin_report(registry) -> dict[str, Any]:
    plugins, errors = registry.get_all_with_errors()
    return {
        "loaded": [
            {
                "name": name,
                "origin": registry.get_origin(name),
                "version": cls.get_metadata().version,
            }
            for name, cls in sorted(plugins.items())
        ],
        "failed": sorted(errors, key=lambda e: e.get("name", "")),
    }


def doctor(registry) -> dict[str, Any]:
    """Assemble the full doctor report."""
    from audio_visualizer.__main__ import get_package_version

    ffmpeg = ffmpeg_report()
    filters = _available_filters()
    viz_rows = visualizer_filters_report(registry, filters)
    report = {
        "core_version": get_package_version(),
        "ffmpeg": ffmpeg,
        "visualizers": viz_rows,
        "hwaccel": hwaccel_report(),
        "config": config_report(),
        "plugins": plugin_report(registry),
    }
    problems: list[str] = []
    if ffmpeg.get("problem"):
        problems.append(f"ffmpeg: {ffmpeg['problem']}")
    for row in viz_rows:
        if not row.get("ok", True) and row.get("problem"):
            problems.append(f"visualizer '{row['name']}': {row['problem']}")
    for pr in report["config"].get("problems", []):
        problems.append(f"config: {pr}")
    for err in report["plugins"]["failed"]:
        problems.append(f"plugin load failed: {err.get('name')}: {err.get('error')}")
    report["problems"] = problems
    report["ok"] = not problems
    return report


def run_doctor(registry, as_json: bool) -> int:
    """Print the report (JSON or human-readable) and return the exit code."""
    report = doctor(registry)
    if as_json:
        print(json.dumps(report, indent=2))
    else:
        ff = report["ffmpeg"]
        print(f"audio-visualizer {report['core_version']} --doctor")
        print()
        state = "OK " if ff["ok"] else "FAIL"
        print(
            f"[{state}] ffmpeg: {ff['version'] or ff['problem']} (project minimum {ff['minimum']})"
        )
        print()
        print("Visualizer filter requirements:")
        for row in report["visualizers"]:
            mark = "OK  " if row.get("ok", True) else "FAIL"
            extra = f"  ({row['problem']})" if row.get("problem") else ""
            print(f"  [{mark}] {row['name']}{extra}")
        print()
        found = report["hwaccel"]["available"]
        print(f"Hardware encoders: {', '.join(sorted(found)) or 'none (software)'}")
        print()
        cfg = report["config"]
        cstate = "present, valid" if cfg["exists"] else "not present (defaults used)"
        if cfg["exists"] and not cfg["valid"]:
            cstate = "present, INVALID"
        print(f"Config: {cfg['path']} ({cstate})")
        for pr in cfg.get("problems", []):
            print(f"    - {pr}")
        print()
        pl = report["plugins"]
        print(f"Plugins: {len(pl['loaded'])} loaded, {len(pl['failed'])} failed")
        for err in pl["failed"]:
            print(f"    - {err.get('name')}: {err.get('error')}")
        print()
        if report["problems"]:
            print(f"PROBLEMS ({len(report['problems'])}):")
            for p in report["problems"]:
                print(f"  - {p}")
        else:
            print("All checks passed.")
    return 0 if report["ok"] else 1

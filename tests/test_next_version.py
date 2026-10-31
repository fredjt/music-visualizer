"""Tests for scripts/next_version.py (v2.2.0 sec.5.3)."""

import importlib.util
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parent.parent / "scripts" / "next_version.py"


def _load():
    spec = importlib.util.spec_from_file_location("next_version", SCRIPT)
    loader = spec.loader if spec is not None else None
    assert spec is not None and loader is not None
    mod = importlib.util.module_from_spec(spec)
    loader.exec_module(mod)
    return mod


@pytest.fixture()
def nv(tmp_path, monkeypatch):
    mod = _load()
    pyproject = tmp_path / "pyproject.toml"
    pyproject.write_text(
        '[project]\nname = "musicvisualizer"\nversion = "2.1.0"\ndescription = "x"\n'
    )
    monkeypatch.setattr(mod, "PYPROJECT", pyproject)
    monkeypatch.setattr(mod.sys, "argv", ["next_version.py", "patch"])
    return mod, pyproject


def test_patch_bump(nv):
    mod, pyproject = nv
    mod.sys.argv[1] = "patch"
    mod.main()
    assert 'version = "2.1.1"' in pyproject.read_text()


def test_minor_bump_resets_patch(nv):
    mod, pyproject = nv
    pyproject.write_text(
        '[project]\nname = "musicvisualizer"\nversion = "2.1.9"\ndescription = "x"\n'
    )
    mod.sys.argv[1] = "minor"
    mod.main()
    assert 'version = "2.2.0"' in pyproject.read_text()


def test_major_bump_resets_minor_and_patch(nv):
    mod, pyproject = nv
    mod.sys.argv[1] = "major"
    mod.main()
    assert 'version = "3.0.0"' in pyproject.read_text()


def test_only_version_line_changes(nv):
    mod, pyproject = nv
    mod.sys.argv[1] = "patch"
    mod.main()
    text = pyproject.read_text()
    assert 'name = "musicvisualizer"' in text
    assert 'description = "x"' in text
    assert text.count("2.1.") == 1


def test_invalid_kind_exits(nv):
    mod, _ = nv
    mod.sys.argv[1] = "banana"
    with pytest.raises(SystemExit):
        mod.main()


def test_missing_version_line_exits(nv):
    mod, pyproject = nv
    pyproject.write_text('[project]\nname = "x"\n')
    mod.sys.argv[1] = "patch"
    with pytest.raises(SystemExit):
        mod.main()

"""Plugin package scaffolding for `new-plugin` (v2.2.0 sec.6.1)."""

import re
from pathlib import Path

from audio_visualizer._scaffold_templates import (
    INIT_TMPL,
    PLUGIN_TMPL,
    PYPROJECT_TMPL,
    TEST_TMPL,
)


def scaffold_plugin(name: str, target_dir: str) -> list[str]:
    """Write a ready-to-edit plugin package under *target_dir*.

    Layout: pyproject.toml (entry-point package), <pkg>/__init__.py,
    <pkg>/plugin.py (the canonical minimal example) and
    tests/test_plugin.py (label discipline via audio_visualizer.testing).
    Returns the written files; invalid names or non-empty targets raise
    ValueError.
    """
    if not re.fullmatch(r"[a-z][a-z0-9-]*", name):
        raise ValueError(
            f"Invalid plugin name '{name}': use lowercase letters, digits "
            "and hyphens, starting with a letter (e.g. 'my-viz')"
        )
    pkg = name.replace("-", "_")
    parts = [p for p in name.split("-") if p]
    cls = "".join(p[:1].upper() + p[1:] for p in parts)
    display = " ".join(p.capitalize() for p in parts)
    root = Path(target_dir).expanduser().resolve()
    if root.exists() and any(root.iterdir()):
        raise ValueError(f"Target directory {root} exists and is not empty")
    (root / pkg).mkdir(parents=True)
    (root / "tests").mkdir(parents=True)

    fill = (
        lambda text: text.replace("{{NAME}}", name)
        .replace("{{PKG}}", pkg)
        .replace("{{CLS}}", cls)
        .replace("{{DISPLAY}}", display)
    )
    files: list[str] = []
    for rel, tmpl in (
        ("pyproject.toml", PYPROJECT_TMPL),
        (f"{pkg}/__init__.py", INIT_TMPL),
        (f"{pkg}/plugin.py", PLUGIN_TMPL),
        ("tests/test_plugin.py", TEST_TMPL),
    ):
        p = root / rel
        p.write_text(fill(tmpl), encoding="utf-8")
        files.append(str(p))
    return files

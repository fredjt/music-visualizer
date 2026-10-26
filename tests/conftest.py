"""Pytest configuration."""

import os


def pytest_configure(config):
    """Set base temp directory outside the repo to avoid test artifacts."""
    config.option.basetemp = os.path.join(
        os.environ.get("TMPDIR", "/tmp"), "audio-visualizer-pytest-tmp"
    )

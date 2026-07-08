"""Contracts for the reproducible Python development environment."""

from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent


def test_default_python_version_is_pinned():
    version_file = ROOT / ".python-version"

    assert version_file.is_file()
    assert version_file.read_text(encoding="utf-8").strip() == "3.14.6"


def test_supported_python_floor_is_311():
    pyproject = (ROOT / "pyproject.toml").read_text(encoding="utf-8")

    assert 'requires-python = ">=3.11"' in pyproject


def test_pytest_adds_repository_root_to_import_path():
    pyproject = (ROOT / "pyproject.toml").read_text(encoding="utf-8")

    assert 'pythonpath = ["."]' in pyproject

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


def test_ci_covers_minimum_and_default_python_versions():
    workflow = (ROOT / ".github/workflows/check.yml").read_text(encoding="utf-8")

    assert 'python-version: ["3.11", "3.14"]' in workflow
    assert "python-version: ${{ matrix.python-version }}" in workflow


def test_ci_uses_pinned_uv_and_locked_environment():
    workflow = (ROOT / ".github/workflows/check.yml").read_text(encoding="utf-8")

    assert (
        "astral-sh/setup-uv@08807647e7069bb48b6ef5acd8ec9567f424441b"
        in workflow
    )
    assert "uv sync --locked --extra dev" in workflow
    assert "uv run --no-sync python -m pytest" in workflow


def test_readmes_document_locked_uv_workflow():
    for filename in ("README.md", "README_EN.md"):
        readme = (ROOT / filename).read_text(encoding="utf-8")

        assert "uv sync --locked --extra dev" in readme
        assert "uv run --no-sync python -m pytest" in readme
        assert "python -m pip install --upgrade pip setuptools wheel" in readme


def test_english_contribution_guide_does_not_use_bare_pytest():
    readme_en = (ROOT / "README_EN.md").read_text(encoding="utf-8")

    assert "\npytest\n" not in readme_en

"""Post-install verification: build the wheel, install it into a clean venv that
has NO access to the source repo, and exercise the console scripts.

These tests prove the release artifact (not the source checkout) actually works —
the class of test the project was missing. They must not depend on the dev repo
being importable; the venv runs from a directory outside this tree.
"""
from __future__ import annotations

import subprocess
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def _need(*bins: str) -> None:
    for b in bins:
        if not (ROOT / b).exists() and b not in {"python", "pip"}:
            pass


def _build_wheel(tmp_path: Path) -> Path:
    """Build the wheel via `python -m build` in a venv that has `build` installed.

    The build must run against the real project tree, but the INSTALLED venv
    under test must not be able to see the repo. We use a throwaway build venv
    (e.g. /tmp/bldenv) so the test runner itself needs no `build` import.
    """
    import os

    build_venv = os.environ.get("BUILD_VENV", "/tmp/bldenv")
    build_python = str(Path(build_venv) / "bin" / "python")
    dist = tmp_path / "dist"
    # Run from a neutral dir: a local `build.py` in ROOT would shadow the
    # `build` module when cwd == ROOT.
    subprocess.run(
        [build_python, "-m", "build", "--wheel", "--outdir", str(dist), str(ROOT)],
        cwd=str(tmp_path),
        check=True,
        capture_output=True,
        text=True,
    )
    wheels = sorted(dist.glob("*.whl"))
    assert wheels, "wheel was not produced"
    return wheels[0]


def _required_wheel_files() -> list[str]:
    return [
        "scripts/resources/templates/daily-note.md",
        "scripts/resources/templates/digest-note.md",
        "scripts/resources/templates/web-clip.md",
        "scripts/resources/templates/en/daily-note.md",
        "scripts/resources/references/note-creation.md",
        "scripts/resources/references/rules-and-errors.md",
    ]


def test_wheel_contains_bundled_resources(tmp_path):
    """The wheel must ship templates/ and references/ as package data."""
    wheel = _build_wheel(tmp_path)
    with zipfile.ZipFile(wheel) as zf:
        names = set(zf.namelist())
    for rel in _required_wheel_files():
        assert any(n.endswith(rel) for n in names), f"wheel missing {rel}"


def test_wheel_exposes_console_scripts(tmp_path):
    wheel = _build_wheel(tmp_path)
    with zipfile.ZipFile(wheel) as zf:
        names = zf.namelist()
        # entry_points.txt is emitted by setuptools for [project.scripts].
        ep = next((n for n in names if n.endswith("entry_points.txt")), None)
        assert ep is not None, "wheel has no entry_points.txt"
        text = zf.read(ep).decode("utf-8")
    for script in (
        "obsidian-create-note",
        "obsidian-update-note",
        "obsidian-audit-vault",
        "obsidian-process-inbox",
        "obsidian-suggest-links",
        "obsidian-vault-info",
        "obsidian-detect-index",
        "obsidian-scaffold-templates",
    ):
        assert f"{script} =" in text, f"console script missing: {script}"


def test_installed_cli_works_without_repo(tmp_path):
    """Install the wheel into a clean venv and run it from a dir outside ROOT.

    This is the decisive test: resources must come from the wheel
    (importlib.resources), never from a source checkout that isn't even on the
    path here.
    """
    wheel = _build_wheel(tmp_path)

    venv = tmp_path / "venv"
    subprocess.run(
        [sys.executable, "-m", "venv", str(venv)],
        check=True,
        capture_output=True,
        text=True,
    )
    pip = venv / "bin" / "pip"
    subprocess.run(
        [str(pip), "install", str(wheel)],
        check=True,
        capture_output=True,
        text=True,
    )
    cli = venv / "bin" / "obsidian-scaffold-templates"

    # Work from a directory with no knowledge of the source repo.
    work = tmp_path / "away"
    work.mkdir()
    vault = work / "vault"
    vault.mkdir()
    (vault / ".obsidian").mkdir()

    out = subprocess.run(
        [str(cli), str(vault), "--apply"],
        cwd=work,
        check=True,
        capture_output=True,
        text=True,
    )
    if out.returncode != 0:  # pragma: no cover - surfaced for debugging
        print("STDERR:", out.stderr)
        print("STDOUT:", out.stdout)
    # The Digest template is the one install.ps1 used to drop — asserting it here
    # proves the fix travels through the wheel, not just the repo.
    assert (vault / "Templates" / "Digest Note.md").is_file(), (
        "installed scaffold did not write the Digest template:\n" + out.stdout
    )
    assert (vault / "Templates" / "Daily Note.md").is_file()

    # create_note must also resolve resources from the wheel (no --skill-root).
    create = venv / "bin" / "obsidian-create-note"
    res = subprocess.run(
        [
            str(create), str(vault), "--type", "insight-note",
            "--title", "wheel-proven", "--apply", "--json",
        ],
        cwd=work,
        check=True,
        capture_output=True,
        text=True,
    )
    assert (vault / "30-Insights").exists()
    created = sorted((vault / "30-Insights").glob("*.md"))
    assert created, "create_note produced no file"

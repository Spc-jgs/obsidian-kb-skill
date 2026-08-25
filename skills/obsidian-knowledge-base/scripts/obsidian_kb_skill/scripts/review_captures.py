#!/usr/bin/env python3
"""Report which captures were written and never opened again.

Every other measurement in this Skill asks whether a capture is *faithful* —
does the note carry the source's facts, does it declare its evidence level,
did it stop when the material was unavailable. None asks whether the capture
was ever used, and that is the question the whole workflow exists to answer.

Christian Tietze named the failure in 2014 (*The Collector's Fallacy*):
"having a text at hand does nothing to increase our knowledge". Andy Matuschak
states the design requirement this module implements — an inbox "should
encourage lingering items to be removed (e.g. it should be obvious when one
has been passed over many times)".

Deliberately not a finding. A cold capture is not a defect and this module
emits no severity: on the reference Vault 66 captures were cold, and one
finding each would bury the audit exactly the way `similar-title` did with 115
of which 113 were normal practice. An aggregate with the coldest examples is
what a reader can act on.
"""
from __future__ import annotations

import argparse
import datetime
import json
import re
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

from obsidian_kb_skill.scripts.git_history import unquote_git_path


SCHEMA_VERSION = "1.0"

# Types whose whole purpose is a single writing. A daily report is not meant
# to be revisited and a folder index is generated, so counting either as a
# cold capture would measure the Vault's shape rather than its intake.
CAPTURE_TYPES = frozenset({
    "web-clip",
    "learning-note",
    "insight-note",
    "conversation-digest",
})

# `.obsidian-kb-backups/` holds copies this Skill made before a write. A copy
# is never reopened by anyone, so counting one guarantees it lands in
# `never_reopened` and pulls the revisit rate down — and the reader is shown
# a backup path as a note worth revisiting. `audit_vault` and `search_vault`
# both skip it; this list did not.
IGNORED_DIRECTORIES = frozenset(
    {".obsidian", ".trash", ".git", "Templates", ".obsidian-kb-backups"}
)

_FRONTMATTER = re.compile(r"\A---\r?\n(.*?)\r?\n---", re.S)
_TYPE = re.compile(r"^type:\s*[\"']?([A-Za-z0-9_-]+)", re.M)
_DATE = re.compile(r"^date:\s*[\"']?(\d{4}-\d{2}-\d{2})", re.M)


@dataclass(frozen=True)
class ColdCapture:
    path: str
    note_type: str
    created: str
    last_touched: str
    cold_days: int

    def as_dict(self) -> dict[str, Any]:
        return {
            "path": self.path,
            "type": self.note_type,
            "created": self.created,
            "last_touched": self.last_touched,
            "cold_days": self.cold_days,
        }


def _markdown_files(vault: Path) -> Iterable[Path]:
    for path in sorted(vault.rglob("*.md")):
        if any(part in IGNORED_DIRECTORIES for part in path.relative_to(vault).parts):
            continue
        if path.is_file():
            yield path


def _git_last_revision(vault: Path) -> dict[str, str] | None:
    """Last commit date per tracked file, or None when this is not a repo.

    Exact where it applies, and it does not apply everywhere: a note created
    but never committed has no history here, and the caller dates it by mtime
    and counts it under `file-mtime` so a partial answer is never read as a
    complete one.

    An earlier version of this docstring said "on the reference Vault only 57
    of 214 notes were tracked". That was wrong, and wrong in the direction
    that hides a defect: the untracked ones were not untracked at all, they
    were escaped by `core.quotepath` and matched nothing. Measured on that
    Vault the day this was fixed — 219 notes on disk, every one of them
    tracked — the map matched **51** before decoding and **219** after.
    """
    probe = subprocess.run(
        ["git", "-C", str(vault), "rev-parse", "--is-inside-work-tree"],
        capture_output=True, text=True,
    )
    if probe.returncode != 0 or probe.stdout.strip() != "true":
        return None
    log = subprocess.run(
        ["git", "-C", str(vault), "log", "--name-only", "--format=%x00%cs", "--", "*.md"],
        capture_output=True, text=True,
    )
    if log.returncode != 0:
        return None
    latest: dict[str, str] = {}
    stamp = ""
    for line in log.stdout.splitlines():
        if line.startswith("\x00"):
            stamp = line[1:].strip()
            continue
        name = unquote_git_path(line.strip())
        if name and stamp:
            latest.setdefault(name, stamp)
    return latest


def review_captures(
    vault: Path,
    *,
    as_of: datetime.date | None = None,
    cold_after_days: int = 0,
    top_k: int = 20,
) -> dict[str, Any]:
    vault = Path(vault).expanduser().resolve()
    as_of = as_of or datetime.date.today()

    revisions = _git_last_revision(vault)
    evidence = "git-history" if revisions is not None else "file-mtime"
    caveat = (
        "git history covers tracked files only; evidence_coverage says how many "
        "captures each source actually dated"
        if evidence == "git-history"
        else "file mtime is perturbed by sync clients and by any git checkout"
    )
    # `evidence` names the preferred source, but the choice is made per note,
    # so one word for the whole report can be a lie — and was: a decoding
    # defect sent most notes to mtime while this still said `git-history`.
    # Both keys are always present so `sum(...) == summary.captures` holds
    # whatever the Vault is.
    coverage = {"git-history": 0, "file-mtime": 0}

    cold: list[ColdCapture] = []
    counts: dict[str, dict[str, int]] = {}
    captures = 0

    for path in _markdown_files(vault):
        text = path.read_text(encoding="utf-8", errors="replace")
        head = _FRONTMATTER.search(text)
        if not head:
            continue
        type_match = _TYPE.search(head.group(1))
        date_match = _DATE.search(head.group(1))
        if not type_match or not date_match:
            continue
        note_type = type_match.group(1)
        if note_type not in CAPTURE_TYPES:
            continue

        relative = path.relative_to(vault).as_posix()
        created = datetime.date.fromisoformat(date_match.group(1))
        touched_raw = (revisions or {}).get(relative)
        if touched_raw:
            touched = datetime.date.fromisoformat(touched_raw)
            coverage["git-history"] += 1
        else:
            touched = datetime.date.fromtimestamp(path.stat().st_mtime)
            coverage["file-mtime"] += 1

        captures += 1
        bucket = counts.setdefault(note_type, {"captures": 0, "never_reopened": 0})
        bucket["captures"] += 1
        if (touched - created).days <= cold_after_days:
            bucket["never_reopened"] += 1
            cold.append(
                ColdCapture(
                    path=relative,
                    note_type=note_type,
                    created=created.isoformat(),
                    last_touched=touched.isoformat(),
                    cold_days=(as_of - touched).days,
                )
            )

    cold.sort(key=lambda item: (-item.cold_days, item.path))
    by_type = [
        {
            "type": name,
            "captures": row["captures"],
            "never_reopened": row["never_reopened"],
            "revisit_rate": round(
                (row["captures"] - row["never_reopened"]) / row["captures"], 3
            ),
        }
        for name, row in sorted(counts.items())
    ]
    never = sum(row["never_reopened"] for row in counts.values())

    return {
        "schema_version": SCHEMA_VERSION,
        "ok": True,
        "command": "review-captures",
        "read_only": True,
        "as_of": as_of.isoformat(),
        "evidence": evidence,
        "evidence_caveat": caveat,
        "evidence_coverage": coverage,
        "cold_after_days": cold_after_days,
        "summary": {
            "captures": captures,
            "never_reopened": never,
            "revisit_rate": round((captures - never) / captures, 3) if captures else None,
        },
        "by_type": by_type,
        "items": [item.as_dict() for item in cold[:top_k]],
        "truncated": len(cold) > top_k,
    }


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Report captures that were written and never opened again."
    )
    parser.add_argument("vault", type=Path)
    parser.add_argument("--cold-after-days", type=int, default=0)
    parser.add_argument("--top-k", type=int, default=20)
    parser.add_argument("--json", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    report = review_captures(
        args.vault, cold_after_days=args.cold_after_days, top_k=args.top_k
    )
    if args.json:
        print(json.dumps(report, ensure_ascii=False))
        return 0
    summary = report["summary"]
    print(f"captures {summary['captures']}, never reopened {summary['never_reopened']}")
    print(f"evidence: {report['evidence']} ({report['evidence_caveat']})")
    for row in report["by_type"]:
        print(f"  {row['type']:22s} revisit {row['revisit_rate']:.0%}"
              f"  ({row['captures'] - row['never_reopened']}/{row['captures']})")
    for item in report["items"]:
        print(f"  cold {item['cold_days']:4d}d  {item['path']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

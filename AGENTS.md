# Repository Guidelines

## Project Structure & Module Organization

`core/` contains the canonical Skill instructions, references, and note templates. Python helper code lives in `obsidian_kb_skill/`, with CLI entry points declared in `pyproject.toml`. `build.py` combines the core content with platform headers and synchronizes generated deliverables under `skills/` and `platforms/`. Do not edit those generated files directly; change their source and regenerate them. Tests are in `tests/`, fixture data is in `tests/fixtures/`, user documentation is in `docs/`, and installer entry points are `install.sh` and `install.ps1`.

## Build, Test, and Development Commands

- `uv sync --locked --extra dev` installs the pinned development environment, including pytest and build tooling.
- `uv run python build.py` regenerates Skill bundles, platform adapters, manifests, and packaged resources after source changes.
- `uv run --no-sync python build.py --check` verifies that generated artifacts match their sources without rewriting them.
- `uv run --no-sync python -m pytest` runs the complete test suite using the repository import path.
- `uv lock --check` confirms that `uv.lock` is current.

Python 3.11 or newer is required; CI exercises Python 3.11 and 3.14, plus the PowerShell installer on Windows.

## Coding Style & Naming Conventions

Use four-space indentation, UTF-8, and LF line endings. Follow existing Python conventions: `snake_case` for modules and functions, `PascalCase` for classes, descriptive constants in `UPPER_SNAKE_CASE`, type annotations for public boundaries, and `pathlib.Path` for filesystem work. Keep CLI output and error contracts deterministic. No formatter or linter is configured, so match nearby code and keep imports grouped as standard library, third-party, then local.

## Testing Guidelines

Pytest discovers `tests/test_*.py`; name tests `test_<behavior>` and group related cases in `Test...` classes when useful. Add regression tests for bug fixes and fixtures for larger evaluation cases. There is no configured coverage threshold. Before opening a PR, run the generated-artifact check, full pytest suite, and lockfile check. Installer or path changes should cover POSIX and Windows behavior where applicable.

When a change makes two places have to agree — a constant restating what another module declares, a list duplicated because the two bundles cannot import each other, documentation naming a code or path the code also names — add an assertion **in the same change**, and a row to `docs/superpowers/specs/2026-08-12-consistency-inventory.md`. This project's recurring defect is a boundary nobody checks: the failure is silent, and the first drift is found by a user. If the relation cannot be checked mechanically, record the row with its guard as **none** and say why.

A conclusion about a population — how many, which ones, what fraction — must cite a command whose output can be recounted. Sampling with `head` and then stating the whole is a mistake this project has already made: #93's body says tightening the reachability predicate would mark six bundled helpers unreachable, the breakdown printed directly beneath it implies one, and the predicate run today prints two — it had enumerated 11 of the 13. The same habit put the wrong file in #133's quotation, which led that issue to propose the wrong fix, and shaped #117's adversarial long notes the way their author pictured a long note rather than the way the reference Vault holds them. Prose is the carrier, so no test will ever catch one: state a count with the command that produced it, or do not state it.

A new assertion must be seen red at least once — write it before the code, or temporarily break what it guards. An assertion green from birth has never distinguished "correct" from "watching something that cannot change". Row 17 of the inventory asserts truthfully and covers less than its name suggests; #118's assertion for the reported signals was **vacuous**, passed, and let a wrong output through, which reading the printed output caught and the green tick could not; deleting on purpose the criterion two of #75's guards were written for changed nothing they asserted. None of that is visible from a passing suite. Neither this rule nor the one above can be checked mechanically — what they govern is how a conclusion was reached, and that leaves no trace in the tree.

## Commit & Pull Request Guidelines

History follows Conventional Commits, often with a scope and concise Chinese description, for example `feat(retrieval): 增加元数据过滤` or `fix(tests): 按 UTF-8 解码输出`. Keep commits focused; use `release:` only for version releases. PRs should explain the problem, summarize source and generated-file changes, list verification commands and results, and link the relevant issue. Include screenshots only when documentation assets or other visible output changes.

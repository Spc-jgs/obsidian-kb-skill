"""Shared test isolation.

The preflight cache defaults to the real user home, which is right for a real
run and wrong for a test: a suite that stages content must not leave entries in
the developer's home directory.

The override is installed at import time rather than through a fixture because
several test modules snapshot `os.environ` at module scope to build the child
process environment, and a fixture would run too late to reach those copies.
"""
from __future__ import annotations

import os
import shutil
import tempfile

from obsidian_kb_skill.scripts.preflight_cache import CACHE_DIR_ENV

_CACHE_DIR = tempfile.mkdtemp(prefix="obsidian-kb-preflight-")
os.environ[CACHE_DIR_ENV] = _CACHE_DIR


def pytest_sessionfinish(session, exitstatus):  # noqa: ARG001
    shutil.rmtree(_CACHE_DIR, ignore_errors=True)

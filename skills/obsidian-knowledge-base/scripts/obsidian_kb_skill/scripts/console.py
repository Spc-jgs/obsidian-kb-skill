"""Cross-platform console setup shared by every helper CLI."""
from __future__ import annotations

import sys
from typing import TextIO


def _reconfigure_utf8(stream: TextIO) -> None:
    reconfigure = getattr(stream, "reconfigure", None)
    if not callable(reconfigure):
        return
    try:
        reconfigure(encoding="utf-8")
    except (AttributeError, OSError, ValueError):
        # StringIO/test doubles and already-closed streams may not be
        # reconfigurable. Their caller owns the encoding contract.
        return


def configure_utf8_stdio() -> None:
    """Make helper output deterministic on legacy Windows code pages."""
    _reconfigure_utf8(sys.stdout)
    _reconfigure_utf8(sys.stderr)

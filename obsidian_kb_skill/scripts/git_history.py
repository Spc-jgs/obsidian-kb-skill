#!/usr/bin/env python3
"""Reading a Vault's git history without misreading the paths in it.

Two helpers ask git what it knows about a Vault — `review-captures` for when a
note was last touched, and the audit for whether a link target ever existed —
and both compare git's answer against paths on disk. That comparison is where
#201 happened: `core.quotepath` defaults to true, so git escapes any path
holding a non-ASCII byte, and an undecoded key matches nothing. The failure is
silent in both callers and wrong in a different direction in each: a capture
falls back to mtime, a deleted note reads as never written.

One decoder, imported by both, so the two cannot drift.
"""
from __future__ import annotations


_C_ESCAPES = {
    "a": "\a", "b": "\b", "f": "\f", "n": "\n",
    "r": "\r", "t": "\t", "v": "\v", '"': '"', "\\": "\\",
}


def unquote_git_path(name: str) -> str:
    """Decode the C-style quoting git applies to a path it must escape.

    Git wraps a path in quotes and escapes it whenever it holds bytes it will
    not print raw. With `core.quotepath` — which defaults to **true** — that
    includes every non-ASCII byte, so a Chinese filename arrives as
    `"20-Learning/\\346\\216\\230...md"` and matches nothing on disk. Setting
    `core.quotepath=false` would stop the octal escaping, but not the quoting:
    a path holding a quote, a backslash or a control character is still
    wrapped. Decoding here covers both and does not depend on the repository's
    configuration.

    The octal escapes are UTF-8 *bytes*, not code points, so they accumulate
    into a bytearray and are decoded once at the end — decoding each escape
    separately would corrupt every multi-byte character.
    """
    if len(name) < 2 or not (name.startswith('"') and name.endswith('"')):
        return name
    body = name[1:-1]
    out = bytearray()
    index = 0
    while index < len(body):
        char = body[index]
        if char != "\\":
            out.extend(char.encode("utf-8"))
            index += 1
            continue
        index += 1
        if index >= len(body):
            break
        escape = body[index]
        if escape in "01234567":
            out.append(int(body[index : index + 3], 8))
            index += 3
        else:
            out.extend(_C_ESCAPES.get(escape, escape).encode("utf-8"))
            index += 1
    return out.decode("utf-8", errors="replace")

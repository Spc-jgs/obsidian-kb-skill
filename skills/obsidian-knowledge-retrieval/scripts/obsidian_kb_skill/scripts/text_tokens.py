#!/usr/bin/env python3
"""The one tokenizer retrieval uses, for documents and for queries alike.

Extracted from `search_vault` when query expansion arrived: an expansion token
that was produced by a different tokenizer than the document index would simply
never match, and the bug would look like a bad lexicon rather than a split
implementation. One function, one definition of a token.
"""
from __future__ import annotations

import re


LATIN_TOKEN_RE = re.compile(r"[A-Za-z0-9]+")
TOKEN_RUN_RE = re.compile(r"[A-Za-z0-9]+|[\u3400-\u4dbf\u4e00-\u9fff]+")
CJK_RE = re.compile(r"[\u3400-\u4dbf\u4e00-\u9fff]")


def has_cjk(text: str) -> bool:
    """True when the text contains a CJK ideograph, which has no word delimiter."""
    return CJK_RE.search(text) is not None


def tokenize(text: str) -> list[str]:
    """Return stable lowercase Latin tokens and overlapping CJK bigrams."""
    tokens: list[str] = []
    for match in TOKEN_RUN_RE.finditer(text):
        run = match.group(0)
        if LATIN_TOKEN_RE.fullmatch(run):
            tokens.append(run.lower())
        elif len(run) == 1:
            tokens.append(run)
        else:
            tokens.extend(run[index : index + 2] for index in range(len(run) - 1))
    return tokens

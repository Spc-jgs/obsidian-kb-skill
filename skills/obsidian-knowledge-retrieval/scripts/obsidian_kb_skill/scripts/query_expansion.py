#!/usr/bin/env python3
"""Deterministic cross-lingual query expansion for read-only Vault search.

A Chinese query and an English note share no token at all: `tokenize()` emits
Latin words and CJK bigrams, and those alphabets never meet. BM25 then has
nothing to rank and the search returns zero results — not a bad answer, no
answer. That is a vocabulary gap between the language the reader thinks in and
the language the note was written in, and a bilingual Vault has it on every note
whose author switched languages mid-project.

This module closes the gap the cheap way: a curated concept lexicon, matched
against the raw query, contributing extra tokens at reduced weight. It is
offline, deterministic, writes nothing, and every token it adds is reported back
so the reader can see which words were the search's idea rather than theirs.

It is not a synonym dictionary and must not become one. Entries cover the
subjects this Skill serves; general language is rejected structurally by
`validate_concepts`.
"""
from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
import re
from typing import Any, Iterable, Sequence

from obsidian_kb_skill.scripts.text_tokens import has_cjk, tokenize


LEXICON_FOLDER = ".obsidian-kb"
LEXICON_FILENAME = "retrieval-lexicon.json"
LEXICON_SCHEMA_VERSION = 1

# An expanded word is a hypothesis about what the reader meant; a typed word is
# evidence. Under the field weights in `search_vault` one direct title token is
# worth roughly 4-6, so holding expansion below half keeps two guessed body hits
# from displacing one real title hit.
EXPANSION_WEIGHT = 0.45
# Bounds on the explanation, not on the arithmetic. A response naming twenty
# concepts cannot be read, so it cannot be audited.
MAX_EXPANSION_CONCEPTS = 8
MAX_EXPANSION_TOKENS = 24

MIN_TERM_CHARS = 2
MAX_TERM_CHARS = 40
MAX_TERMS_PER_CONCEPT = 12
MAX_USER_CONCEPTS = 200
MAX_LEXICON_BYTES = 64 * 1024

CONCEPT_ID_RE = re.compile(r"^[a-z0-9][a-z0-9-]{0,63}$")

# General language never earns a place here. One of these inside a concept makes
# it fire on unrelated questions, and the reader cannot tell why the search
# wandered. Checked mechanically, so the rule survives a tired reviewer.
LEXICON_STOPWORDS = frozenset(
    {
        "一起", "一样", "东西", "什么", "以及", "但是", "使用", "关于", "内容",
        "包括", "可以", "哪些", "地方", "处理", "如何", "存在", "怎么", "怎样",
        "情况", "意思", "所有", "方式", "方法", "时候", "有关", "查看", "样子",
        "然后", "现在", "用来", "自己", "行为", "解决", "说明", "这些", "进行",
        "通过", "问题", "需要",
        "content", "detail", "example", "general", "issue", "item", "matter",
        "method", "other", "point", "problem", "stuff", "thing", "topic",
        "value", "way",
    }
)


class LexiconError(ValueError):
    """A lexicon — built-in or user-supplied — violates its structural rules."""


@dataclass(frozen=True)
class Concept:
    """Surface forms that mean the same thing, in any mix of languages."""

    id: str
    terms: tuple[str, ...]


@dataclass(frozen=True)
class ConceptMatch:
    """One concept that fired, and what it contributed."""

    id: str
    matched: str
    added: tuple[str, ...]

    def payload(self) -> dict[str, Any]:
        return {"id": self.id, "matched": self.matched, "added": list(self.added)}


@dataclass(frozen=True)
class QueryExpansion:
    """Extra tokens a query earned, with the evidence for each of them."""

    tokens: tuple[str, ...] = ()
    concepts: tuple[ConceptMatch, ...] = ()
    truncated: bool = False

    @property
    def active(self) -> bool:
        return bool(self.tokens)

    def payload(self) -> dict[str, Any]:
        return {
            "weight": EXPANSION_WEIGHT,
            "tokens": list(self.tokens),
            "concepts": [concept.payload() for concept in self.concepts],
            "truncated": self.truncated,
        }


# `_C` keeps the table below readable: the data is the point, the constructor is
# not. Terms are written in the order a reader would explain the concept.
def _C(concept_id: str, *terms: str) -> Concept:
    return Concept(id=concept_id, terms=tuple(terms))


# Concepts a term deliberately belongs to more than once. Chinese 代理 really is
# both an agent and a network proxy, and a search for one should say out loud
# that it also considered the other rather than silently picking. Anything not
# listed here that collides is an editing accident, and the invariant test says
# so.
AMBIGUOUS_TERMS = frozenset({"代理"})


BUILTIN_CONCEPTS: tuple[Concept, ...] = (
    # -- Knowledge base, notes, Obsidian ----------------------------------
    _C("archive", "归档", "存档", "archive", "archival"),
    _C("backup", "备份", "还原", "backup", "restore"),
    _C("daily-note", "日报", "日记", "daily note", "journal"),
    _C("digest", "摘要", "综述", "digest", "summary"),
    _C("folder", "目录", "文件夹", "folder", "directory"),
    _C("folder-index", "目录索引", "索引文件", "folder index", "index note"),
    _C("frontmatter", "元数据", "前置信息", "frontmatter", "metadata"),
    _C("governance", "治理", "规范", "governance", "policy"),
    _C("inbox", "收件箱", "收集箱", "待整理", "inbox"),
    _C("knowledge", "知识", "knowledge"),
    _C("knowledge-graph", "知识图谱", "知识图", "图谱", "knowledge graph", "graph"),
    _C("link", "链接", "双链", "反向链接", "wikilink", "backlink", "link"),
    _C("meeting-note", "会议纪要", "会议记录", "meeting note", "minutes"),
    _C("navigation", "导航", "navigation", "navigate"),
    _C("note", "笔记", "note"),
    _C("plugin", "插件", "扩展程序", "plugin", "extension"),
    _C("save", "保存", "写入", "记下", "save", "write"),
    _C("tag", "标签", "tag", "label"),
    _C("template", "模板", "template", "scaffold"),
    _C("vault", "知识库", "vault", "knowledge base"),
    # -- Retrieval and ranking ---------------------------------------------
    _C("filter", "过滤", "筛选", "filter"),
    _C("index", "索引", "index", "indexing"),
    _C("lexical-search", "词法", "关键词", "字面", "lexical", "keyword"),
    _C("query", "查询", "提问", "query"),
    _C("ranking", "排序", "排名", "打分", "ranking", "rank", "score"),
    _C("recall", "召回", "查全", "recall"),
    _C("relevance", "相关性", "相关度", "relevance", "relevant"),
    _C("retrieval", "检索", "搜索", "查找", "retrieval", "search"),
    _C("semantic", "语义", "含义", "semantic", "meaning"),
    _C("snippet", "片段", "摘录", "snippet", "excerpt"),
    _C("tokenization", "分词", "切词", "tokenization", "tokenize", "token"),
    _C("vector-embedding", "向量", "嵌入", "embedding", "vector"),
    # -- Agents, skills, permission ----------------------------------------
    _C("agent", "代理", "智能体", "助手", "agent"),
    _C("context", "上下文", "context"),
    _C("continue", "接着", "继续", "续做", "continue", "resume"),
    _C("handoff", "交接", "续接", "接力", "handoff", "handover"),
    _C("model", "模型", "language model", "model"),
    _C("permission", "权限", "授权", "许可", "permission", "authorization"),
    _C("protocol", "协议", "protocol"),
    _C("read-only", "只读", "read-only", "read only"),
    _C("skill", "技能", "skill"),
    _C("task", "任务", "工作项", "task", "work item"),
    _C("tool-server", "工具服务器", "工具服务", "tool server", "mcp server"),
    _C("transport", "传输", "通道", "transport", "channel"),
    _C("untrusted-input", "不可信", "不可靠", "untrusted", "unsafe input"),
    # -- Capture and sourcing ----------------------------------------------
    _C("article", "文章", "帖子", "article", "post"),
    _C("capture", "采集", "捕获", "抓取", "capture", "clip"),
    _C("checksum", "哈希", "校验和", "指纹", "hash", "checksum"),
    _C("evidence", "证据", "凭据", "evidence"),
    _C("provenance", "可追溯", "溯源", "出处", "traceability", "provenance"),
    _C("rewrite", "改写", "重写", "rewrite", "paraphrase"),
    _C("source-text", "原文", "原始材料", "来源", "source text", "source", "verbatim"),
    _C("web-clip", "网页剪藏", "网页收藏", "web clip", "web capture"),
    # -- Backend and delivery ------------------------------------------------
    _C("buffering", "缓冲", "攒批", "buffering", "buffer"),
    _C("cache", "缓存", "cache", "caching"),
    _C(
        "cache-stampede",
        "缓存击穿", "缓存雪崩", "惊群",
        "cache stampede", "thundering herd", "single-flight",
    ),
    _C("concurrency", "并发", "同时", "concurrency", "concurrent"),
    _C("expiry", "过期", "失效", "到期", "expiry", "expire", "ttl"),
    _C("latency", "延迟", "卡顿", "latency", "delay"),
    _C("proxy", "反向代理", "代理", "reverse proxy", "proxy"),
    _C("queue", "队列", "queue", "backlog"),
    _C("recompute", "重算", "重新计算", "recompute", "recomputation"),
    _C("request", "请求", "调用方", "request", "caller"),
    _C("retry", "重试", "retry"),
    _C("reuse", "复用", "重用", "reuse"),
    _C(
        "server-sent-events",
        "服务器推送", "实时推送", "事件流",
        "server-sent events", "sse", "event stream",
    ),
    _C("streaming", "流式", "增量", "streaming", "incremental"),
    # -- Data and schema ------------------------------------------------------
    _C("backfill", "回填", "补数据", "backfill"),
    _C("database-schema", "表结构", "库表", "数据库结构", "database schema", "schema"),
    _C("deploy", "上线", "发布", "部署", "deploy", "release"),
    _C("migration", "迁移", "migration", "migrate"),
    _C("zero-downtime", "不停机", "零停机", "zero-downtime", "zero downtime"),
    # -- Environments and tooling ---------------------------------------------
    _C("connection", "连接", "接入", "connect", "connection"),
    _C(
        "continuous-integration",
        "持续集成", "流水线",
        "continuous integration", "ci pipeline", "ci",
    ),
    _C("dependency", "依赖", "依赖项", "dependency", "dependencies"),
    _C("install", "安装", "install", "installation"),
    _C("interpreter", "解释器", "运行时版本", "interpreter", "runtime version"),
    _C("lockfile", "锁文件", "锁定版本", "lockfile", "lock file", "pin"),
    _C(
        "reproducibility",
        "可复现", "结果一致", "完全相同",
        "reproducible", "reproducibility",
    ),
    # -- Security ---------------------------------------------------------------
    _C("path-containment", "路径遏制", "越界路径", "path containment", "path traversal"),
    _C("symlink", "符号链接", "软链接", "symlink", "symbolic link"),
    _C("trust-boundary", "信任边界", "安全边界", "trust boundary", "security boundary"),
    _C("validation", "校验", "验证", "validation", "validate"),
)


def duplicate_terms(concepts: Sequence[Concept]) -> tuple[str, ...]:
    """Terms claimed by more than one concept, so ambiguity has to be declared."""
    owners: dict[str, set[str]] = {}
    for concept in concepts:
        for term in concept.terms:
            owners.setdefault(term, set()).add(concept.id)
    return tuple(sorted(term for term, ids in owners.items() if len(ids) > 1))


def validate_concepts(
    concepts: Sequence[Concept], *, source: str, limit: int | None = None
) -> tuple[Concept, ...]:
    """Enforce the structural rules a lexicon must satisfy to be loadable.

    Applied to the built-in table by its own test and to a user's file at load
    time, so the shipped lexicon cannot quietly break a rule a user's file is
    refused for.
    """
    if limit is not None and len(concepts) > limit:
        raise LexiconError(f"{source}: at most {limit} concepts are allowed")
    seen_ids: set[str] = set()
    for concept in concepts:
        if not CONCEPT_ID_RE.match(concept.id):
            raise LexiconError(
                f"{source}: concept id {concept.id!r} must be lowercase "
                "letters, digits, and hyphens"
            )
        if concept.id in seen_ids:
            raise LexiconError(f"{source}: duplicate concept id {concept.id!r}")
        seen_ids.add(concept.id)
        if not 2 <= len(concept.terms) <= MAX_TERMS_PER_CONCEPT:
            raise LexiconError(
                f"{source}: concept {concept.id!r} must carry 2 to "
                f"{MAX_TERMS_PER_CONCEPT} terms; one term expands to nothing"
            )
        if len(set(concept.terms)) != len(concept.terms):
            raise LexiconError(f"{source}: concept {concept.id!r} repeats a term")
        for term in concept.terms:
            if term != term.strip() or not term:
                raise LexiconError(
                    f"{source}: concept {concept.id!r} has an untrimmed term"
                )
            if not MIN_TERM_CHARS <= len(term) <= MAX_TERM_CHARS:
                raise LexiconError(
                    f"{source}: term {term!r} must be {MIN_TERM_CHARS} to "
                    f"{MAX_TERM_CHARS} characters; a single character is a "
                    "morpheme, not a concept"
                )
            if term.casefold() in LEXICON_STOPWORDS:
                raise LexiconError(
                    f"{source}: term {term!r} is general language and would "
                    "fire on unrelated questions"
                )
    return tuple(concepts)


def _read_lexicon_document(path: Path) -> dict[str, Any]:
    size = path.stat().st_size
    if size > MAX_LEXICON_BYTES:
        raise LexiconError(
            f"{LEXICON_FILENAME}: file exceeds {MAX_LEXICON_BYTES} bytes"
        )
    try:
        raw = path.read_text(encoding="utf-8")
    except (OSError, UnicodeError) as exc:
        raise LexiconError(f"{LEXICON_FILENAME}: {exc}") from exc
    try:
        document = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise LexiconError(
            f"{LEXICON_FILENAME}: not valid JSON at line {exc.lineno}"
        ) from exc
    if not isinstance(document, dict):
        raise LexiconError(f"{LEXICON_FILENAME}: top level must be an object")
    if document.get("schema_version") != LEXICON_SCHEMA_VERSION:
        raise LexiconError(
            f"{LEXICON_FILENAME}: schema_version must be "
            f"{LEXICON_SCHEMA_VERSION}"
        )
    return document


def _concepts_from_document(document: dict[str, Any]) -> list[Concept]:
    entries = document.get("concepts")
    if not isinstance(entries, list):
        raise LexiconError(f"{LEXICON_FILENAME}: 'concepts' must be a list")
    concepts: list[Concept] = []
    for position, entry in enumerate(entries, start=1):
        if not isinstance(entry, dict):
            raise LexiconError(
                f"{LEXICON_FILENAME}: concept {position} must be an object"
            )
        concept_id = entry.get("id")
        terms = entry.get("terms")
        if not isinstance(concept_id, str):
            raise LexiconError(
                f"{LEXICON_FILENAME}: concept {position} has no string 'id'"
            )
        if not isinstance(terms, list) or not all(
            isinstance(term, str) for term in terms
        ):
            raise LexiconError(
                f"{LEXICON_FILENAME}: concept {concept_id!r} needs a list of "
                "string 'terms'"
            )
        concepts.append(Concept(id=concept_id, terms=tuple(terms)))
    return concepts


def lexicon_path(vault: Path) -> Path:
    """Where a Vault keeps its own concepts. Dot-prefixed, so never indexed."""
    return vault / LEXICON_FOLDER / LEXICON_FILENAME


def load_lexicon(vault: Path | None) -> tuple[Concept, ...]:
    """Return the built-in concepts plus this Vault's own, in that order.

    A Vault may hold vocabulary no shipped table can guess — a team's product
    names, the Chinese term a particular author prefers. Absent file means
    built-ins only; a malformed one refuses rather than degrading silently,
    because a search that quietly ran with different vocabulary than the file
    describes is a search nobody can reproduce.
    """
    builtin = validate_concepts(BUILTIN_CONCEPTS, source="built-in lexicon")
    if vault is None:
        return builtin
    path = lexicon_path(vault)
    if not path.exists():
        return builtin
    if path.is_symlink() or not path.is_file():
        raise LexiconError(
            f"{LEXICON_FILENAME}: must be a regular file inside the Vault"
        )
    user = _concepts_from_document(_read_lexicon_document(path))
    known = {concept.id for concept in builtin}
    for concept in user:
        if concept.id in known:
            raise LexiconError(
                f"{LEXICON_FILENAME}: concept id {concept.id!r} is already a "
                "built-in concept; choose another id"
            )
    return builtin + validate_concepts(
        user, source=LEXICON_FILENAME, limit=MAX_USER_CONCEPTS
    )


def _match_offset(term: str, query: str, query_tokens: Sequence[str]) -> int | None:
    """Return where a term matches the query, or None.

    CJK has no word delimiter, so a Chinese term matches as a substring — that
    is the only operator that finds 击穿 inside 避免缓存击穿的方案. A Latin term
    matches as a consecutive token run instead, so `cache stampede` matches
    "cache stampede control" and not a query that happens to contain both words
    a sentence apart.
    """
    if has_cjk(term):
        offset = query.casefold().find(term.casefold())
        return offset if offset >= 0 else None
    needle = tokenize(term)
    if not needle:
        return None
    for start in range(len(query_tokens) - len(needle) + 1):
        if list(query_tokens[start : start + len(needle)]) == needle:
            return start
    return None


def expand_query(
    query: str, concepts: Iterable[Concept] = BUILTIN_CONCEPTS
) -> QueryExpansion:
    """Return the tokens a curated lexicon adds to this query, and why.

    Order is fixed — concepts by where they matched, then by id; tokens in the
    order the concept lists them — so the same query produces the same expansion
    on every machine and the published evaluation stays reproducible.
    """
    typed = tokenize(query)
    typed_set = set(typed)
    candidates: list[tuple[int, str, ConceptMatch]] = []
    for concept in concepts:
        best: tuple[int, str] | None = None
        for term in concept.terms:
            offset = _match_offset(term, query, typed)
            if offset is not None and (best is None or offset < best[0]):
                best = (offset, term)
        if best is None:
            continue
        added: list[str] = []
        for term in concept.terms:
            for token in tokenize(term):
                if token not in typed_set and token not in added:
                    added.append(token)
        if not added:
            continue
        candidates.append(
            (best[0], concept.id, ConceptMatch(concept.id, best[1], tuple(added)))
        )
    candidates.sort(key=lambda item: (item[0], item[1]))

    matches: list[ConceptMatch] = []
    tokens: list[str] = []
    truncated = False
    for _, _, match in candidates:
        if len(matches) >= MAX_EXPANSION_CONCEPTS:
            truncated = True
            break
        kept: list[str] = []
        for token in match.added:
            if token in tokens:
                continue
            if len(tokens) >= MAX_EXPANSION_TOKENS:
                truncated = True
                break
            tokens.append(token)
            kept.append(token)
        if kept:
            matches.append(ConceptMatch(match.id, match.matched, tuple(kept)))
        if truncated:
            break
    return QueryExpansion(
        tokens=tuple(tokens), concepts=tuple(matches), truncated=truncated
    )

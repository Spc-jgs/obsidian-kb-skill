### Task 2: Byte-Preserving Typed Inbox Plans

**Files:**
- Modify: `obsidian_kb_skill/scripts/inbox_plan.py`
- Modify: `tests/test_inbox_plan.py`

**Interfaces:**
- Consumes: `InboxSourceSnapshot` and catalog route mappings. Preserve the
  current H1-or-filename title behavior with an Inbox-local private helper; do
  not create a new cross-module dependency on `audit_vault._note_title()`.
  `StaticIndexPlan` is forward-referenced and remains `None` until Task 3.
- Produces:

```python
InboxStatus = Literal["ready", "skipped", "blocked"]

@dataclass(frozen=True)
class InboxProposal:
    destination: Path
    target: str
    note_type: str
    tags: tuple[str, ...]
    metadata_updates: tuple[tuple[str, object], ...]
    rendered_bytes: bytes
    rendered_sha256: str
    index: StaticIndexPlan | None

@dataclass(frozen=True)
class InboxPlanItem:
    source: Path
    identity: SourceIdentity | None
    source_sha256: str | None
    title: str | None
    status: InboxStatus
    proposal: InboxProposal | None
    issue: InboxIssue | None

@dataclass(frozen=True)
class InboxPlan:
    effective_date: str
    items: tuple[InboxPlanItem, ...]

def render_frontmatter_updates(
    snapshot: InboxSourceSnapshot,
    updates: Mapping[str, object],
) -> bytes: ...

def plan_inbox(
    vault: Path,
    inbox_name: str = "00-Inbox",
    *,
    effective_date: str | None = None,
) -> InboxPlan: ...

def legacy_plan_dict(vault: Path, item: InboxPlanItem) -> dict[str, Any]: ...
```

- [ ] **Step 1: Write rendering and proposal RED tests**

Cover no frontmatter, valid LF, valid CRLF, UTF-8 BOM, comments, quoted values,
missing one or three keys, existing scalar/list tags, and empty/null existing
`date/type/tags`. Assert the original body slice appears byte-for-byte in the
rendered output and no existing frontmatter line changes.

```python
def test_render_inserts_missing_keys_without_rewriting_frontmatter(tmp_path: Path):
    original = (
        b"\xef\xbb\xbf---\r\n"
        b'title: "Keep quoting" # keep comment\r\n'
        b"---\r\n# Body\r\nexact  \r\n"
    )
    item = snapshot_one(tmp_path, original)

    rendered = render_frontmatter_updates(
        item,
        {"date": "2042-03-04", "type": "insight-note", "tags": ["insight"]},
    )

    assert b'title: "Keep quoting" # keep comment\r\n' in rendered
    assert rendered.endswith(b"# Body\r\nexact  \r\n")
    assert parse_frontmatter(rendered.decode("utf-8-sig")).issue is None
```

Assert that changing raw bytes, route, update values, destination, or effective
date changes the relevant hashes/proposal. Assert `legacy_plan_dict()` retains
the existing `path`, `target`, `title`, `tags`, `type`, `related_suggestion`, and
`skip` meanings.

- [ ] **Step 2: Run focused RED tests**

```bash
uv run --locked --extra dev pytest tests/test_inbox_plan.py -q
```

Expected: failures for missing plan/render APIs.

- [ ] **Step 3: Implement the raw-byte renderer and typed planning**

Locate the raw frontmatter delimiter without reserializing existing YAML. Detect
the BOM and newline convention, insert only serialized lines for absent keys,
and reparse the rendered candidate. Use `yaml.safe_dump()` only on each new
value, never on the existing mapping. Reject a multi-line serialization that is
not an indented valid mapping entry.

An existing key with `None`, empty string, or empty list produces
`InboxIssue(code="ambiguous-empty-metadata", ...)`. An absent frontmatter block
may receive all three defaults. Freeze `effective_date` exactly once in
`plan_inbox()`.

Resolve both target directory and destination with shared Vault resolvers;
reject a destination that exists lexically, including a dangling symlink.

- [ ] **Step 4: Run focused and current Inbox regressions**

```bash
uv run --locked --extra dev pytest \
  tests/test_inbox_plan.py tests/test_process_inbox.py \
  tests/test_cli_integration.py tests/test_json_output.py -q
```

Expected: new typed-plan tests pass and old production behavior remains green
because the CLI has not switched adapters yet.

- [ ] **Step 5: Commit typed planning**

```bash
git add obsidian_kb_skill/scripts/inbox_plan.py tests/test_inbox_plan.py
git commit -m "refactor: model immutable inbox plans"
```

---


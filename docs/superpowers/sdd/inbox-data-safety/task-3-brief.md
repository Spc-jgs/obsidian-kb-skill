### Task 3: Pure Static-Index Plans

**Files:**
- Modify: `obsidian_kb_skill/scripts/folder_index_policy.py`
- Modify: `obsidian_kb_skill/scripts/inbox_plan.py`
- Modify: `tests/test_folder_index_policy.py`
- Modify: `tests/test_inbox_plan.py`

**Interfaces:**
- Consumes: `StaticIndexEntry`, existing Folder Index config and exclusion
  rules, `sha256_bytes()`.
- Produces:

```python
StaticIndexAction = Literal["append", "unchanged", "missing", "unmanaged"]

@dataclass(frozen=True)
class StaticIndexPlan:
    action: StaticIndexAction
    index: Path | None
    before: bytes | None
    after: bytes | None
    before_sha256: str | None
    after_sha256: str | None
    line: str | None

def plan_static_index_entry(
    vault: Path,
    entry: StaticIndexEntry,
) -> StaticIndexPlan: ...
```

- [ ] **Step 1: Write pure-plan RED tests**

Test missing index, Folder Index-managed, Dataview-managed, append, already
present, invalid plugin JSON, malicious plugin filenames, internal folder
symlink, external symlink, BOM/CRLF, and exact before/after bytes.

```python
def test_static_index_plan_is_read_only_and_byte_exact(tmp_path: Path):
    vault = make_vault(tmp_path)
    index = vault / "30-Insights" / "INDEX.md"
    before = b"# Insights\r\n"
    index.write_bytes(before)

    plan = plan_static_index_entry(
        vault,
        StaticIndexEntry(Path("30-Insights/Idea.md"), "Idea", "2042-03-04"),
    )

    assert plan.action == "append"
    assert plan.before == before
    assert plan.after == before + b"- [[30-Insights/Idea|Idea]] (2042-03-04)\r\n"
    assert index.read_bytes() == before
```

- [ ] **Step 2: Run RED**

```bash
uv run --locked --extra dev pytest \
  tests/test_folder_index_policy.py tests/test_inbox_plan.py -q
```

Expected: import/API failures for `StaticIndexPlan` and
`plan_static_index_entry()`.

- [ ] **Step 3: Implement the pure policy**

Refactor the current append decision into the pure function. Preserve the
existing `append_static_index_entry()` signature and `StaticIndexResult`; have
it call the pure planner and append only for `action == "append"`.

Read bytes and preserve the existing index newline convention. Escape or reject
titles that would create a multi-line index entry. Treat invalid enabled-plugin
configuration as a policy error for the pure Inbox plan, while keeping existing
consumer compatibility through the current non-strict config API.

Update `plan_inbox()` to attach `StaticIndexPlan` and block the item when index
ownership/path cannot be proved.

- [ ] **Step 4: Run Folder Index consumer regressions**

```bash
uv run --locked --extra dev pytest \
  tests/test_folder_index_policy.py tests/test_inbox_plan.py \
  tests/test_create_note.py tests/test_create_category.py \
  tests/test_process_inbox.py tests/test_detect_index.py \
  tests/test_audit_vault.py tests/test_vault_info.py -q
```

Expected: all selected tests pass with unchanged existing-consumer outputs.

- [ ] **Step 5: Commit pure index planning**

```bash
git add obsidian_kb_skill/scripts/folder_index_policy.py \
  obsidian_kb_skill/scripts/inbox_plan.py \
  tests/test_folder_index_policy.py tests/test_inbox_plan.py
git commit -m "refactor: plan inbox index updates without writes"
```

---


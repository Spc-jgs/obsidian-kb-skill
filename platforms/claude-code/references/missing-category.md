# Missing Category Exception (reference)

Load only after discovery and Vault governance show that a clear stable topic
has no governed category. Existing governed categories never load this file.

## Confirmation Contract

Propose one full Vault-relative category path and tell the user they may rename
it. In the same confirmation, record a separate answer for whether to update the
applicable `AGENTS.md` with the new route. Do not mutate before the final path and
route-persistence choice are confirmed.

## Create the Confirmed Category

Inspect the read-only plan, then apply the exact same path:

```bash
python <skill-root>/scripts/run_helper.py create-category <vault> \
  --folder "<parent>/<category>" --preflight-json
python <skill-root>/scripts/run_helper.py create-category <vault> \
  --folder "<parent>/<category>" --apply --confirmed --compact-json
```

The helper creates only the category and its governed index. Never infer and
create nested missing parents or silently repair an index. If route persistence
was approved, minimally edit `AGENTS.md`; otherwise call it a one-off category
and ask again next time. Perform other Vault-required structural maintenance,
including README updates when applicable, then resume ordinary `create-note`.

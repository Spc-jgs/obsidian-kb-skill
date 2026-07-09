# Optional Git Post-Processing (reference)

Loaded only when the user asks to version-control saved notes. The always-loaded skill body points here.

## Optional Git Post-Processing

Git is not a default part of note capture. Run it only when the user explicitly requests it or applicable Vault-local governance requires it.

### Pre-write Git synchronization

When Git is required, perform this before Create Step 1 or Update Step 1:

1. Inspect the worktree. If unrelated changes exist, stop and report them.
2. Fetch the tracked remote branch without modifying files.
3. If the worktree is clean and local is only behind, run `git merge --ff-only <remote>/<branch>`.
4. If local is already current or only ahead, continue.
5. If histories are diverged or `merge --ff-only` fails, stop and report. Do not create a local commit first and then auto-merge remote work.

### Post-write Git publication

1. Complete post-write validation first.
2. Inspect the worktree and stage only files created or changed by this invocation. Never include unrelated user changes.
3. Commit, then fetch the remote branch again and compare local and remote history.
4. **Stop on divergence or conflict.** Report the state instead of merging, rebasing, or choosing a conflict side automatically.
5. **Never auto-resolve INDEX conflicts.** In particular, never replace a Folder Index `folder-index-content` block with a manual note list to make a merge pass.
6. Push only when the remote is not ahead and histories are not diverged.

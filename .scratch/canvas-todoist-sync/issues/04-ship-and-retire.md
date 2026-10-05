# 04: Ship and retire

**What to build:** The sync runs itself on GitHub Actions every 3 hours, commits its state, and retires cleanly after the Sync End Date. The repo also contains everything I need to set it up, keep it running across terms, and Decommission it. See the spec's Workflow section and Further Notes in `.scratch/canvas-todoist-sync/spec.md`.

**Blocked by:** 02 (Sync rules), 03 (Resilient HTTP and error handling)

**Status:** done

- [x] After the Sync End Date the sync is Retired: no feed or Todoist calls, a "sync retired" log line, and exit 0 (engine test, written first).
- [x] The workflow:
  - runs every 3 hours and on manual dispatch
  - uses a concurrency group with `cancel-in-progress: false`
  - has `contents: write` and `actions: write` permissions
  - runs on Python 3.12
  - takes `CANVAS_CALENDAR_FEED_URL` and `TODOIST_TOKEN` from repo secrets
- [x] After the run, the workflow does `git pull --rebase` and commits `state.json` only if it changed, with the message `chore: sync state [skip ci]`.
- [x] Once Retired, the workflow disables itself with `gh workflow disable`.
- [x] `config.example.yaml` lists every setting with its default, and `.env.example` lists both secrets with placeholder values.
- [x] The README covers:
  - getting the Calendar Feed address (Canvas → Calendar → Calendar Feed) and treating it like a password
  - getting the Todoist token
  - finding course IDs
  - running locally with `--dry-run`
  - setting up the GitHub secrets
  - resetting state, and that tasks I deleted may reappear once afterwards
  - "Each new term"
  - the Decommission checklist: confirm the workflow is disabled, reset the Todoist token, delete the repo secrets, archive or delete the School Project, archive or delete the repo
- [x] A manual `--dry-run` against my real feed and Todoist succeeds, and its summary is pasted into this ticket under `## Comments`.

## Comments

**2026-10-05, manual `--dry-run` against the real Calendar Feed and Todoist** (with the committed `state.json`, default settings):

```
Dry run: created 0, updated 0, skipped 8, errors 0
```

Exit code 0; `state.json` unchanged. The 8 skipped are feed Assignments outside the Sync Window.

2026-10-05: First workflow run (37290924317) failed with `Calendar Feed fetch failed: InvalidURL`: the pasted repo secret wasn't the bare address. Resetting both secrets with `gh secret set -f .env` fixed it. Run 37294076484 on Python 3.12 succeeded: `created 0, updated 0, skipped 8, errors 0`, `state.json` unchanged. Afterwards bumped `actions/checkout` and `actions/setup-python` to v7 (Node 24).

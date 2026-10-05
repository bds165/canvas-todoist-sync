# 04: Ship and retire

**What to build:** The sync runs itself on GitHub Actions every 3 hours, commits its state, and retires cleanly after the Sync End Date. The repo also contains everything I need to set it up, keep it running across terms, and Decommission it. See the spec's Workflow and Lifecycle sections in `.scratch/canvas-todoist-sync/spec.md`.

**Blocked by:** 02 (Sync rules), 03 (Resilient HTTP and error handling)

**Status:** ready-for-agent

- [ ] After the Sync End Date the sync is Retired: no Canvas or Todoist calls, a "sync retired" log line, and exit 0 (engine test, written first).
- [ ] The workflow:
  - runs every 3 hours and on manual dispatch
  - uses a concurrency group with `cancel-in-progress: false`
  - has `contents: write` and `actions: write` permissions
  - runs on Python 3.12+
  - takes the three secrets from repo secrets
- [ ] After the run, the workflow does `git pull --rebase` and commits `state.json` only if it changed, with the message `chore: sync state [skip ci]`.
- [ ] Once Retired, the workflow disables itself with `gh workflow disable`.
- [ ] `config.example.yaml` lists every setting with its default, and `.env.example` lists the three secrets with placeholder values.
- [ ] The README covers:
  - getting both tokens, including setting the Canvas token to expire around 2027-08-31
  - finding course IDs
  - running locally with `--dry-run`
  - setting up the GitHub secrets
  - resetting state, and that tasks I deleted may reappear once afterwards
  - "Each new term"
  - the Decommission checklist: confirm the workflow is disabled, revoke the Canvas token, reset the Todoist token, delete the repo secrets, archive or delete the School Project, archive or delete the repo
- [ ] A manual `--dry-run` against real Canvas and Todoist succeeds, and its summary is pasted into this ticket under `## Comments`.

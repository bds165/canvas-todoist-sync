# 03: Resilient HTTP and error handling

**What to build:** The sync survives an unattended run:

- Transient failures and Todoist rate limits are retried.
- One bad Assignment doesn't sink the run.
- A free-plan limit produces a clear warning instead of a crash.
- Neither the feed address nor the Todoist token ever reaches the logs.
- The exit code only signals failure when the whole run failed, so that GitHub only emails me about real outages.

This is mostly the adapter seam (canned responses), plus engine tests for error isolation. See `.scratch/canvas-todoist-sync/spec.md`.

**Blocked by:** 01 (Tracer bullet)

**Status:** ready-for-agent

- [ ] One shared HTTP helper retries with backoff on 429 and 5xx, for both the feed fetch and Todoist.
- [ ] Todoist's `retry_after` is honoured when present.
- [ ] The Calendar Feed address (which works like a password) and the Todoist token never appear in log output or error messages, including messages from failed requests (adapter tests assert this).
- [ ] A Todoist plan-limit response (sections or active tasks) is mapped to a distinct plan-limit error. The engine logs it as a clear warning, counts it in `errors`, and continues. The next run retries naturally.
- [ ] A failure while syncing one Assignment is logged and skipped. The rest of the run continues and the state for unaffected items is saved.
- [ ] A feed that is malformed, or parses to something unexpected, fails the run clearly instead of marking every Assignment Missing from Canvas.
- [ ] The process exits non-zero only when the whole run failed: feed unreachable after retries, Todoist rejecting the token, or an unparseable feed.
- [ ] Tests, written first, cover each criterion: adapter tests with canned responses; engine tests with fakes for the plan-limit and isolation behaviour.

# 03: Resilient HTTP and error handling

**What to build:** The sync survives an unattended run against real APIs:

- Rate limits and transient failures are retried.
- One bad course or Assignment doesn't sink the run.
- A free-plan limit produces a clear warning instead of a crash.
- Tokens never reach the logs.
- The exit code only signals failure when the whole run failed, so that GitHub only emails me about real outages.

This is mostly the HTTP-adapter seam (canned responses), plus engine tests for error isolation. See `.scratch/canvas-todoist-sync/spec.md`.

**Blocked by:** 01 (Tracer bullet)

**Status:** ready-for-agent

- [ ] One shared HTTP helper retries with backoff on 429 and 5xx, for both Canvas and Todoist.
- [ ] Canvas throttling is detected both as 429 and as 403 with "Rate Limit Exceeded", and is retried.
- [ ] Todoist's `retry_after` is honoured when present.
- [ ] Authorization headers and tokens never appear in log output, including logged errors (an adapter test asserts this).
- [ ] A Todoist plan-limit response (sections or active tasks) is mapped to a distinct plan-limit error. The engine logs it as a clear warning, counts it in `errors`, and continues. The next run retries naturally.
- [ ] A failure while fetching one course, or while syncing one Assignment, is logged and skipped. The rest of the run continues and the state for unaffected items is saved.
- [ ] The process exits non-zero only when the whole run failed, for example bad credentials or Canvas or Todoist unreachable after retries.
- [ ] Tests, written first, cover each criterion: adapter tests with canned responses; engine tests with fakes for the plan-limit and isolation behaviour.

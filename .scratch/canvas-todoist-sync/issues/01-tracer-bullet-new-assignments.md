# 01: Tracer bullet: new Assignments become Synced Tasks

**What to build:** One complete path from Canvas to Todoist. I run the sync locally (first with `--dry-run`, then for real). Every new Assignment within the Sync Window becomes a Synced Task in the School Project, under its Course Section. `state.json` records what was created, and the run ends with a one-line summary.

This ticket establishes both test seams from the spec (`.scratch/canvas-todoist-sync/spec.md`):

- the sync-engine entry point, with an in-memory fake Canvas source and fake Todoist gateway
- the Canvas and Todoist HTTP adapters, tested against canned responses

Use plain `requests` and Todoist API v1 only. Use the per-course Assignments API (ADR 0001). Vocabulary follows `GLOSSARY.md`.

**Blocked by:** None (can start immediately)

**Status:** ready-for-agent

- [ ] Config loads from YAML with the spec's defaults (`School`, Lookahead 31, Lookback 5, Sync End Date 2027-08-01, undated off, dry run off). The three secrets come from environment variables, or from a local `.env` during development.
- [ ] In-scope courses are the current-term active enrollments, filtered by `course_allowlist` when it is non-empty.
- [ ] Assignments are fetched per course with the user's submission included, following `Link`-header pagination (adapter test).
- [ ] Canvas JSON is mapped to Assignment records: ID, course, name, Canvas Due Date (UTC or none), link, points, published, locked, and submitted/graded/excused (adapter test).
- [ ] A new Synced Task is created only for an Assignment that is published, not locked, and not Done (submitted, graded or excused), with a Canvas Due Date inside the Sync Window (Lookback through Lookahead). Undated Assignments are skipped unless the setting enables them.
- [ ] The School Project is found by name or created. A Course Section is found or created by override name, falling back to the course code.
- [ ] Task title is the Assignment name. The description contains the Canvas link and points possible. The due date is sent as a fixed UTC datetime (adapter test asserts the payload). No labels are added.
- [ ] `state.json` records, per course, the section ID and, per Assignment, the task ID, the last-synced Canvas Due Date and the status `open`. It contains no secrets.
- [ ] Dry run makes zero Todoist writes and logs what would be created.
- [ ] The run ends with the summary line `created N, updated N, closed N, skipped N, errors N`.
- [ ] Engine tests (written first, through the fakes) cover:
  - new Assignment → task created
  - Assignment inside the Lookback gets a task
  - excused or submitted Assignment gets no task
  - outside the Sync Window gets no task
  - dry run writes nothing

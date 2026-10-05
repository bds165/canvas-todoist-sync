# 01: Tracer bullet: Assignments in the Calendar Feed become Synced Tasks

**What to build:** One complete path from the Calendar Feed to Todoist. I run the sync locally (first with `--dry-run`, then for real). Every Assignment in my feed that falls inside the Sync Window becomes a Synced Task in the School Project, under its Course Section. `state.json` records what was created, and the run ends with a one-line summary.

This ticket establishes both test seams from the spec (`.scratch/canvas-todoist-sync/spec.md`):

- the sync-engine entry point, with an in-memory fake Canvas source and fake Todoist gateway
- the Calendar Feed and Todoist adapters, tested against made-up `.ics` fixtures and canned HTTP responses

Read Canvas only through the Calendar Feed (ADR 0002). Use plain `requests`, `icalendar`, and Todoist API v1 only. Vocabulary follows `GLOSSARY.md`. The code must run on Python 3.12.

**Blocked by:** None (can start immediately)

**Status:** ready-for-agent

- [ ] Config loads from YAML with the spec's defaults (`School`, Lookahead 31, Lookback 5, Sync End Date 2027-08-01, dry run off). The secrets `CANVAS_CALENDAR_FEED_URL` and `TODOIST_TOKEN` come from environment variables, or from a local `.env` during development.
- [ ] The Calendar Feed adapter (tested with made-up fixtures, never the real feed):
  - keeps only `event-assignment-<id>` events
  - takes the course ID from the event link's `include_contexts=course_<id>` and the course code from the trailing `[CODE]` tag in the title
  - strips that tag from the title
  - builds the link `<host>/courses/<course id>/assignments/<assignment id>`
  - parses timed events as UTC and `VALUE=DATE` events as date-only, including the duplicated `VALUE=DATE` parameter
  - handles folded and escaped lines
- [ ] A new Synced Task is created only for an Assignment whose course passes `course_allowlist` (when non-empty) and whose Canvas Due Date is inside the Sync Window (Lookback through Lookahead). Date-only due dates are compared as whole days.
- [ ] The School Project is found by name or created. A Course Section is found or created by override name, falling back to the course code.
- [ ] Task title is the Assignment title without the course tag. The description contains the Assignment link. No labels are added.
- [ ] A timed due date is sent as a fixed UTC datetime, and a date-only due date as a plain date (adapter test asserts both payloads).
- [ ] `state.json` records, per course, the section ID and, per Assignment, the task ID, the last-synced Canvas Due Date (timed or date-only, exactly as the feed gave it) and the status `open`. It contains no secrets and no feed address.
- [ ] Dry run makes zero Todoist writes and logs what would be created.
- [ ] The run ends with the summary line `created N, updated N, skipped N, errors N`.
- [ ] Engine tests (written first, through the fakes) cover:
  - new Assignment → task
  - timed and date-only due dates
  - inside the Lookback → task
  - outside the Sync Window → no task
  - allowlist respected
  - dry run writes nothing

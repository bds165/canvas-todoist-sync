# 02: Sync rules: keep Synced Tasks current and respect my changes

**What to build:** Every rule in the spec's "Sync rules" section beyond creation, all tested through the sync-engine seam with the in-memory fakes. After this ticket:

- Synced Tasks follow Canvas Due Date changes.
- Anything I do in Todoist is respected.
- Assignments that disappear from the feed, and a missing `state.json`, are handled safely.

The sync never closes tasks; I finish them myself. See `.scratch/canvas-todoist-sync/spec.md`, `GLOSSARY.md` and ADR 0002.

**Blocked by:** 01 (Tracer bullet)

**Status:** done

**Canvas Due Date changes**
- [x] Any change from the last-synced Canvas Due Date updates the task's due date. That includes a time-only change, a switch between date-only and timed, and a new date outside the Sync Window.
- [x] Every due date change appends "Due date updated from Canvas on <date>" to the task's *current* description, keeping my edits.
- [x] A Reschedule I made stands while the Canvas Due Date is unchanged, and is overwritten when it changes.
- [x] A second run with no feed changes makes zero Todoist writes.

**Dismissed and moved tasks**
- [x] All active tasks across all projects are fetched once per run. An `open` entry whose task is absent becomes `dismissed`, and its Assignment is never recreated or touched again. This applies whether I completed the task or deleted it.
- [x] A task I moved to another section or project is not Dismissed.
- [x] My renames, priorities, labels and description edits are never overwritten.

**Course Section resilience**
- [x] The stored section ID is used even if I renamed the section.
- [x] If the section was deleted, it is recreated by name only when a new Synced Task needs it. Existing tasks are never moved.

**Missing from Canvas**
- [x] An `open` entry whose Assignment is absent from the feed becomes `missing_from_canvas` (its previous status is kept). This is logged once, at that change. Its task is left untouched, and its due date is never cleared.
- [x] When the Assignment reappears, its previous status is restored and due date changes apply as normal.

**Rebuilding missing state**
- [x] With no `state.json`, active School Project tasks whose description contains a matching Assignment link are adopted instead of being duplicated.
- [x] With no `state.json`, School Project tasks completed in the last 3 months with a matching link become `dismissed`. This needs the completed-tasks gateway operation and its adapter call.

**Tests**
- [x] Engine tests, written first, cover every criterion above.

## Comments

2026-10-05: Implemented, with engine tests through the fakes and adapter tests for the three new Todoist calls (`list_active_tasks`, `list_completed_tasks`, `update_task`). 58 tests pass; mypy strict is clean. Before closing, still to do:

- A real run with a Canvas Due Date change, to confirm Todoist v1 drops the time when a timed task is updated with only `due_date` (date-only switch). The adapter test checks the payload only.
- Known limits, left as they are:
  - "Last 3 months" of completed tasks is 89 days, so the query stays inside Todoist's 3-month range limit in every month.
  - A rebuild adopts only Assignments in the feed at that moment. A Synced Task whose Assignment is Missing from Canvas during a reset can be duplicated if the Assignment later returns inside the Sync Window.

2026-10-05: Checked against the real feed and Todoist.

- Dry run: `created 0, updated 0, skipped 8, errors 0`. It found 4 tasks I had completed: 509058, 509063, 509066 and 519449.
- Date-only switch: In-class Assessment 4 (512221) had a time set in Todoist, and its stored Canvas Due Date was faked as timed. The real run gave `created 0, updated 1, skipped 8, errors 0`. Reading the task back afterwards: due `2026-10-15` with no time, and the note was appended after the Canvas link. So Todoist v1 does drop the time when it is sent only `due_date`.
- `state.json` committed with the 4 entries now `dismissed`.

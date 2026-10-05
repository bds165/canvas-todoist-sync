# 02: Sync rules: keep Synced Tasks current and respect my changes

**What to build:** Every rule in the spec's "Sync rules" section beyond creation, all tested through the sync-engine seam with the in-memory fakes. After this ticket:

- Synced Tasks follow Canvas Due Date changes.
- Anything I do in Todoist is respected.
- Assignments that disappear from the feed, and a missing `state.json`, are handled safely.

The sync never closes tasks; I finish them myself. See `.scratch/canvas-todoist-sync/spec.md`, `GLOSSARY.md` and ADR 0002.

**Blocked by:** 01 (Tracer bullet)

**Status:** ready-for-agent

**Canvas Due Date changes**
- [ ] Any change from the last-synced Canvas Due Date updates the task's due date. That includes a time-only change, a switch between date-only and timed, and a new date outside the Sync Window.
- [ ] Every due date change appends "Due date updated from Canvas on <date>" to the task's *current* description, keeping my edits.
- [ ] A Reschedule I made stands while the Canvas Due Date is unchanged, and is overwritten when it changes.
- [ ] A second run with no feed changes makes zero Todoist writes.

**Dismissed and moved tasks**
- [ ] All active tasks across all projects are fetched once per run. An `open` entry whose task is absent becomes `dismissed`, and its Assignment is never recreated or touched again. This applies whether I completed the task or deleted it.
- [ ] A task I moved to another section or project is not Dismissed.
- [ ] My renames, priorities, labels and description edits are never overwritten.

**Course Section resilience**
- [ ] The stored section ID is used even if I renamed the section.
- [ ] If the section was deleted, it is recreated by name only when a new Synced Task needs it. Existing tasks are never moved.

**Missing from Canvas**
- [ ] An `open` entry whose Assignment is absent from the feed becomes `missing_from_canvas` (its previous status is kept). This is logged once, at that change. Its task is left untouched, and its due date is never cleared.
- [ ] When the Assignment reappears, its previous status is restored and due date changes apply as normal.

**Rebuilding missing state**
- [ ] With no `state.json`, active School Project tasks whose description contains a matching Assignment link are adopted instead of being duplicated.
- [ ] With no `state.json`, School Project tasks completed in the last 3 months with a matching link become `dismissed`. This needs the completed-tasks gateway operation and its adapter call.

**Tests**
- [ ] Engine tests, written first, cover every criterion above.

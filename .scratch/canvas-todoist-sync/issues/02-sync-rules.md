# 02: Sync rules: keep Synced Tasks current and respect my changes

**What to build:** Every rule in the spec's "Sync rules" section beyond creation, all tested through the sync-engine seam with the in-memory fakes. After this ticket:

- Synced Tasks follow Canvas: they close when the Assignment is Done, and due dates follow the Canvas Due Date.
- Anything I do in Todoist is respected.
- Disappearing Assignments and a missing `state.json` are handled safely.

See `.scratch/canvas-todoist-sync/spec.md` and `GLOSSARY.md`.

If this ticket runs out of context, split it after the "Dismissed and moved tasks" criteria. The remaining criteria become a follow-up ticket.

**Blocked by:** 01 (Tracer bullet)

**Status:** ready-for-agent

**Close once**
- [ ] When an `open` entry's Assignment becomes Done (submitted, graded or excused), its task is closed and its status set to `closed_by_sync`.
- [ ] A task I reopen after it was Closed by Sync is never closed again, and the sync never reopens any task.

**Canvas Due Date changes**
- [ ] Any change from the last-synced Canvas Due Date updates the task's due date. That includes a time-only change and a new date outside the Sync Window.
- [ ] A removed Canvas Due Date clears the task's due date.
- [ ] Every due date change appends "Due date updated from Canvas on <date>" to the task's *current* description, keeping my edits.
- [ ] A Reschedule I made stands while the Canvas Due Date is unchanged.
- [ ] A second run with no Canvas changes makes zero Todoist writes.

**Dismissed and moved tasks**
- [ ] All active tasks across all projects are fetched once per run. An `open` entry whose task is absent becomes `dismissed`, and its Assignment is never recreated or touched again.
- [ ] A task I moved to another section or project is not Dismissed.
- [ ] My renames, priorities, labels and description edits are never overwritten.

**Course Section resilience**
- [ ] The stored section ID is used even if I renamed the section.
- [ ] If the section was deleted, it is recreated by name only when a new Synced Task needs it. Existing tasks are never moved.

**Missing from Canvas**
- [ ] An entry whose Assignment no longer appears becomes `missing_from_canvas` (its previous status is kept). This is logged once, at that change, and its task is left untouched.
- [ ] When the Assignment reappears, its previous status is restored and the normal rules apply.

**Rebuilding missing state**
- [ ] With no `state.json`, active School Project tasks whose description contains a matching Canvas link are adopted instead of being duplicated.
- [ ] With no `state.json`, School Project tasks completed in the last 3 months with a matching link become `dismissed`. This needs the completed-tasks gateway operation and its adapter call.

**Tests**
- [ ] Engine tests, written first, cover every criterion above. That includes these spec cases: user-completed task not recreated, user-edited title preserved, user-Rescheduled task not overwritten, time-only change overwrites a Reschedule, first run with no state file.

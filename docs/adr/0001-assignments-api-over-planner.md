---
status: superseded by ADR-0002
---

# Use the per-course Assignments API, not the Planner API

We fetch Assignments course by course from `GET /api/v1/courses/:id/assignments?include[]=submission` and do not use the Planner API (`/api/v1/planner/items`). The Assignments API reports `published` and `locked_for_user`, which the skip rules depend on, and every result has a stable assignment ID that serves as the key in the state file. The Planner API returns everything in one call and also covers ungraded to-do items. However, its docs don't say whether locked or unpublished items are excluded or which fields `plannable` includes, and ungraded items have no submission, so the sync could never decide they are Done.

## Consequences

- Quizzes and graded discussions are still synced, because Canvas stores them as assignments underneath.
- Ungraded to-do items and planner notes are deliberately not synced.
- Switching to the Planner API later would change the state file's key, from assignment ID to something like `plannable_type` plus `plannable_id`, and would need a state migration.

# Canvas → Todoist Sync

A one-way copy of Canvas coursework into Todoist. Canvas is the source of truth for what is due and when. Todoist is where the student plans the work and checks it off.

## Canvas side

**Assignment**:
A gradable Canvas item that has a Canvas assignment ID. This includes quizzes and graded discussions. Ungraded to-do items and planner notes are not Assignments.
_Avoid_: planner item, to-do, homework

**Done**:
The state of an Assignment whose submission is submitted, graded or excused.
_Avoid_: complete, finished (those words describe Todoist tasks)

**Canvas Due Date**:
The due moment Canvas reports for an Assignment.
_Avoid_: deadline

## Todoist side

**School Project**:
The single Todoist project that every Synced Task is created in.

**Course Section**:
A Todoist section inside the School Project. Each one represents one Canvas course.

**Synced Task**:
A Todoist task the sync created for one Assignment.
_Avoid_: todo, item, card

**Reschedule**:
A change the user makes to a Synced Task's due date in Todoist.

## Lifecycle

**Sync Window**:
The time range in which an Assignment's Canvas Due Date must fall for a new Synced Task to be created. It runs from the Lookback back to the Lookahead ahead.
_Avoid_: range, horizon

**Lookahead**:
How far into the future the Sync Window reaches.

**Lookback**:
How far into the past the Sync Window reaches, so that recently overdue, not-yet-Done Assignments still get a Synced Task.

**Closed by Sync**:
A Synced Task that the sync completed because its Assignment became Done. The sync closes a task at most once.

**Dismissed**:
A Synced Task that the user completed or deleted in Todoist. The sync treats both the same way and never touches the task again.
_Avoid_: user-completed, user-deleted

**Missing from Canvas**:
The status of an Assignment that has a Synced Task but no longer appears in Canvas, whether it was deleted or unpublished, or its course left scope.

## Project lifecycle

**Sync End Date**:
The last day the sync does any work. After it, the sync is Retired.

**Retired**:
The state after the Sync End Date, in which runs do nothing and the scheduled workflow switches itself off.

**Decommission**:
The manual teardown after retirement: revoking tokens, removing secrets, and archiving the School Project and the repo.
_Avoid_: shutdown, uninstall

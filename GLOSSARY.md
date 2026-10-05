# Canvas → Todoist Sync

A one-way copy of Canvas coursework into Todoist. Canvas is the source of truth for what is due and when. Todoist is where the student plans the work and checks it off.

## Canvas side

**Calendar Feed**:
The student's private Canvas calendar subscription address. It lists their dated Assignments and calendar events across all courses, and it is the sync's only source of Canvas data.
_Avoid_: ICS link, iCal URL, calendar export, API

**Assignment**:
A gradable Canvas item with a Canvas assignment ID, as it appears in the Calendar Feed. This includes quizzes and graded discussions. Ordinary calendar events (lectures, office hours) are not Assignments.
_Avoid_: event, planner item, to-do, homework

**Canvas Due Date**:
The due moment the Calendar Feed reports for an Assignment. It is either a date and time, or a date only (an all-day Assignment).
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
How far into the past the Sync Window reaches, so that recently overdue Assignments still get a Synced Task.

**Dismissed**:
A Synced Task that the user completed or deleted in Todoist. The sync treats both the same way and never touches the task again. The user, not the sync, finishes Synced Tasks.
_Avoid_: user-completed, user-deleted, done

**Missing from Canvas**:
The status of an Assignment that has a Synced Task but no longer appears in the Calendar Feed. It may have been deleted or unpublished, lost its due date, or moved outside the feed's range; the sync cannot tell which.

## Project lifecycle

**Sync End Date**:
The last day the sync does any work. After it, the sync is Retired.

**Retired**:
The state after the Sync End Date, in which runs do nothing and the scheduled workflow switches itself off.

**Decommission**:
The manual teardown after retirement: resetting the Todoist token, removing the secrets (including the Calendar Feed address), and archiving the School Project and the repo.
_Avoid_: shutdown, uninstall

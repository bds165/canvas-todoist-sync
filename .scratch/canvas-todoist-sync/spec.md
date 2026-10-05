# Spec: Canvas → Todoist Sync

Status: ready-for-agent

## Problem Statement

My coursework lives in Canvas, but I plan and check off my work in Todoist on macOS, iOS and Windows. Copying every Assignment by hand is tedious and error-prone. Due dates change, new Assignments appear mid-week, and I forget to tick things off after submitting. I want Todoist to always reflect what Canvas says is due without my laptop being on. The sync must never trample the edits I make in Todoist, and it must not fill my free-plan account (5 projects, 20 sections, 300 active tasks) with clutter. I finish school in mid-2027, so the whole thing must retire and be easy to take down once I'm done.

## Solution

A small Python script runs every 3 hours on GitHub Actions in a private repo and does a one-way sync from Canvas to Todoist:

- Every Assignment (including quizzes and graded discussions) due within the **Sync Window** (5 days back to 31 days ahead) becomes a **Synced Task** in a single **School Project**, filed under one **Course Section** per course.
- When the **Canvas Due Date** changes, the sync updates the task's due date and notes the change on the task.
- When an Assignment becomes **Done** (submitted, graded or excused), the sync closes its task once.
- Anything I change myself in Todoist is respected. Tasks I complete or delete (**Dismissed**) are never recreated. Renames, priorities, labels and moves are never touched. My **Reschedules** stand until Canvas changes the date again.
- A `state.json` file committed back to the repo after each run remembers what has been synced.
- After the **Sync End Date** (2027-08-01) the sync is **Retired**: runs do nothing and the workflow switches itself off. A documented **Decommission** checklist finishes the teardown.

## User Stories

### Getting Assignments into Todoist

1. As a student, I want each Assignment from my active courses copied into Todoist as a Synced Task, so that I see all my coursework in the tool where I plan my day.
2. As a student, I want quizzes and graded discussions included, because they are Assignments in Canvas too, so that no graded work is missed.
3. As a student, I want ungraded to-do items and planner notes left out, so that only gradable work reaches Todoist.
4. As a student, I want only courses from the current term synced, so that old unarchived courses don't flood my list.
5. As a student, I want to optionally restrict the sync to a list of course IDs, so that I can exclude a course I don't need to track.
6. As a student, I want new terms' courses picked up automatically when I haven't set a course list, so that I don't have to reconfigure every term.
7. As a student, I want unpublished and locked Assignments skipped, so that I only see work I can actually do.
8. As a student, I want Assignments without a due date skipped by default, with a setting to include them, so that undated busywork doesn't clutter my list unless I choose otherwise.
9. As a student, I want new Synced Tasks created only for Assignments due within the next 31 days, so that my free-plan task quota isn't eaten by far-future work.
10. As a student, I want not-yet-Done Assignments that went overdue within the last 5 days to still get a Synced Task, so that recent late work isn't silently missed.
11. As a student, I want Assignments that are already Done never to get a new Synced Task, so that I'm not asked to do finished work.
12. As a student, I want an Assignment that enters the Sync Window later (e.g. a due date gets added, or time passes) to get its Synced Task then, so that nothing falls through the cracks.
13. As a student, I want both the Lookahead and Lookback configurable, so that I can tune the Sync Window if my workload changes.

### How Synced Tasks look

14. As a student, I want all Synced Tasks in one School Project (default name `School`, created if missing), so that I stay under the free plan's 5-project limit.
15. As a student, I want one Course Section per course, named from my short override or else the Canvas course code, so that tasks are grouped by course.
16. As a student, I want the task title to be the Assignment name, so that I recognise it immediately.
17. As a student, I want the task description to contain the Canvas link and points possible, so that I can jump straight to the Assignment and judge its weight.
18. As a student, I want the due date stored as a fixed moment from Canvas's UTC time, so that it shows the correct local time on all my devices, even when I travel.
19. As a student, I want no labels added to Synced Tasks, so that my label setup stays mine.

### Keeping tasks current

20. As a student, I want a Synced Task's due date updated whenever the Canvas Due Date changes, so that I always see the real deadline.
21. As a student, I want a time-only change (e.g. 11:59pm to 11:00pm) to count as a change, so that I hear about every deadline move.
22. As a student, I want a Canvas Due Date moved outside the Sync Window still applied to an existing Synced Task, so that the task never shows a stale date.
23. As a student, I want a removed Canvas Due Date to clear the task's due date, so that the task doesn't show a deadline that no longer exists.
24. As a student, I want a note added to the description whenever the sync changes a due date ("Due date updated from Canvas on <date>"), so that I understand why my Reschedule disappeared.
25. As a student, I want a Synced Task closed when its Assignment becomes Done (submitted, graded or excused), so that I don't have to tick it off twice.
26. As a student, I want on-paper Assignments to close once they're graded, so that offline work eventually resolves too.
27. As a student, I want the sync to close a task at most once, so that if I reopen it (e.g. to revise) it stays open.
28. As a student, I want the sync never to reopen a task, even if a teacher allows a resubmission, so that my list doesn't change under me.

### Respecting my changes

29. As a student, I want a task I complete myself never recreated, so that finished work stays finished.
30. As a student, I want a task I delete never recreated, so that I can drop items I don't care about.
31. As a student, I want my renames, priorities, labels and descriptions kept, so that I can personalise tasks freely.
32. As a student, I want to move a Synced Task to another section or project without it being treated as deleted, so that I can organise my way.
33. As a student, I want my Reschedule respected until Canvas changes the date again, so that I can plan earlier than the deadline.
34. As a student, I want a Course Section I renamed to keep being used, so that my naming sticks.
35. As a student, I want a Course Section I deleted recreated only when that course needs a new Synced Task, so that I'm not fighting the sync over empty sections.

### When Canvas changes underneath

36. As a student, I want an Assignment that disappears from Canvas (deleted, unpublished, or its course left scope) to leave its Synced Task untouched, so that I don't lose anything I was tracking.
37. As a student, I want that disappearance logged once, not every run, so that the logs stay readable.
38. As a student, I want an Assignment that reappears to resume normal syncing, so that a temporary unpublish doesn't break anything.

### State and recovery

39. As a student, I want the sync to remember what it has created in a `state.json` committed after each run, so that it works without a database.
40. As a student, I want a run with missing state to adopt existing Synced Tasks by their Canvas link, so that a reset doesn't duplicate everything.
41. As a student, I want a run with missing state to treat tasks I completed in the last 3 months as Dismissed, so that a reset doesn't bring back finished work.
42. As a student, I want the README to explain that tasks I deleted can't be recovered after a reset and may reappear once, so that I'm not surprised.
43. As a student, I want state to contain no secrets, so that the repo is safe to keep.

### Operating it

44. As a student, I want the sync to run every 3 hours on GitHub Actions and on demand, so that it works when my laptop is off.
45. As a student, I want overlapping runs queued instead of racing, so that a manual run never creates duplicates or a failed state commit.
46. As a student, I want a dry-run mode that logs what would change without writing to Todoist, so that I can check config safely.
47. As a student, I want each run to end with a one-line summary (created, updated, closed, skipped, errors), so that I can see at a glance what happened.
48. As a student, I want one failing course or Assignment logged and skipped rather than aborting the run, so that one problem doesn't block everything.
49. As a student, I want the run to exit non-zero only when the whole run fails, so that GitHub only emails me about real outages.
50. As a student, I want clear warnings when Todoist rejects a create because of a free-plan limit, so that I know to clean up or shorten the Lookahead.
51. As a student, I want rate limits respected with retry and backoff, so that the sync doesn't get my tokens throttled.
52. As a student, I want tokens never printed or logged, so that the Actions logs are safe.
53. As a student, I want a second run with no Canvas changes to make zero Todoist writes, so that the sync is predictable and cheap.
54. As a student, I want a typical run to finish in under a minute, so that it stays within free Actions minutes.

### Lifecycle

55. As a student, I want a configured Sync End Date (2027-08-01) after which runs do nothing and exit successfully, so that losing Canvas access after graduation doesn't trigger failure emails.
56. As a student, I want the workflow to disable itself after the Sync End Date, so that I don't have to remember to switch it off.
57. As a student, I want the README to tell me to set the Canvas token to expire around 2027-08-31, so that access dies even if everything else is forgotten.
58. As a student, I want an "Each new term" section in the README, so that term changes take two minutes.
59. As a student, I want a Decommission checklist in the README, so that taking the project down is quick and complete.
60. As a future reader of the repo, I want the glossary and ADRs kept current, so that the reasons behind surprising choices are on record.

## Implementation Decisions

### Modules

- **Sync engine**: the deep module holding all the behaviour. A single entry point takes a Canvas source, a Todoist gateway, the prior state (possibly absent), the config and the current time, and returns the new state plus a run summary. It owns:
  - the Sync Window
  - Done detection
  - Dismissed detection
  - due date change detection, including the description note
  - Missing from Canvas tracking
  - Course Section resolution
  - rebuilding missing state
  - the Sync End Date guard
  - per-item error isolation
  - honouring dry run (no Todoist writes)
- **Canvas source**, a small interface with two operations:
  - list in-scope courses: current-term active enrollments, filtered by the allowlist when one is set
  - list a course's Assignments as domain records: assignment ID, course ID, name, Canvas Due Date (UTC or none), link, points possible, published, locked for user, and submission state (submitted, graded or excused)
- **Canvas HTTP adapter**: implements the Canvas source using the per-course Assignments endpoint with the user's submission included (ADR 0001). It follows `Link`-header pagination.
- **Todoist gateway**, a small interface:
  - list all active tasks across all projects
  - list completed tasks in a project since a given time (maximum 3 months)
  - find or create the project by name
  - list and create sections
  - create a task
  - update a task's due date and description
  - close a task
  - raise a distinct "plan limit reached" error
- **Todoist HTTP adapter**: implements the gateway against Todoist API v1 (`/api/v1/`) with plain `requests`. IDs are opaque strings. Due dates are sent as fixed-timezone UTC datetimes.
- **Shared HTTP helper**: retries with backoff on 429 and 5xx. It also covers Canvas throttling (429, or 403 with "Rate Limit Exceeded") and honours Todoist's `retry_after`. Authorization headers are never logged.
- **Config loader**: reads the non-secret YAML config and the three secret environment variables. Applies the defaults listed below.
- **State store**: loads and saves `state.json`, and treats a missing file as missing state.
- **Entry point / CLI**:
  - wires the adapters, config and state together, and accepts a `--dry-run` flag
  - prints the summary
  - sets the exit code: non-zero only when the whole run failed
  - reports when the sync is Retired

### Config (non-secret)

| Setting | Default |
|---|---|
| `todoist_project_name` | `School` |
| `course_allowlist` | empty, meaning all active current-term enrollments |
| `course_name_overrides` | empty map from course ID to short name |
| `sync_assignments_without_due_date` | `false` |
| `lookahead_days` | `31` |
| `lookback_days` | `5` |
| `sync_end_date` | `2027-08-01` |
| `dry_run` | `false` |

Secrets: `CANVAS_BASE_URL`, `CANVAS_TOKEN`, `TODOIST_TOKEN`.

### State shape

- **Per course:** the Todoist section ID.
- **Per Canvas assignment ID:**
  - Todoist task ID
  - last-synced Canvas Due Date (or none)
  - status: one of `open`, `closed_by_sync`, `dismissed`, `missing_from_canvas`
  - previous status, while it is `missing_from_canvas`

### Sync rules

1. **Retirement:** if today is after the Sync End Date, return immediately with no Canvas or Todoist calls.
2. **Dismissed detection:**
   - Fetch all active Todoist tasks once.
   - Any `open` state entry whose task is not in that list becomes `dismissed`.
   - Completed and deleted tasks are not told apart.
   - Membership is checked across all projects, so a moved task is not Dismissed.
3. **Missing state:**
   - Adopt active tasks in the School Project whose description contains a matching Canvas link.
   - Mark School Project tasks completed in the last 3 months with a matching link as `dismissed`.
4. **New Assignment** (no state entry): create a Synced Task only if all of these hold:
   - it is published and not locked
   - it is not Done
   - it has a Canvas Due Date inside the Sync Window, or is undated and undated Assignments are enabled
5. **Existing `open` entry:**
   - If the Canvas Due Date differs from the last-synced value (including time-only changes, moves outside the Sync Window, and removal), update the task's due date, or clear it on removal. Append the "Due date updated from Canvas on <date>" note to the current description. Record the new value.
   - If the Assignment is Done, close the task and set `closed_by_sync`.
6. **`closed_by_sync` and `dismissed`:** never touched again, never reopened, never re-closed.
7. **Missing from Canvas:**
   - An entry whose Assignment no longer appears becomes `missing_from_canvas`, keeping its previous status. Log it once, at that transition.
   - On reappearance, restore the previous status and apply the normal rules.
8. **Course Section:**
   - Use the stored section ID if it still exists, even if I renamed it.
   - If it doesn't exist, create the section by name, but only when a new Synced Task needs it.
   - Existing tasks are never moved.
9. **Free-plan limit:** a plan-limit error on create is logged as a warning, counted as an error in the summary, and the run continues. It is retried naturally on the next run.
10. **Idempotence:** a run with no Canvas changes makes zero Todoist writes.

### Workflow

- Scheduled every 3 hours, plus `workflow_dispatch`.
- `concurrency` group with `cancel-in-progress: false`.
- Permissions: `contents: write` and `actions: write`.
- Steps:
  1. set up Python 3.12+
  2. install dependencies
  3. run the sync
  4. `git pull --rebase`, then commit `state.json` only if it changed, as `chore: sync state [skip ci]`
- After the Sync End Date, a step runs `gh workflow disable` on itself.

### Dependencies

`requests`, a YAML parser, and the standard library. `pytest` for development. No Todoist SDK.

## Testing Decisions

- **Good tests check behaviour you can observe from outside.** Assert on what ends up in Todoist (the fake's tasks, sections and recorded writes), on the returned state and on the summary. Never assert on internal helpers or call order. Write tests first, one red-green slice at a time (TDD).
- **Seam 1: sync engine (primary).** All behaviour is tested through the single sync-run entry point with in-memory fakes:
  - The **fake Canvas source** serves configurable courses and Assignments.
  - The **fake Todoist gateway** keeps tasks and sections in memory and records every write.
  - Fakes can simulate a Reschedule, a Dismissed task, a reopened task, a deleted section, a moved task, and a plan-limit error.
  - Time is injected.
- Required cases for seam 1:
  1. new Assignment → Synced Task created
  2. Canvas Due Date change → task updated, with note
  3. submission → close
  4. user-completed task not recreated
  5. user-edited title preserved
  6. user-Rescheduled task not overwritten when Canvas is unchanged
  7. first run with no state file (adopt by link, and completed tasks become Dismissed)
  8. Assignment inside the Lookback gets a task
  9. excused counts as Done
  10. reopened task not closed again
  11. time-only Canvas Due Date change overwrites a Reschedule
  12. removed Canvas Due Date clears the task's date
  13. Missing from Canvas logged once and its task left alone, then resumes on reappearance
  14. plan-limit error logged and the run continues
  15. second run with no changes makes zero writes
  16. no work after the Sync End Date
  17. plus dry run makes no writes, and a moved task is not Dismissed
- **Seam 2: HTTP adapters (secondary, small).** Test the Canvas and Todoist adapters against canned HTTP responses, using a stubbed transport or a recorded-response library. Cover:
  - `Link`-header pagination
  - retry and backoff on 429/5xx and on Canvas's 403 "Rate Limit Exceeded"
  - honouring `retry_after`
  - mapping Canvas JSON to Assignment records, including submission states
  - the Todoist due date payload as fixed UTC
  - plan-limit responses mapped to the distinct error
  - tokens never appearing in logs
- **Not tested automatically:** the workflow YAML and the CLI wiring. They are checked by a manual `--dry-run` run, as in the "Each new term" procedure.
- **Prior art:** none. This is a new repo.

## Out of Scope

- Two-way sync (Todoist changes affecting Canvas).
- Announcements, grades, calendar events, ungraded to-do items, and planner notes. The Planner API is deliberately not used (ADR 0001).
- Distinguishing completed from deleted tasks.
- Re-closing or reopening tasks after the sync's single close.
- Automated cleanup of Todoist data at Decommission.
- OneNote integration (possible phase 2: a page per Assignment via Microsoft Graph, linked in the task). Keep adapters modular so a new output can be added later.

## Further Notes

- Vocabulary follows `GLOSSARY.md`. "Done" is the Canvas-side state; "complete/close" are Todoist-side actions.
- Todoist REST v2 and Sync v9 were shut down in February 2026. Use only API v1.
- Free-plan limits (20 sections, 300 active tasks) are per account and include personal tasks.
- The README must cover:
  - getting both tokens, including the Canvas token expiry around 2027-08-31
  - finding course IDs
  - running locally with `--dry-run`
  - setting up GitHub secrets
  - resetting state and what a reset can't recover
  - "Each new term"
  - the Decommission checklist:
    1. confirm the workflow is disabled
    2. revoke the Canvas token
    3. reset the Todoist token
    4. delete the repo secrets
    5. archive or delete the School Project
    6. archive or delete the repo
- This spec replaces the draft `canvas-todoist-sync.md` at the repo root.

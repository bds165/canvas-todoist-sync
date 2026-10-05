# Spec: Canvas → Todoist Sync

Status: ready-for-agent

## Problem Statement

My coursework at the University of Auckland lives in Canvas, but I plan and check off my work in Todoist on macOS, iOS and Windows. Copying every Assignment by hand is tedious and error-prone: due dates change, and new Assignments appear mid-week. I want Todoist to always reflect what Canvas says is due, without my laptop being on.

Constraints:

- My school has disabled personal Canvas access tokens. Even an approved token would expire every 30 days, so the Canvas API is not an option.
- The sync must never trample the edits I make in Todoist.
- It must not fill my free-plan account (5 projects, 20 sections, 300 active tasks) with clutter.
- I finish school in mid-2027, so the sync must retire and be easy to take down once I'm done.

## Solution

A small Python script runs every 3 hours on GitHub Actions in a private repo. It reads my Canvas **Calendar Feed**, the private iCal address Canvas gives every student, which needs no token. It then does a one-way sync into Todoist:

- Every Assignment (including quizzes and tests) due within the **Sync Window** (5 days back to 31 days ahead) becomes a **Synced Task** in a single **School Project**, filed under one **Course Section** per course.
- When the **Canvas Due Date** changes, the sync updates the task's due date and notes the change on the task.
- I finish Synced Tasks myself; the feed has no submission status, so the sync never closes them.
- Anything I change in Todoist is respected:
  - Tasks I complete or delete (**Dismissed**) are never recreated.
  - Renames, priorities, labels and moves are never touched.
  - My **Reschedules** stand until Canvas changes the date again.
- A `state.json` file committed back to the repo after each run remembers what has been synced.
- After the **Sync End Date** (2027-08-01) the sync is **Retired**: runs do nothing and the workflow switches itself off. A documented **Decommission** checklist finishes the teardown.

## User Stories

### Getting Assignments into Todoist

1. As a student, I want each Assignment in my Calendar Feed copied into Todoist as a Synced Task, so that I see all my coursework in the tool where I plan my day.
2. As a student, I want quizzes and tests included, because they appear as Assignments in the feed, so that no graded work is missed.
3. As a student, I want ordinary calendar events (lectures, office hours) left out, so that only Assignments reach Todoist.
4. As a student, I want the sync to read Canvas through the official Calendar Feed rather than a token, so that I stay within my university's rules.
5. As a student, I want to optionally restrict the sync to a list of course IDs, so that I can exclude a course I don't need to track.
6. As a student, I want new terms' courses picked up automatically when I haven't set a course list, so that I don't have to reconfigure every term.
7. As a student, I want new Synced Tasks created only for Assignments due within the next 31 days, so that my free-plan task quota isn't eaten by far-future work.
8. As a student, I want Assignments that became overdue within the last 5 days to still get a Synced Task, so that recent late additions aren't silently missed.
9. As a student, I accept that the first run creates tasks for the last 5 days' Assignments that I may already have submitted, and I'll tick those off once.
10. As a student, I want an Assignment that enters the Sync Window later (because time passes or its date moves closer) to get its Synced Task then, so that nothing falls through the cracks.
11. As a student, I want both the Lookahead and Lookback configurable, so that I can tune the Sync Window if my workload changes.

### How Synced Tasks look

12. As a student, I want all Synced Tasks in one School Project (default name `School`, created if missing), so that I stay under the free plan's 5-project limit.
13. As a student, I want one Course Section per course, named from my short override or else the course code from the feed (e.g. `COMPSCI 101`), so that tasks are grouped by course.
14. As a student, I want the task title to be the Assignment's title, without the trailing course tag, because the Course Section already shows the course, so that titles stay short.
15. As a student, I want the task description to contain a direct link to the Assignment in Canvas (not the calendar page), so that one tap opens it.
16. As a student, I want an Assignment due at a specific time to get that exact moment as a fixed due time, so that it shows correctly in local time on all my devices.
17. As a student, I want an Assignment that the feed gives only a date for to get a date-only due date, so that Todoist shows exactly what Canvas said and no invented time.
18. As a student, I want no labels added to Synced Tasks, so that my label setup stays mine.

### Keeping tasks current

19. As a student, I want a Synced Task's due date updated whenever the Canvas Due Date changes, so that I always see the real deadline.
20. As a student, I want a time-only change, or a switch between date-only and timed, to count as a change, so that I hear about every deadline move.
21. As a student, I want a Canvas Due Date moved outside the Sync Window still applied to an existing Synced Task, as long as it is still in the feed, so that the task never shows a stale date.
22. As a student, I want a note added to the description whenever the sync changes a due date ("Due date updated from Canvas on <date>"), so that I understand why my Reschedule disappeared.

### Respecting my changes

23. As a student, I want to finish Synced Tasks myself, since Canvas doesn't tell the feed when I've submitted, so that my list reflects what I've actually done.
24. As a student, I want a task I complete never recreated, so that finished work stays finished.
25. As a student, I want a task I delete never recreated, so that I can drop items I don't care about.
26. As a student, I want my renames, priorities, labels and descriptions kept, so that I can personalise tasks freely.
27. As a student, I want to move a Synced Task to another section or project without it being treated as deleted, so that I can organise my way.
28. As a student, I want my Reschedule respected until Canvas changes the date again, so that I can plan earlier than the deadline.
29. As a student, I want a Course Section I renamed to keep being used, so that my naming sticks.
30. As a student, I want a Course Section I deleted recreated only when that course needs a new Synced Task, so that I'm not fighting the sync over empty sections.

### When Canvas changes underneath

31. As a student, I want an Assignment that disappears from the feed to leave its Synced Task untouched. It may have been deleted, unpublished, lost its due date, or moved out of the feed's range; the sync can't tell which. Leaving the task alone means I don't lose anything I was tracking.
32. As a student, I want that disappearance logged once, not every run, so that the logs stay readable.
33. As a student, I want an Assignment that reappears to resume normal syncing, including a due date update if its date changed, so that a temporary disappearance doesn't break anything.

### State and recovery

34. As a student, I want the sync to remember what it has created in a `state.json` committed after each run, so that it works without a database.
35. As a student, I want a run with missing state to adopt existing Synced Tasks by their Canvas Assignment link, so that a reset doesn't duplicate everything.
36. As a student, I want a run with missing state to treat tasks I completed in the last 3 months as Dismissed, so that a reset doesn't bring back finished work.
37. As a student, I want the README to explain that tasks I deleted can't be recovered after a reset and may reappear once, so that I'm not surprised.
38. As a student, I want state to contain no secrets, and in particular not the feed address, so that the repo is safe to keep.

### Operating it

39. As a student, I want the sync to run every 3 hours on GitHub Actions and on demand, so that it works when my laptop is off.
40. As a student, I want overlapping runs queued instead of racing, so that a manual run never creates duplicates or a failed state commit.
41. As a student, I want a dry-run mode that logs what would change without writing to Todoist, so that I can check config safely.
42. As a student, I want each run to end with a one-line summary (created, updated, skipped, errors), so that I can see at a glance what happened.
43. As a student, I want one failing Assignment logged and skipped rather than aborting the run, so that one problem doesn't block everything.
44. As a student, I want the run to exit non-zero only when the whole run fails (e.g. feed unreachable, Todoist rejects my token), so that GitHub only emails me about real outages.
45. As a student, I want clear warnings when Todoist rejects a create because of a free-plan limit, so that I know to clean up or shorten the Lookahead.
46. As a student, I want failed requests retried with backoff and Todoist's rate limits respected, so that transient errors don't fail the run.
47. As a student, I want neither the feed address nor the Todoist token ever printed or logged, so that the Actions logs are safe.
48. As a student, I want a second run with no Canvas changes to make zero Todoist writes, so that the sync is predictable and cheap.
49. As a student, I want a typical run to finish in under a minute, so that it stays within free Actions minutes.

### Lifecycle

50. As a student, I want a configured Sync End Date (2027-08-01) after which runs do nothing and exit successfully, so that losing Canvas access after graduation doesn't trigger failure emails.
51. As a student, I want the workflow to disable itself after the Sync End Date, since the feed address never expires, so that I don't have to remember to switch it off.
52. As a student, I want an "Each new term" section in the README, so that term changes take two minutes.
53. As a student, I want a Decommission checklist in the README, so that taking the project down is quick and complete.
54. As a future reader of the repo, I want the glossary and ADRs kept current, so that the reasons behind surprising choices (like using the Calendar Feed) are on record.

## Implementation Decisions

### Modules

- **Sync engine**: the deep module holding all the behaviour.
  - A single entry point takes a Canvas source, a Todoist gateway, the prior state (possibly absent), the config and the current time.
  - It returns the new state plus a run summary.
  - It owns: the Sync Window, Dismissed detection, due date change detection and the description note, Missing from Canvas tracking, Course Section resolution, rebuilding missing state, the Sync End Date guard, per-item error isolation, and honouring dry run.
- **Canvas source**: a small interface with one operation, which lists the Assignments currently in the feed. Each Assignment record has:
  - assignment ID and course ID
  - course code, from the title tag
  - title, without the course tag
  - Canvas Due Date: a UTC date-time, or a date only
  - the Assignment's own Canvas link
- **Calendar Feed adapter**: implements the Canvas source (ADR 0002).
  - Fetches the feed with one GET and parses it with the `icalendar` library.
  - Keeps only events whose UID is `event-assignment-<id>`.
  - Takes the course ID from the event link's `include_contexts=course_<id>` parameter, and the course code from the trailing `[CODE]` tag in the title.
  - Builds the Assignment link as `<canvas host>/courses/<course id>/assignments/<assignment id>`, with the host taken from the event link.
  - Treats `VALUE=DATE` events as date-only, and handles the feed's duplicated `VALUE=DATE` parameter.
- **Todoist gateway**, a small interface:
  - list all active tasks across all projects
  - list completed tasks in a project since a given time (maximum 3 months)
  - find or create the project by name
  - list and create sections
  - create a task
  - update a task's due date and description
  - raise a distinct "plan limit reached" error

  It has no close operation: the sync never closes tasks.
- **Todoist HTTP adapter**: implements the gateway against Todoist API v1 (`/api/v1/`) with plain `requests`. IDs are opaque strings. A timed due date is sent as a fixed UTC datetime, and a date-only due date as a plain date.
- **Shared HTTP helper**: retries with backoff on 429 and 5xx and honours Todoist's `retry_after`. It never logs the feed address or authorization headers.
- **Config loader**: reads the non-secret YAML config and the two secret environment variables, and applies defaults.
- **State store**: loads and saves `state.json`, and treats a missing file as missing state.
- **Entry point / CLI**:
  - wires the adapters, config and state together, and accepts a `--dry-run` flag
  - prints the summary
  - sets the exit code: non-zero only when the whole run failed
  - reports when the sync is Retired

### Config

**Non-secret settings** (committed YAML):

| Setting | Default |
|---|---|
| `todoist_project_name` | `School` |
| `course_allowlist` | empty, meaning every course in the feed |
| `course_name_overrides` | empty map from course ID to short name |
| `lookahead_days` | `31` |
| `lookback_days` | `5` |
| `sync_end_date` | `2027-08-01` |
| `dry_run` | `false` |

**Secrets** (environment variables, or a git-ignored `.env` locally): `CANVAS_CALENDAR_FEED_URL` and `TODOIST_TOKEN`.

### State shape

- **Per course:** the Todoist section ID.
- **Per Canvas assignment ID:**
  - Todoist task ID
  - last-synced Canvas Due Date, kept exactly as the feed gave it (timed or date-only)
  - status: one of `open`, `dismissed`, `missing_from_canvas`
  - previous status, while it is `missing_from_canvas`

### Sync rules

1. **Retirement:** if today is after the Sync End Date, return immediately with no feed or Todoist calls.
2. **Dismissed detection:**
   - Fetch all active Todoist tasks once.
   - Any `open` state entry whose task is not in that list becomes `dismissed`.
   - Completed and deleted tasks are not told apart.
   - Membership is checked across all projects, so a moved task is not Dismissed.
3. **Missing state:**
   - Adopt active tasks in the School Project whose description contains a matching Assignment link.
   - Mark School Project tasks completed in the last 3 months with a matching link as `dismissed`.
4. **New Assignment** (no state entry): create a Synced Task only if its course passes the allowlist and its Canvas Due Date falls inside the Sync Window. Date-only due dates are compared as whole days.
5. **Existing `open` entry:** if the Canvas Due Date differs from the last-synced value, update the task's due date. This includes:
   - a time-only change
   - a switch between date-only and timed
   - a move outside the Sync Window

   Then append "Due date updated from Canvas on <date>" to the task's current description, and record the new value.
6. **`dismissed`:** never touched again.
7. **Missing from Canvas:**
   - An `open` entry whose Assignment is absent from the feed becomes `missing_from_canvas`, keeping its previous status. Log it once, at that transition. The task is left untouched; its due date is never cleared.
   - On reappearance, restore the previous status and apply rule 5.
8. **Course Section:**
   - Use the stored section ID if it still exists, even if I renamed it.
   - If it doesn't exist, create the section by name (the override, or else the course code), but only when a new Synced Task needs it.
   - Existing tasks are never moved.
9. **Free-plan limit:** a plan-limit error on create is logged as a warning, counted in errors, and the run continues. It is retried naturally on the next run.
10. **Idempotence:** a run with no feed changes makes zero Todoist writes.

### Workflow

- Scheduled every 3 hours, plus `workflow_dispatch`.
- `concurrency` group with `cancel-in-progress: false`.
- Permissions: `contents: write` and `actions: write`.
- Steps:
  1. set up Python 3.12+
  2. install dependencies
  3. run the sync with both secrets
  4. `git pull --rebase`, then commit `state.json` only if it changed, as `chore: sync state [skip ci]`
- After the Sync End Date, a step runs `gh workflow disable` on itself.

### Dependencies

`requests`, `icalendar`, a YAML parser, and the standard library. `pytest` for development. No Todoist SDK. The code must run on Python 3.12, even though local development uses a newer version.

## Testing Decisions

- **Good tests check behaviour you can observe from outside.** Assert on what ends up in Todoist (the fake's tasks, sections and recorded writes), on the returned state and on the summary. Never assert on internal helpers or call order. Write tests first, one red-green slice at a time (TDD).
- **Seam 1: sync engine (primary).** All behaviour is tested through the single sync-run entry point with in-memory fakes:
  - The **fake Canvas source** serves configurable Assignment records.
  - The **fake Todoist gateway** keeps tasks and sections in memory and records every write.
  - Fakes can simulate a Reschedule, a Dismissed task, a moved task, a deleted section, and a plan-limit error.
  - Time is injected.
- Required cases for seam 1:
  1. new Assignment → Synced Task created
  2. timed and date-only due dates
  3. Assignment inside the Lookback gets a task
  4. outside the Sync Window gets no task
  5. course allowlist respected
  6. Canvas Due Date change → task updated, with note
  7. time-only change and date-only↔timed switch count as changes
  8. user-completed task not recreated
  9. user-deleted task not recreated
  10. moved task not Dismissed
  11. user-edited title preserved
  12. user-Rescheduled task not overwritten when Canvas is unchanged
  13. Reschedule overwritten when Canvas changes
  14. renamed section reused
  15. deleted section recreated lazily
  16. Missing from Canvas logged once and its task untouched, then resumes on reappearance
  17. first run with no state file (adopt by link, and completed tasks become Dismissed)
  18. plan-limit error logged and the run continues
  19. second run with no changes makes zero writes
  20. dry run makes no writes
  21. no work after the Sync End Date
- **Seam 2: adapters (secondary, small).**
  - **Calendar Feed adapter**, tested against made-up `.ics` fixtures (never the real feed). Cover:
    - only `event-assignment-` UIDs are kept
    - course ID from the link, and course code from the title tag
    - title without the tag
    - Assignment link built correctly
    - date-only versus timed due dates, including the duplicated `VALUE=DATE` parameter
    - folded and escaped lines
    - retry on a failed fetch
    - the feed address never appearing in logs or error messages
  - **Todoist adapter**, tested with canned HTTP responses. Cover:
    - fixed UTC and date-only due date payloads
    - plan-limit responses mapped to the distinct error
    - `retry_after` honoured
    - the token never appearing in logs
- **Not tested automatically:** the workflow YAML and the CLI wiring. They are checked by a manual `--dry-run` run, as in the "Each new term" procedure.
- **Prior art:** none. This is a new repo.

## Out of Scope

- Closing Synced Tasks when an Assignment is submitted or graded. The feed has no submission status. If a Canvas token ever becomes available, this can come back as a follow-up using the REST API (see ADR 0002).
- Undated Assignments, points possible, and published/locked filtering, none of which the feed provides.
- Clearing a task's due date when Canvas removes it. That looks the same as a disappearance and is handled as Missing from Canvas.
- Two-way sync (Todoist changes affecting Canvas).
- Ordinary calendar events, announcements, grades, ungraded to-do items, and planner notes.
- Distinguishing completed from deleted tasks.
- Automated cleanup of Todoist data at Decommission.
- OneNote integration (possible phase 2: a page per Assignment via Microsoft Graph, linked in the task). Keep adapters modular so a new output can be added later.

## Further Notes

- **Vocabulary** follows `GLOSSARY.md`. ADR 0002 supersedes ADR 0001.
- **University of Auckland's position** (from TeachWell's Canvas FAQs):
  - non-admin Canvas API tokens expire after 30 days
  - Digital Services is "unlikely to issue tokens for most use cases"
  - students are pointed to the Calendar Feed
- **What the real feed showed** (checked 2026-10-05, structure only):
  - 20 events, all `event-assignment-<id>`, across 4 courses
  - every title ends in a `[CODE 123]` tag
  - event links point to the Canvas calendar page, with `include_contexts=course_<id>` and `#assignment_<id>`
  - 11 of 20 events are date-only (`VALUE=DATE`, with the parameter duplicated); the timed ones have DTSTART equal to DTEND, in UTC
  - the feed covered about 3 weeks back through the end of semester
  - whether extensions show the personal due date is **unverified**
- **Todoist:** REST v2 and Sync v9 were shut down in February 2026, so use only API v1. The free-plan limits (20 sections, 300 active tasks) are per account and include personal tasks.
- **The README must cover:**
  - getting the Calendar Feed address (Canvas → Calendar → Calendar Feed), and treating it like a password
  - getting the Todoist token
  - finding course IDs (from the feed link or the Canvas course URL)
  - running locally with `--dry-run`
  - setting up the GitHub secrets
  - resetting state, and that tasks I deleted may reappear once afterwards
  - "Each new term"
  - the Decommission checklist:
    1. confirm the workflow is disabled
    2. reset the Todoist token
    3. delete the repo secrets
    4. archive or delete the School Project
    5. archive or delete the repo

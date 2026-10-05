# Canvas → Todoist Assignment Sync: Requirements

> **Status: DRAFT** (2026-10-05). This version adds the decisions from the design grilling session. A new spec will replace it. Terms in **bold** are defined in [GLOSSARY.md](./GLOSSARY.md).

## Goal

Build a small script that automatically copies my Canvas assignments into Todoist as tasks, keeps their due dates current, and closes tasks once I've submitted the work. It runs on a schedule in GitHub Actions, so it works without my laptop being on.

This is a one-way sync. Canvas is the source of truth for assignments and due dates. Todoist is where I manage and check off my work.

The project has a fixed lifespan: it retires on its own after the **Sync End Date** (2027-08-01). See [Lifecycle](#lifecycle).

## Context and constraints

- **Todoist plan:** free (Beginner) plan.
  - At most **5 active projects**, so all synced tasks go into **one** project, not one project per course.
  - The account-wide limits of **20 sections** and **300 active tasks** include my personal tasks.
- **Devices:** I use Todoist on macOS, iOS, and Windows. Nothing in this project should be device-specific.
- **Hosting:** GitHub Actions on a schedule, in a **private** repo.
- **Language:** Python 3.12+. Use plain `requests` for both APIs, with one shared retry/backoff helper, and no Todoist SDK. Use the standard library for everything else.
- **APIs:**
  - Canvas LMS REST API (https://canvas.instructure.com/doc/api/). Use the per-course Assignments API, not the Planner API. See [ADR 0001](./docs/adr/0001-assignments-api-over-planner.md).
  - **Todoist API v1** at `https://api.todoist.com/api/v1/` (https://developer.todoist.com/api/v1/).
    - REST v2 and Sync v9 were shut down in February 2026.
    - IDs are opaque strings.

## Configuration

All secrets come from environment variables (GitHub Actions secrets in CI, a local `.env` file for development, which must be git-ignored):

| Variable | Purpose |
|---|---|
| `CANVAS_BASE_URL` | My school's Canvas URL, e.g. `https://myschool.instructure.com` |
| `CANVAS_TOKEN` | Canvas personal access token (Account → Settings → New Access Token). Set its expiry to about **2027-08-31**. |
| `TODOIST_TOKEN` | Todoist API token (Settings → Integrations → Developer) |

Non-secret settings go in a `config.yaml` committed to the repo:

- `todoist_project_name`: default `School`. Create it if it doesn't exist.
- `course_allowlist`: optional list of Canvas course IDs to sync. Default is empty, which means sync all *active* enrollments, so new terms are picked up automatically.
- `course_name_overrides`: optional map from course ID to a short display name (e.g. `12345: "COMP 2xx"`), used for section names.
- `sync_assignments_without_due_date`: default `false`.
- `lookahead_days`: default `31`.
- `lookback_days`: default `5`.
- `sync_end_date`: `2027-08-01`. On any later day, the script does nothing.
- `dry_run`: default `false`. When `true`, log what would change but make no Todoist writes.

## Functional requirements

### 1. Fetch from Canvas
- Get my active courses (current term only, so old unarchived courses aren't included).
- For each course, get its assignments with `include[]=submission`.
  - **Assignment** means anything with a Canvas assignment ID, including quizzes and graded discussions.
  - Ungraded to-do items and planner notes are out of scope.
- Handle Canvas pagination (`Link` headers) properly.
- Skip assignments that are unpublished or `locked_for_user`.
- A new task is only created for an assignment whose due date falls inside the **Sync Window**: from `lookback_days` ago to `lookahead_days` ahead, and the assignment must not be Done.
- Skip assignments with no due date unless `sync_assignments_without_due_date` is `true`.

### 2. Organize in Todoist
- All tasks go into the single **School Project**.
- One **Course Section** per course, named from `course_name_overrides` or else the Canvas course code.
  - Store the section ID per course in state.
  - If I rename a section, keep using it.
  - If I delete a section, recreate it by name the next time that course needs a new task. Existing tasks are never moved.
- Task **content** is the assignment name.
- Task **description** includes the Canvas assignment link (`html_url`) and points possible, if available. The link is how a Synced Task is matched to its Assignment when state is rebuilt.
- Task **due date** is a *fixed* timezone due date: Canvas's UTC `due_at`, sent unchanged as `YYYY-MM-DDTHH:MM:SSZ`.
- No labels are added.

### 3. Keep tasks in sync
- **New assignment** inside the Sync Window → create a task.
- **Canvas due date changed** → update the task's due date and add a note to the description: "Due date updated from Canvas on <date>". "Changed" covers:
  - a different date or time, even a time-only change
  - a new date outside the Sync Window
  - a removed due date (clear the task's due date)
- **Assignment is Done** (submission submitted, graded, or excused) → close the task if it is still open. This happens at most once (**Closed by Sync**). If I reopen the task, it is never closed again, and the sync never reopens tasks.
- **Assignment Missing from Canvas** (deleted, unpublished, or its course left scope):
  - Leave the task alone.
  - Log it once, when it first disappears, and mark it `missing_from_canvas`.
  - If the assignment comes back, restore its previous status and resume normal syncing.

### 4. Respect my changes in Todoist
This part is important:
- **Never recreate a task I completed or deleted myself (Dismissed).**
  - Each run fetches all my active tasks across all projects in one call.
  - A task that state lists as open, but that isn't in that list, becomes Dismissed. Completed and deleted tasks are not told apart.
  - Because the check covers all projects, moving a task out of the School Project does not make it Dismissed.
- **Never overwrite edits I made**, such as renaming the task, changing priority, adding labels, or moving it to another section or project. After creation, the sync may only:
  - change the due date (and add the note), and only when the *Canvas* due date has changed since the last sync
  - close the task once, when the assignment becomes Done

  If I rescheduled a task in Todoist, leave it alone unless Canvas changes the date again.

### 5. State tracking
- Keep `state.json`, which contains:
  - per course: the Todoist section ID
  - per Canvas assignment ID:
    - the Todoist task ID
    - the last-synced Canvas due date
    - status: `open`, `closed_by_sync`, `dismissed`, or `missing_from_canvas` (with its previous status)
- The GitHub Actions workflow commits the updated state file back to the repo after each run, with a commit message like `chore: sync state [skip ci]`.
- **Missing state** (first run or reset):
  - Adopt active tasks in the School Project whose description contains a matching Canvas link.
  - Also fetch the School Project's completed tasks from the last 3 months (the API's maximum per query). Mark any with a matching link as Dismissed.
  - Tasks I deleted can't be recovered and may be recreated once. The README must say this.

## Non-functional requirements

- **Idempotent:** running the script twice in a row with no Canvas changes makes zero Todoist writes.
- **Rate limits:** respect Canvas and Todoist rate limits, and retry with backoff on HTTP 429/5xx.
  - Canvas may also throttle with 403 "Rate Limit Exceeded".
  - Honor Todoist's `retry_after`.
- **Free-plan limits:** if Todoist rejects a create because of a plan limit (sections or tasks), log a clear warning and continue.
- **Security:** never print or log tokens. No secrets in the repo, including in `state.json`.
- **Logging:** end each run with a short summary, e.g. `created 2, updated 1, closed 3, skipped 14, errors 0`.
- **Failure behavior:** if one course or assignment fails, log it and continue. Exit non-zero only if the whole run failed (so GitHub emails me).
- **Runtime:** a typical run should finish in under a minute.

## GitHub Actions workflow

- Runs on a schedule **every 3 hours**, plus a manual `workflow_dispatch` trigger.
- Uses a `concurrency: sync` group with `cancel-in-progress: false`.
- Set up Python, install dependencies, and run the sync. Then `git pull --rebase` and commit `state.json` if it changed.
- Uses repo secrets for the three environment variables.
- Permissions: `contents: write` (to push state) and `actions: write` (to disable itself).
- **Retirement step:** after `sync_end_date`, the workflow runs `gh workflow disable sync.yml`.

## Lifecycle

| Phase | What happens |
|---|---|
| Setup | Create tokens (Canvas token expires about 2027-08-31), add repo secrets, write `config.yaml`, run locally with `--dry-run`. |
| Each new term | Courses are picked up automatically. Optionally add `course_name_overrides`, then check one dry run. |
| **Retired** (after 2027-08-01) | The script does nothing and exits successfully. The workflow disables itself. |
| **Decommission** (manual) | Follow the checklist below. |

**Decommission checklist:**
1. Confirm the workflow is disabled.
2. Revoke the Canvas token.
3. Reset the Todoist token, which invalidates the old one.
4. Delete the repo secrets.
5. Archive or delete the School Project in Todoist.
6. Archive or delete the repo.

## Deliverables

1. Python source, organized simply (e.g. `canvas.py`, `todoist.py`, `sync.py`, `main.py`), with type hints.
2. `config.example.yaml` and `.env.example`.
3. `.github/workflows/sync.yml`.
4. `pytest` unit tests for the sync/diff logic using mocked API responses, **written before the implementation (TDD)**. They cover:
   - new assignment
   - due date change
   - submission → close
   - user-completed task not recreated
   - user-edited title preserved
   - user-rescheduled task not overwritten
   - first run with no state file
   - assignment inside the Lookback window gets a task
   - excused counts as Done
   - reopened task not closed again
   - time-only due date change overwrites a reschedule
   - removed due date clears the task's date
   - assignment missing from Canvas is logged once and its task left alone
   - free-plan limit error is logged and the run continues
   - a run with no changes makes zero Todoist writes
   - no work after `sync_end_date`
5. A `README.md` covering:
   - how to get both tokens (including the Canvas token expiry)
   - how to find course IDs
   - how to run locally with `--dry-run`
   - how to set up the GitHub secrets
   - how to reset the state, and what a reset can't recover
   - "Each new term"
   - the Decommission checklist

## Out of scope (for now)

- Two-way sync (Todoist changes affecting Canvas).
- Syncing Canvas announcements, grades, calendar events, ungraded to-do items, or planner notes.
- OneNote integration. A possible phase 2 is creating a OneNote page per assignment via Microsoft Graph and linking it in the task. Keep the code modular enough that this could be added later.
- Automated cleanup of Todoist data at decommission.

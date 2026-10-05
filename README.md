# Canvas → Todoist Sync

Copies my Canvas Assignments into Todoist, one way, every 3 hours on GitHub Actions.

- Each Assignment due in the **Sync Window** (5 days back to 31 days ahead) becomes a **Synced Task** in the `School` project, under one section per course.
- When Canvas changes a due date, the task's due date follows, with a note in its description.
- Anything I do in Todoist is respected. Tasks I complete or delete are never recreated, and renames, priorities, labels, moves and Reschedules are left alone (a Reschedule stands until Canvas changes the date again).
- The sync never closes tasks: Canvas doesn't say when I've submitted, so I tick them off myself.
- After the **Sync End Date** (2027-08-01) the sync is **Retired**: runs do nothing and the workflow switches itself off. Then follow the [Decommission checklist](#decommission).

It reads Canvas through the Calendar Feed rather than the Canvas API ([ADR 0002](docs/adr/0002-calendar-feed-instead-of-api.md)). Vocabulary is in [GLOSSARY.md](GLOSSARY.md).

## Setup

### 1. Get the Calendar Feed address

In Canvas, open **Calendar** and click **Calendar Feed** (bottom right). Copy the address.

**Treat it like a password.** Anyone with it can read my calendar, and it never expires. Keep it out of commits, chats and logs; the sync itself never prints it. If it leaks, contact the university's Canvas support about resetting it.

### 2. Get the Todoist token

In Todoist, open **Settings → Integrations → Developer** and copy the **API token**. It gives full access to my Todoist account, so treat it like a password too.

### 3. Set the GitHub secrets

In the repo, go to **Settings → Secrets and variables → Actions** and add two repository secrets:

| Secret | Value |
|---|---|
| `CANVAS_CALENDAR_FEED_URL` | the Calendar Feed address |
| `TODOIST_TOKEN` | the Todoist API token |

Or from a terminal (each command prompts for the value, so it stays out of shell history):

```sh
gh secret set CANVAS_CALENDAR_FEED_URL
gh secret set TODOIST_TOKEN
```

### 4. Settings (optional)

Every setting has a default, so no config file is needed. To change one, copy `config.example.yaml` to `config.yaml`, edit it, and commit it. The example lists every setting with its default.

### 5. Check it with a dry run

Run the sync locally with `--dry-run` (below), then start the workflow by hand: **Actions → Sync Canvas to Todoist → Run workflow**. After that it runs every 3 hours by itself.

## Running locally

Needs Python 3.12 or newer.

```sh
python -m venv .venv
.venv/Scripts/activate            # Windows; on macOS/Linux: source .venv/bin/activate
pip install -r requirements-dev.txt
cp .env.example .env              # then fill in both secrets; .env is git-ignored
python -m canvas_todoist --dry-run
```

`--dry-run` logs what would be created or updated, and writes nothing to Todoist or `state.json`. Leave the flag off to sync for real. Each run ends with a summary line: created, updated, skipped, errors.

Tests and type checks:

```sh
python -m pytest
python -m mypy
```

### Finding course IDs

`course_allowlist` and `course_name_overrides` use Canvas course IDs. Find one in either place:

- the course's address in Canvas: `https://<canvas host>/courses/123456` → `123456`
- the Calendar Feed: each entry's link contains `include_contexts=course_123456`

## How it runs

The workflow (`.github/workflows/sync.yml`) runs every 3 hours and on demand. Runs queue rather than overlap. After each run it commits `state.json` if it changed, as `chore: sync state [skip ci]`.

- `state.json` records which Synced Task belongs to which Assignment. It holds Todoist IDs and due dates only, no secrets.
- One failing Assignment is logged and skipped; the rest of the run carries on.
- A full free-plan account (20 sections, 300 active tasks) produces a warning, and the next run tries again. Tidy up Todoist or shorten `lookahead_days`.
- The run fails, and GitHub emails me, only when the whole run failed: the feed was unreachable or unreadable, or Todoist rejected the token.

## Resetting state

If `state.json` is lost or wrong, delete it and commit. The next run rebuilds it:

- Active tasks in the School Project are matched to their Assignments by the Canvas link in their description, so nothing is duplicated.
- Tasks I completed in the last 3 months become Dismissed, so they aren't recreated.
- **Tasks I deleted can't be recovered this way.** Todoist doesn't list deleted tasks, so an Assignment whose task I deleted may get a new Synced Task once. Delete it again and it stays gone.
- Only Assignments in the Calendar Feed at the time are matched. If one is Missing from Canvas during the reset and later comes back inside the Sync Window, it may get a second Synced Task.

## Each new term

1. If `course_allowlist` is set, swap the old course IDs for the new ones ([finding course IDs](#finding-course-ids)). If it's empty, new courses are picked up automatically.
2. Add `course_name_overrides` for any new course that should get a short section name.
3. Delete last term's empty Course Sections in Todoist. The free plan allows only 20 sections.
4. Run `python -m canvas_todoist --dry-run` and check that the new courses' Assignments appear.
5. Commit `config.yaml` if it changed.

## Decommission

After the Sync End Date the sync is Retired and the workflow disables itself. Then:

1. Confirm the workflow is disabled: **Actions → Sync Canvas to Todoist** shows it as disabled (or run `gh workflow list --all`). If not, run `gh workflow disable sync.yml`.
2. Reset the Todoist token: **Settings → Integrations → Developer → Issue a new API token**. This makes the old one useless.
3. Delete both repo secrets: **Settings → Secrets and variables → Actions**, or `gh secret delete CANVAS_CALENDAR_FEED_URL` and `gh secret delete TODOIST_TOKEN`.
4. Archive or delete the School Project in Todoist.
5. Archive or delete this repo.

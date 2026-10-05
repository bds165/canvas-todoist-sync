from datetime import date, datetime, timezone

import pytest

from canvas_todoist.calendar_feed import CalendarFeedError
from canvas_todoist.config import Config
from canvas_todoist.engine import SyncAborted, run_sync
from canvas_todoist.models import Assignment
from canvas_todoist.state import State
from canvas_todoist.todoist import PlanLimitReached, TodoistError, TodoistRejectedToken

from tests.fakes import FakeCanvasSource, FakeTodoist

NOW = datetime(2026, 10, 5, 9, 0, tzinfo=timezone.utc)


def assignment(
    assignment_id: str = "1001",
    *,
    course_id: str = "77",
    course_code: str = "COMPSCI 101",
    title: str = "Essay 1",
    due: date | datetime = datetime(2026, 10, 10, 10, 59, tzinfo=timezone.utc),
) -> Assignment:
    return Assignment(
        assignment_id=assignment_id,
        course_id=course_id,
        course_code=course_code,
        title=title,
        due=due,
        url=f"https://canvas.example.edu/courses/{course_id}/assignments/{assignment_id}",
    )


def test_new_assignment_becomes_synced_task_in_course_section():
    todoist = FakeTodoist()

    result = run_sync(FakeCanvasSource([assignment()]), todoist, None, Config(), NOW)

    task = todoist.task_titled("Essay 1")
    assert todoist.projects[task.project_id] == "School"
    assert todoist.section_name(task.section_id) == "COMPSCI 101"
    assert "https://canvas.example.edu/courses/77/assignments/1001" in task.description
    assert task.due == datetime(2026, 10, 10, 10, 59, tzinfo=timezone.utc)
    entry = result.state.assignments["1001"]
    assert entry.task_id == task.id
    assert entry.status == "open"
    assert entry.canvas_due == datetime(2026, 10, 10, 10, 59, tzinfo=timezone.utc)
    assert result.state.courses["77"].section_id == task.section_id
    assert str(result.summary) == "created 1, updated 0, skipped 0, errors 0"


def test_assignments_in_one_course_share_its_section():
    todoist = FakeTodoist()
    canvas = FakeCanvasSource([assignment("1001", title="Essay 1"), assignment("1002", title="Quiz 1")])

    run_sync(canvas, todoist, None, Config(), NOW)

    assert todoist.task_titled("Essay 1").section_id == todoist.task_titled("Quiz 1").section_id
    assert len(todoist.sections) == 1


def test_existing_project_and_section_are_found_by_name():
    todoist = FakeTodoist()
    project_id = todoist.create_project("School")
    section_id = todoist.create_section(project_id, "COMPSCI 101")

    run_sync(FakeCanvasSource([assignment()]), todoist, None, Config(), NOW)

    task = todoist.task_titled("Essay 1")
    assert (task.project_id, task.section_id) == (project_id, section_id)
    assert len(todoist.projects) == 1 and len(todoist.sections) == 1


def test_course_section_uses_override_name():
    todoist = FakeTodoist()
    config = Config(course_name_overrides={"77": "Programming"})

    run_sync(FakeCanvasSource([assignment()]), todoist, None, config, NOW)

    assert todoist.section_name(todoist.task_titled("Essay 1").section_id) == "Programming"


def test_date_only_due_date_stays_date_only():
    todoist = FakeTodoist()

    result = run_sync(FakeCanvasSource([assignment(due=date(2026, 10, 12))]), todoist, None, Config(), NOW)

    assert todoist.task_titled("Essay 1").due == date(2026, 10, 12)
    assert result.state.assignments["1001"].canvas_due == date(2026, 10, 12)


def test_assignment_overdue_within_lookback_gets_task():
    todoist = FakeTodoist()
    canvas = FakeCanvasSource([
        assignment("1", title="Timed, 5 days ago", due=datetime(2026, 9, 30, 9, 0, tzinfo=timezone.utc)),
        assignment("2", title="Date-only, 5 days ago", due=date(2026, 9, 30)),
    ])

    result = run_sync(canvas, todoist, None, Config(), NOW)

    assert {t.content for t in todoist.tasks.values()} == {"Timed, 5 days ago", "Date-only, 5 days ago"}
    assert result.summary.created == 2


def test_assignment_outside_sync_window_gets_no_task():
    todoist = FakeTodoist()
    canvas = FakeCanvasSource([
        assignment("1", due=datetime(2026, 9, 30, 8, 59, tzinfo=timezone.utc)),  # just past Lookback
        assignment("2", due=date(2026, 9, 29)),
        assignment("3", due=datetime(2026, 11, 5, 9, 1, tzinfo=timezone.utc)),  # just past Lookahead
        assignment("4", due=date(2026, 11, 6)),
    ])

    result = run_sync(canvas, todoist, None, Config(), NOW)

    assert todoist.tasks == {}
    assert result.state.assignments == {}
    assert str(result.summary) == "created 0, updated 0, skipped 4, errors 0"


def test_lookahead_edge_is_inside_window():
    todoist = FakeTodoist()
    canvas = FakeCanvasSource([
        assignment("1", title="Timed", due=datetime(2026, 11, 5, 9, 0, tzinfo=timezone.utc)),
        assignment("2", title="Date-only", due=date(2026, 11, 5)),
    ])

    run_sync(canvas, todoist, None, Config(), NOW)

    assert {t.content for t in todoist.tasks.values()} == {"Timed", "Date-only"}


def test_sync_window_is_configurable():
    todoist = FakeTodoist()
    canvas = FakeCanvasSource([
        assignment("1", title="Soon", due=date(2026, 10, 7)),
        assignment("2", title="Later", due=date(2026, 10, 9)),
        assignment("3", title="Yesterday", due=date(2026, 10, 4)),
    ])

    run_sync(canvas, todoist, None, Config(lookahead_days=2, lookback_days=0), NOW)

    assert {t.content for t in todoist.tasks.values()} == {"Soon"}


def test_course_allowlist_is_respected():
    todoist = FakeTodoist()
    canvas = FakeCanvasSource([
        assignment("1", course_id="77", title="Tracked"),
        assignment("2", course_id="88", course_code="MATHS 108", title="Excluded"),
    ])

    result = run_sync(canvas, todoist, None, Config(course_allowlist=frozenset({"77"})), NOW)

    assert {t.content for t in todoist.tasks.values()} == {"Tracked"}
    assert "88" not in result.state.courses
    assert result.summary.skipped == 1


def test_dry_run_writes_nothing_and_logs_what_would_be_created(caplog):
    todoist = FakeTodoist()
    caplog.set_level("INFO")

    result = run_sync(FakeCanvasSource([assignment()]), todoist, None, Config(dry_run=True), NOW)

    assert todoist.writes == []
    assert result.state.assignments == {}
    assert "Essay 1" in caplog.text and "would create" in caplog.text.lower()
    assert result.summary.created == 1


def test_assignment_already_in_state_is_not_recreated():
    todoist = FakeTodoist()
    canvas = FakeCanvasSource([assignment()])
    first = run_sync(canvas, todoist, None, Config(), NOW)
    todoist.writes.clear()

    second = run_sync(canvas, todoist, first.state, Config(), NOW)

    assert todoist.writes == []
    assert second.state == first.state
    assert str(second.summary) == "created 0, updated 0, skipped 0, errors 0"


def test_run_aborted_partway_still_reports_tasks_already_created():
    todoist = FakeTodoist()
    todoist.failures["create_task:Quiz 1"] = TodoistRejectedToken("Todoist POST /tasks failed: HTTP 401")
    canvas = FakeCanvasSource([assignment("1001", title="Essay 1"), assignment("1002", title="Quiz 1")])

    with pytest.raises(SyncAborted) as raised:
        run_sync(canvas, todoist, None, Config(), NOW)

    partial = raised.value.result.state
    assert set(partial.assignments) == {"1001"}
    assert partial.assignments["1001"].task_id == todoist.task_titled("Essay 1").id


def test_date_only_sync_window_counts_whole_days_in_auckland():
    # 12:00 UTC on 5 Oct is 01:00 on 6 Oct in Auckland (NZDT, UTC+13).
    now = datetime(2026, 10, 5, 12, 0, tzinfo=timezone.utc)
    todoist = FakeTodoist()
    canvas = FakeCanvasSource([
        assignment("1", title="Last Lookahead day", due=date(2026, 11, 6)),
        assignment("2", title="Past Lookback", due=date(2026, 9, 30)),
        assignment("3", title="First Lookback day", due=date(2026, 10, 1)),
    ])

    run_sync(canvas, todoist, None, Config(), now)

    assert {t.content for t in todoist.tasks.values()} == {"Last Lookahead day", "First Lookback day"}


# -- Canvas Due Date changes ---------------------------------------------------

LATER = datetime(2026, 10, 6, 9, 0, tzinfo=timezone.utc)
NEW_DUE = datetime(2026, 10, 12, 10, 59, tzinfo=timezone.utc)


def synced(todoist: FakeTodoist, *assignments: Assignment, config: Config = Config()):
    """State after a first run that created a Synced Task for each Assignment."""
    result = run_sync(FakeCanvasSource(list(assignments)), todoist, None, config, NOW)
    todoist.writes.clear()
    return result.state


def test_canvas_due_date_change_updates_task_and_notes_it():
    todoist = FakeTodoist()
    state = synced(todoist, assignment())

    result = run_sync(FakeCanvasSource([assignment(due=NEW_DUE)]), todoist, state, Config(), LATER)

    task = todoist.task_titled("Essay 1")
    assert task.due == NEW_DUE
    # 9:00 UTC on 6 Oct is 22:00 on 6 Oct in Auckland.
    assert task.description == (
        "https://canvas.example.edu/courses/77/assignments/1001\n\n"
        "Due date updated from Canvas on 2026-10-06"
    )
    assert result.state.assignments["1001"].canvas_due == NEW_DUE
    assert str(result.summary) == "created 0, updated 1, skipped 0, errors 0"


@pytest.mark.parametrize(
    ("before", "after"),
    [
        pytest.param(datetime(2026, 10, 10, 10, 59, tzinfo=timezone.utc),
                     datetime(2026, 10, 10, 9, 0, tzinfo=timezone.utc), id="time only"),
        pytest.param(date(2026, 10, 10), datetime(2026, 10, 10, 10, 59, tzinfo=timezone.utc), id="date-only to timed"),
        pytest.param(datetime(2026, 10, 10, 10, 59, tzinfo=timezone.utc), date(2026, 10, 10), id="timed to date-only"),
        pytest.param(date(2026, 10, 10), date(2027, 3, 1), id="outside the Sync Window"),
    ],
)
def test_every_kind_of_canvas_due_date_change_is_applied(before, after):
    todoist = FakeTodoist()
    state = synced(todoist, assignment(due=before))

    result = run_sync(FakeCanvasSource([assignment(due=after)]), todoist, state, Config(), LATER)

    task = todoist.task_titled("Essay 1")
    assert task.due == after and type(task.due) is type(after)
    assert task.description.endswith("Due date updated from Canvas on 2026-10-06")
    assert result.state.assignments["1001"].canvas_due == after
    assert result.summary.updated == 1


def test_due_date_note_keeps_my_edits_to_title_and_description():
    todoist = FakeTodoist()
    state = synced(todoist, assignment())
    task = todoist.task_titled("Essay 1")
    task.content = "Essay 1: draft first!"
    task.description = "My plan: outline on Monday"

    run_sync(FakeCanvasSource([assignment(due=NEW_DUE)]), todoist, state, Config(), LATER)

    assert task.content == "Essay 1: draft first!"
    assert task.description == "My plan: outline on Monday\n\nDue date updated from Canvas on 2026-10-06"
    assert todoist.writes == [("update_task", task.id)]


def test_my_reschedule_stands_while_canvas_due_date_is_unchanged():
    todoist = FakeTodoist()
    state = synced(todoist, assignment())
    task = todoist.task_titled("Essay 1")
    todoist.reschedule(task.id, date(2026, 10, 8))

    result = run_sync(FakeCanvasSource([assignment()]), todoist, state, Config(), LATER)

    assert task.due == date(2026, 10, 8)
    assert todoist.writes == []
    assert result.summary.updated == 0


def test_my_reschedule_is_overwritten_when_canvas_due_date_changes():
    todoist = FakeTodoist()
    state = synced(todoist, assignment())
    task = todoist.task_titled("Essay 1")
    todoist.reschedule(task.id, date(2026, 10, 8))

    run_sync(FakeCanvasSource([assignment(due=NEW_DUE)]), todoist, state, Config(), LATER)

    assert task.due == NEW_DUE


def test_second_run_after_a_due_date_change_makes_no_writes():
    todoist = FakeTodoist()
    state = synced(todoist, assignment())
    canvas = FakeCanvasSource([assignment(due=NEW_DUE)])
    first = run_sync(canvas, todoist, state, Config(), LATER)
    todoist.writes.clear()

    second = run_sync(canvas, todoist, first.state, Config(), LATER)

    assert todoist.writes == []
    assert str(second.summary) == "created 0, updated 0, skipped 0, errors 0"


def test_dry_run_due_date_change_writes_nothing():
    todoist = FakeTodoist()
    state = synced(todoist, assignment())

    result = run_sync(FakeCanvasSource([assignment(due=NEW_DUE)]), todoist, state, Config(dry_run=True), LATER)

    assert todoist.writes == []
    assert result.state.assignments["1001"].canvas_due == datetime(2026, 10, 10, 10, 59, tzinfo=timezone.utc)
    assert result.summary.updated == 1


# -- Dismissed and moved tasks --------------------------------------------------


@pytest.mark.parametrize("dismiss", ["complete", "delete"])
def test_task_i_completed_or_deleted_is_dismissed_and_never_touched_again(dismiss):
    todoist = FakeTodoist()
    state = synced(todoist, assignment())
    task_id = todoist.task_titled("Essay 1").id
    if dismiss == "complete":
        todoist.complete(task_id, at=NOW)
    else:
        todoist.delete(task_id)
    canvas = FakeCanvasSource([assignment(due=NEW_DUE)])

    first = run_sync(canvas, todoist, state, Config(), LATER)
    second = run_sync(canvas, todoist, first.state, Config(), LATER)

    assert first.state.assignments["1001"].status == "dismissed"
    assert second.state.assignments["1001"].status == "dismissed"
    assert todoist.writes == []
    assert todoist.tasks == {}
    assert str(second.summary) == "created 0, updated 0, skipped 0, errors 0"


def test_task_i_moved_to_another_project_is_not_dismissed():
    todoist = FakeTodoist()
    state = synced(todoist, assignment())
    task = todoist.task_titled("Essay 1")
    todoist.move(task.id, todoist.create_project("Personal"))
    todoist.writes.clear()

    result = run_sync(FakeCanvasSource([assignment(due=NEW_DUE)]), todoist, state, Config(), LATER)

    assert result.state.assignments["1001"].status == "open"
    assert task.due == NEW_DUE
    assert todoist.writes == [("update_task", task.id)]


# -- Course Section resilience --------------------------------------------------


def test_section_i_renamed_keeps_being_used():
    todoist = FakeTodoist()
    state = synced(todoist, assignment("1001"))
    section_id = todoist.task_titled("Essay 1").section_id
    assert section_id is not None
    todoist.rename_section(section_id, "Programming 🖥")

    run_sync(FakeCanvasSource([assignment("1002", title="Quiz 1")]), todoist, state, Config(), LATER)

    assert todoist.task_titled("Quiz 1").section_id == section_id
    assert len(todoist.sections) == 1


def test_section_i_deleted_is_not_recreated_until_a_new_task_needs_it():
    todoist = FakeTodoist()
    state = synced(todoist, assignment("1001"))
    todoist.delete_section(todoist.task_titled("Essay 1").section_id)

    result = run_sync(FakeCanvasSource([assignment("1001")]), todoist, state, Config(), LATER)

    assert todoist.writes == []
    assert todoist.sections == {}
    assert result.state.assignments["1001"].status == "dismissed"


def test_section_i_deleted_is_recreated_by_name_for_a_new_task():
    todoist = FakeTodoist()
    state = synced(todoist, assignment("1001"))
    old_section = todoist.task_titled("Essay 1").section_id
    todoist.delete_section(old_section)
    canvas = FakeCanvasSource([assignment("1001"), assignment("1002", title="Quiz 1")])

    result = run_sync(canvas, todoist, state, Config(), LATER)

    new_section = todoist.task_titled("Quiz 1").section_id
    assert new_section != old_section
    assert todoist.section_name(new_section) == "COMPSCI 101"
    assert result.state.courses["77"].section_id == new_section


def test_existing_task_in_another_section_is_never_moved():
    todoist = FakeTodoist()
    state = synced(todoist, assignment("1001"))
    task = todoist.task_titled("Essay 1")
    todoist.move(task.id, task.project_id, todoist.create_section(task.project_id, "This week"))
    todoist.writes.clear()

    run_sync(FakeCanvasSource([assignment("1001", due=NEW_DUE)]), todoist, state, Config(), LATER)

    assert todoist.section_name(task.section_id) == "This week"
    assert todoist.writes == [("update_task", task.id)]


# -- Missing from Canvas --------------------------------------------------------


def test_assignment_gone_from_feed_is_missing_from_canvas_logged_once_and_task_untouched(caplog):
    caplog.set_level("INFO")
    todoist = FakeTodoist()
    state = synced(todoist, assignment())
    task = todoist.task_titled("Essay 1")
    empty_feed = FakeCanvasSource([])

    first = run_sync(empty_feed, todoist, state, Config(), LATER)
    second = run_sync(empty_feed, todoist, first.state, Config(), LATER)

    entry = second.state.assignments["1001"]
    assert entry.status == "missing_from_canvas"
    assert entry.previous_status == "open"
    assert caplog.text.lower().count("missing from canvas") == 1
    assert todoist.writes == []
    assert task.due == datetime(2026, 10, 10, 10, 59, tzinfo=timezone.utc)


def test_assignment_back_in_feed_resumes_syncing_its_due_date():
    todoist = FakeTodoist()
    state = synced(todoist, assignment())
    gone = run_sync(FakeCanvasSource([]), todoist, state, Config(), LATER)

    back = run_sync(FakeCanvasSource([assignment(due=NEW_DUE)]), todoist, gone.state, Config(), LATER)

    entry = back.state.assignments["1001"]
    assert (entry.status, entry.previous_status) == ("open", None)
    assert todoist.task_titled("Essay 1").due == NEW_DUE
    assert back.summary.updated == 1


def test_dismissed_assignment_gone_from_feed_stays_dismissed():
    todoist = FakeTodoist()
    state = synced(todoist, assignment())
    todoist.delete(todoist.task_titled("Essay 1").id)
    dismissed = run_sync(FakeCanvasSource([assignment()]), todoist, state, Config(), LATER)

    gone = run_sync(FakeCanvasSource([]), todoist, dismissed.state, Config(), LATER)
    back = run_sync(FakeCanvasSource([assignment()]), todoist, gone.state, Config(), LATER)

    assert gone.state.assignments["1001"].status == "dismissed"
    assert back.state.assignments["1001"].status == "dismissed"
    assert todoist.writes == []


def test_task_dismissed_while_missing_from_canvas_stays_dismissed_on_return():
    todoist = FakeTodoist()
    state = synced(todoist, assignment())
    gone = run_sync(FakeCanvasSource([]), todoist, state, Config(), LATER)
    todoist.complete(todoist.task_titled("Essay 1").id, at=LATER)

    back = run_sync(FakeCanvasSource([assignment(due=NEW_DUE)]), todoist, gone.state, Config(), LATER)

    assert back.state.assignments["1001"].status == "dismissed"
    assert todoist.writes == []


# -- Rebuilding missing state ---------------------------------------------------


def school_with_task(todoist: FakeTodoist, description: str, due: date | datetime = date(2026, 10, 9)) -> str:
    project_id = todoist.find_project("School") or todoist.create_project("School")
    task_id = todoist.add_task("Essay 1 (renamed)", description, project_id, due)
    todoist.writes.clear()
    return task_id


def test_without_state_active_task_with_assignment_link_is_adopted():
    todoist = FakeTodoist()
    task_id = school_with_task(todoist, "notes\nhttps://canvas.example.edu/courses/77/assignments/1001")

    result = run_sync(FakeCanvasSource([assignment()]), todoist, None, Config(), NOW)

    entry = result.state.assignments["1001"]
    assert (entry.task_id, entry.status) == (task_id, "open")
    assert entry.canvas_due == datetime(2026, 10, 10, 10, 59, tzinfo=timezone.utc)
    assert todoist.writes == []
    assert len(todoist.tasks) == 1
    assert str(result.summary) == "created 0, updated 0, skipped 0, errors 0"


def test_without_state_link_to_a_longer_assignment_id_is_not_a_match():
    todoist = FakeTodoist()
    school_with_task(todoist, "https://canvas.example.edu/courses/77/assignments/10010")

    result = run_sync(FakeCanvasSource([assignment("1001")]), todoist, None, Config(), NOW)

    assert result.summary.created == 1


def test_without_state_task_in_another_project_is_not_adopted():
    todoist = FakeTodoist()
    personal = todoist.create_project("Personal")
    todoist.add_task("Essay 1", "https://canvas.example.edu/courses/77/assignments/1001", personal, date(2026, 10, 9))

    result = run_sync(FakeCanvasSource([assignment()]), todoist, None, Config(), NOW)

    assert result.summary.created == 1


def test_without_state_task_completed_in_last_3_months_is_dismissed():
    todoist = FakeTodoist()
    recent = school_with_task(todoist, "https://canvas.example.edu/courses/77/assignments/1001")
    todoist.complete(recent, at=datetime(2026, 7, 10, tzinfo=timezone.utc))
    canvas = FakeCanvasSource([assignment("1001")])

    first = run_sync(canvas, todoist, None, Config(), NOW)
    second = run_sync(canvas, todoist, first.state, Config(), NOW)

    entry = second.state.assignments["1001"]
    assert (entry.task_id, entry.status) == (recent, "dismissed")
    assert todoist.tasks == {}
    assert todoist.writes == []


def test_without_state_task_completed_over_3_months_ago_does_not_count():
    todoist = FakeTodoist()
    old = school_with_task(todoist, "https://canvas.example.edu/courses/77/assignments/1001")
    todoist.complete(old, at=datetime(2026, 6, 1, tzinfo=timezone.utc))

    result = run_sync(FakeCanvasSource([assignment("1001")]), todoist, None, Config(), NOW)

    assert result.summary.created == 1


def test_without_state_and_without_school_project_nothing_is_adopted():
    todoist = FakeTodoist()

    result = run_sync(FakeCanvasSource([assignment()]), todoist, None, Config(dry_run=True), NOW)

    assert todoist.writes == []
    assert result.summary.created == 1


# -- Idempotence ----------------------------------------------------------------


def test_second_run_without_feed_changes_makes_no_writes_whatever_the_statuses():
    todoist = FakeTodoist()
    canvas = FakeCanvasSource([
        assignment("1", title="Open"),
        assignment("2", title="Dismissed"),
        assignment("3", title="Missing"),
        assignment("4", title="Far off", due=date(2027, 3, 1)),
    ])
    state = run_sync(canvas, todoist, None, Config(), NOW).state
    todoist.delete(todoist.task_titled("Dismissed").id)
    canvas.assignments = [a for a in canvas.assignments if a.title != "Missing"]
    first = run_sync(canvas, todoist, state, Config(), LATER)
    todoist.writes.clear()

    second = run_sync(canvas, todoist, first.state, Config(), LATER)

    assert todoist.writes == []
    assert second.state == first.state
    assert str(second.summary) == "created 0, updated 0, skipped 1, errors 0"


# -- Errors --------------------------------------------------------------------


def test_plan_limit_on_task_create_is_a_warning_and_the_run_continues(caplog):
    todoist = FakeTodoist()
    todoist.failures["create_task:Essay 1"] = PlanLimitReached("Todoist POST /tasks failed: HTTP 403")
    canvas = FakeCanvasSource([assignment("1001", title="Essay 1"), assignment("1002", title="Quiz 1")])

    result = run_sync(canvas, todoist, None, Config(), NOW)

    assert todoist.task_titled("Quiz 1")
    assert set(result.state.assignments) == {"1002"}
    assert str(result.summary) == "created 1, updated 0, skipped 0, errors 1"
    warnings = [r.getMessage() for r in caplog.records if r.levelname == "WARNING"]
    assert any("Essay 1" in m and "plan limit" in m.lower() for m in warnings)


def test_plan_limit_on_section_create_is_a_warning_and_the_run_continues(caplog):
    todoist = FakeTodoist()
    todoist.failures["create_section:MATHS 108"] = PlanLimitReached("Todoist POST /sections failed: HTTP 403")
    canvas = FakeCanvasSource([
        assignment("1001", course_id="88", course_code="MATHS 108", title="Quiz 2"),
        assignment("1002", title="Essay 1"),
    ])

    result = run_sync(canvas, todoist, None, Config(), NOW)

    assert todoist.task_titled("Essay 1")
    assert set(result.state.assignments) == {"1002"}
    assert "88" not in result.state.courses
    assert result.summary.errors == 1
    warnings = [r.getMessage() for r in caplog.records if r.levelname == "WARNING"]
    assert any("Quiz 2" in m and "plan limit" in m.lower() for m in warnings)


def test_assignment_held_back_by_plan_limit_is_created_on_the_next_run():
    todoist = FakeTodoist()
    todoist.failures["create_task:Essay 1"] = PlanLimitReached("Todoist POST /tasks failed: HTTP 403")
    canvas = FakeCanvasSource([assignment()])
    first = run_sync(canvas, todoist, None, Config(), NOW)
    todoist.failures.clear()

    second = run_sync(canvas, todoist, first.state, Config(), NOW)

    assert second.state.assignments["1001"].task_id == todoist.task_titled("Essay 1").id
    assert second.summary.created == 1


def test_failure_creating_one_task_is_logged_and_the_rest_are_synced(caplog):
    todoist = FakeTodoist()
    todoist.failures["create_task:Quiz 1"] = TodoistError("Todoist POST /tasks failed: HTTP 400")
    canvas = FakeCanvasSource([
        assignment("1001", title="Essay 1"),
        assignment("1002", title="Quiz 1"),
        assignment("1003", title="Lab 1"),
    ])

    result = run_sync(canvas, todoist, None, Config(), NOW)

    assert set(result.state.assignments) == {"1001", "1003"}
    assert str(result.summary) == "created 2, updated 0, skipped 0, errors 1"
    errors = [r.getMessage() for r in caplog.records if r.levelname == "ERROR"]
    assert any("Quiz 1" in m and "HTTP 400" in m for m in errors)


def test_failure_updating_one_task_keeps_its_old_state_and_the_rest_are_updated():
    todoist = FakeTodoist()
    state = synced(todoist, assignment("1001", title="Essay 1"), assignment("1002", title="Quiz 1"))
    todoist.failures[f"update_task:{todoist.task_titled('Essay 1').id}"] = TodoistError("HTTP 500")
    canvas = FakeCanvasSource([
        assignment("1001", title="Essay 1", due=NEW_DUE),
        assignment("1002", title="Quiz 1", due=NEW_DUE),
    ])

    result = run_sync(canvas, todoist, state, Config(), LATER)

    assert result.state.assignments["1001"].canvas_due == datetime(2026, 10, 10, 10, 59, tzinfo=timezone.utc)
    assert result.state.assignments["1002"].canvas_due == NEW_DUE
    assert todoist.task_titled("Quiz 1").due == NEW_DUE
    assert str(result.summary) == "created 0, updated 1, skipped 0, errors 1"


@pytest.mark.parametrize(
    ("feed_error", "todoist_error"),
    [
        (CalendarFeedError("Calendar Feed fetch failed: HTTP 503"), None),
        (CalendarFeedError("Calendar Feed is not a calendar"), None),
        (None, TodoistRejectedToken("Todoist GET /tasks failed: HTTP 401")),
        (None, TodoistError("Todoist GET /tasks failed: HTTP 503")),
    ],
    ids=["feed unreachable", "feed unparseable", "token rejected", "todoist down"],
)
def test_run_that_cannot_read_canvas_or_todoist_fails_and_marks_nothing_missing(feed_error, todoist_error):
    todoist = FakeTodoist()
    state = synced(todoist, assignment())
    canvas = FakeCanvasSource([assignment()])
    canvas.error = feed_error
    if todoist_error is not None:
        todoist.failures["*"] = todoist_error

    with pytest.raises(SyncAborted) as raised:
        run_sync(canvas, todoist, state, Config(), LATER)

    assert raised.value.result.state == state
    assert todoist.writes == []


# -- Retirement ----------------------------------------------------------------


def feed_and_todoist_that_fail_on_any_call() -> tuple[FakeCanvasSource, FakeTodoist]:
    """A feed and a Todoist that fail on any call, so a test can show none was made."""
    canvas = FakeCanvasSource([assignment()])
    canvas.error = AssertionError("Calendar Feed was read")
    todoist = FakeTodoist()
    todoist.failures["*"] = AssertionError("Todoist was called")
    return canvas, todoist


def test_after_the_sync_end_date_the_sync_is_retired_and_calls_nothing(caplog):
    caplog.set_level("INFO")
    canvas, todoist = feed_and_todoist_that_fail_on_any_call()
    state = State()
    # 12:00 UTC on 1 Aug is already midnight on 2 Aug in Auckland (NZST, UTC+12).
    now = datetime(2027, 8, 1, 12, 0, tzinfo=timezone.utc)

    result = run_sync(canvas, todoist, state, Config(sync_end_date=date(2027, 8, 1)), now)

    assert result.retired
    assert result.state == state
    assert str(result.summary) == "created 0, updated 0, skipped 0, errors 0"
    assert "sync retired" in caplog.text.lower()


def test_the_sync_end_date_itself_is_the_last_day_of_work():
    todoist = FakeTodoist()
    # 11:59 UTC on 1 Aug is 23:59 on 1 Aug in Auckland.
    now = datetime(2027, 8, 1, 11, 59, tzinfo=timezone.utc)
    canvas = FakeCanvasSource([assignment(due=datetime(2027, 8, 3, 10, 59, tzinfo=timezone.utc))])

    result = run_sync(canvas, todoist, None, Config(sync_end_date=date(2027, 8, 1)), now)

    assert not result.retired
    assert todoist.task_titled("Essay 1")

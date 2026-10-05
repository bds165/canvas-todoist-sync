from datetime import date, datetime, timezone

import pytest

from canvas_todoist.config import Config
from canvas_todoist.engine import SyncAborted, run_sync
from canvas_todoist.models import Assignment

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


def test_failed_run_still_reports_tasks_already_created():
    todoist = FakeTodoist()
    todoist.fail_creates_after = 1
    canvas = FakeCanvasSource([assignment("1001", title="Essay 1"), assignment("1002", title="Quiz 1")])

    with pytest.raises(SyncAborted) as raised:
        run_sync(canvas, todoist, None, Config(), NOW)

    partial = raised.value.result.state
    assert set(partial.assignments) == {"1001"}
    assert partial.assignments["1001"].task_id == todoist.task_titled("Essay 1").id

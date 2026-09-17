import asyncio
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock

from app.services.task_scheduler import (
    ScheduledTask,
    TaskFrequency,
    TaskScheduler,
    TaskStatus,
    TaskType,
)


def _task(**schedule):
    return ScheduledTask(
        task_id="task_timing_test",
        task_type=TaskType.HOME_SCENARIO,
        name="测试任务",
        description="",
        frequency=TaskFrequency.DAILY,
        next_run_time=datetime(2026, 9, 17, 12, 0, tzinfo=timezone.utc),
        params={"scenario": "home", "_schedule": schedule},
        user_id="user-1",
    )


def test_reminder_is_sent_once_for_each_occurrence():
    scheduler = TaskScheduler()
    scheduler._notify_user = AsyncMock()
    scheduler._sync_task_to_db = AsyncMock()
    task = _task(reminder_enabled=True, reminder_before_minutes=10)
    now = datetime(2026, 9, 17, 11, 55, tzinfo=timezone.utc)

    asyncio.run(scheduler._maybe_send_reminder(task, now))
    asyncio.run(scheduler._maybe_send_reminder(task, now + timedelta(minutes=1)))

    scheduler._notify_user.assert_awaited_once()
    assert task.params["_schedule"]["reminder_sent_for"] == task.next_run_time.isoformat()


def test_deadline_marks_task_expired_and_disables_it():
    scheduler = TaskScheduler()
    scheduler._notify_user = AsyncMock()
    scheduler._sync_task_to_db = AsyncMock()
    task = _task(deadline="2026-09-17T11:00:00+00:00")

    expired = asyncio.run(
        scheduler._handle_deadline(task, datetime(2026, 9, 17, 11, 1, tzinfo=timezone.utc))
    )

    assert expired is True
    assert task.status == TaskStatus.EXPIRED
    assert task.enabled is False
    scheduler._notify_user.assert_awaited_once()


def test_repeat_until_stops_future_occurrences():
    scheduler = TaskScheduler()
    task = _task(repeat_until="2026-09-17T12:01:00+00:00")

    scheduler._update_next_run_time(task)

    assert task.next_run_time is None
    assert task.enabled is False
    assert task.status == TaskStatus.COMPLETED

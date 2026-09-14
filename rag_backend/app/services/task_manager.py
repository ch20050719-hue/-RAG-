"""
定时任务管理器

此文件已废弃，功能已合并到 task_scheduler.py
保留此文件仅为向后兼容，请使用 task_scheduler.py 中的 TaskScheduler 和 TaskManager

使用方式：
    from app.services.task_scheduler import task_scheduler, task_manager, TaskScheduler, TaskManager
    from app.services.task_scheduler import home_scenario_task, device_status_check_task
"""

from app.services.task_scheduler import (
    TaskScheduler,
    TaskManager,
    TaskType,
    TaskFrequency,
    TaskStatus,
    ScheduledTask,
    task_scheduler,
    task_manager,
    home_scenario_task,
    device_status_check_task,
)

__all__ = [
    'TaskScheduler',
    'TaskManager',
    'TaskType',
    'TaskFrequency',
    'TaskStatus',
    'ScheduledTask',
    'task_scheduler',
    'task_manager',
    'home_scenario_task',
    'device_status_check_task',
]

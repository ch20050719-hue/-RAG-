"""
定时任务调度器
提供智能家居设备定时控制和设备状态检查功能

包含两个主要组件：
1. TaskScheduler: 调度器核心，管理定时任务的创建、调度和执行
2. TaskManager: 业务层面的任务配置封装，提供便捷的任务创建方法
"""

import asyncio
import logging
import traceback
import uuid
from dataclasses import dataclass
from typing import Dict, Any, List, Optional, Callable, Set
from datetime import datetime, timedelta, timezone
from enum import Enum

logger = logging.getLogger(__name__)

class TaskType(str, Enum):
    """任务类型"""
    HOME_SCENARIO = "home_scenario"  # 智能家居场景
    DEVICE_STATUS_CHECK = "device_status_check"  # 设备状态检查
    DEVICE_CONTROL = "device_control"  # 单设备控制
    CUSTOM = "custom"  # 自定义任务


class TaskFrequency(str, Enum):
    """执行频率"""
    ONCE = "once"  # 一次性
    DAILY = "daily"  # 每日
    WEEKLY = "weekly"  # 每周
    MONTHLY = "monthly"  # 每月
    QUARTERLY = "quarterly"  # 每季度
    YEARLY = "yearly"  # 每年


class TaskStatus(str, Enum):
    """任务状态"""
    PENDING = "pending"  # 待执行
    RUNNING = "running"  # 执行中
    COMPLETED = "completed"  # 已完成
    FAILED = "failed"  # 失败
    CANCELLED = "cancelled"  # 已取消
    EXPIRED = "expired"  # 已过截止时间


@dataclass
class ScheduledTask:
    """定时任务"""
    task_id: str
    task_type: TaskType
    name: str
    description: str
    frequency: TaskFrequency
    next_run_time: Optional[datetime]
    last_run_time: Optional[datetime] = None
    callback: Optional[Callable] = None
    params: Dict[str, Any] = None
    status: TaskStatus = TaskStatus.PENDING
    enabled: bool = True
    retry_count: int = 0
    max_retries: int = 3
    db_id: Optional[str] = None
    user_id: Optional[str] = None
    tenant_id: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        schedule = dict((self.params or {}).get("_schedule", {}))
        return {
            "task_id": self.task_id,
            "task_type": self.task_type.value,
            "name": self.name,
            "description": self.description,
            "frequency": self.frequency.value,
            "next_run_time": self.next_run_time.isoformat() if self.next_run_time else None,
            "last_run_time": self.last_run_time.isoformat() if self.last_run_time else None,
            "status": self.status.value,
            "enabled": self.enabled,
            "retry_count": self.retry_count,
            "db_id": self.db_id,
            "user_id": self.user_id,
            "tenant_id": self.tenant_id,
            "schedule": schedule,
        }

async def home_scenario_task(params: Dict[str, Any]):
    """拒绝已下线的旧场景任务，避免旧记录绕过版本三模式边界。"""

    del params
    raise ValueError("home_scenario tasks are retired; use manual/automatic mode or device_control")


async def device_status_check_task(params: Dict[str, Any]):
    """检查设备状态并返回快照。"""
    from app.home_automation.device_tools import get_device_service

    devices = get_device_service().list_devices()
    return {"devices": [device.model_dump(mode="json") for device in devices]}


async def device_control_task(params: Dict[str, Any]):
    """按计划控制单个已注册设备，仍经过统一设备服务校验。"""
    from app.home_automation.device_models import DeviceStateValue
    from app.home_automation.device_tools import get_device_service

    device_id = str(params.get("device_id", "")).strip()
    if not device_id:
        raise ValueError("定时设备控制缺少 device_id")
    state = DeviceStateValue(str(params.get("state", "")))
    result = get_device_service().set_switch_state(device_id=device_id, state=state)
    if not result.accepted:
        raise ValueError(result.blocked_reason or result.message or "设备控制未被接受")
    logger.info("智能家居设备定时控制完成: %s=%s", device_id, state.value)
    return result.model_dump(mode="json")


class TaskScheduler:
    """
    定时任务调度器
    
    功能：
    1. 管理定时任务（创建、更新、删除、暂停、恢复）
    2. 按计划执行任务
    3. 任务重试机制
    4. 任务执行日志
    """
    
    def __init__(self):
        self._tasks: Dict[str, ScheduledTask] = {}
        self._task_queue: asyncio.Queue = asyncio.Queue()
        self._running = False
        self._scheduler_task: Optional[asyncio.Task] = None
        self._execution_task: Optional[asyncio.Task] = None
        self._running_tasks: Set[asyncio.Task] = set()
        self._queued_task_ids: Set[str] = set()
        self._execution_history: List[Dict[str, Any]] = []
        logger.info("✅ 定时任务调度器初始化完成")

    @staticmethod
    def _as_utc(value: Any) -> Optional[datetime]:
        """将数据库或 JSON 中的时间统一为带时区的 UTC 时间。"""
        if value is None:
            return None
        if isinstance(value, str):
            value = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc)

    @staticmethod
    def _schedule_options(task: ScheduledTask) -> Dict[str, Any]:
        return dict((task.params or {}).get("_schedule") or {})

    def _update_schedule_options(self, task: ScheduledTask, **updates: Any) -> None:
        """以不可变副本更新 JSONB 中的调度扩展配置。"""
        params = dict(task.params or {})
        params["_schedule"] = {**self._schedule_options(task), **updates}
        task.params = params

    async def _notify_user(
        self,
        task: ScheduledTask,
        notification_type: str,
        title: str,
        message: str,
        priority: str = "medium",
    ) -> None:
        options = self._schedule_options(task)
        channels = options.get("notification_channels") or ["in_app"]
        if "in_app" not in channels or not task.user_id:
            return
        try:
            from app.services.group_chat_service import group_chat_ws_manager

            await group_chat_ws_manager.send_personal_notification(
                str(task.user_id),
                {
                    "notification_type": notification_type,
                    "type": notification_type,
                    "source": "task",
                    "title": title,
                    "message": message,
                    "priority": priority,
                    "task_id": task.task_id,
                    "metadata": {"task_id": task.task_id, "frequency": task.frequency.value},
                },
            )
        except Exception as exc:
            logger.warning("任务通知发送失败 %s: %s", task.task_id, exc, exc_info=True)

    def _occurrence_key(self, task: ScheduledTask) -> Optional[str]:
        next_run = self._as_utc(task.next_run_time)
        return next_run.isoformat() if next_run else None

    async def _maybe_send_reminder(self, task: ScheduledTask, current_time: datetime) -> None:
        """在执行前发送一次提醒，并按执行时间去重。"""
        options = self._schedule_options(task)
        if not options.get("reminder_enabled", False):
            return
        next_run = self._as_utc(task.next_run_time)
        if not next_run or next_run <= current_time:
            return
        reminder_time = self._as_utc(options.get("reminder_time"))
        if reminder_time is None and options.get("reminder_before_minutes") is not None:
            reminder_time = next_run - timedelta(minutes=int(options["reminder_before_minutes"]))
        if reminder_time is None or reminder_time > current_time:
            return
        occurrence_key = self._occurrence_key(task)
        if options.get("reminder_sent_for") == occurrence_key:
            return
        await self._notify_user(
            task,
            "task_reminder",
            f"任务即将执行：{task.name}",
            f"任务“{task.name}”将于 {next_run.astimezone().strftime('%Y-%m-%d %H:%M')} 执行。",
        )
        self._update_schedule_options(task, reminder_sent_for=occurrence_key)
        await self._sync_task_to_db(task)

    async def _handle_deadline(self, task: ScheduledTask, current_time: datetime) -> bool:
        """处理已到截止时间的任务，返回是否应停止本轮调度。"""
        deadline = self._as_utc(self._schedule_options(task).get("deadline"))
        if not deadline or current_time < deadline:
            return False
        task.status = TaskStatus.EXPIRED
        task.enabled = False
        self._update_schedule_options(task, expired_at=current_time.isoformat())
        await self._sync_task_to_db(task)
        await self._notify_user(
            task,
            "task_deadline",
            f"任务已到截止时间：{task.name}",
            f"任务“{task.name}”未在截止时间前执行，已自动停止。",
            priority="high",
        )
        logger.info("任务已过截止时间并停止: %s (%s)", task.name, task.task_id)
        return True

    async def start(self):
        """启动调度器"""
        if self._running:
            logger.warning("⚠️ 调度器已在运行中")
            return

        await self.load_tasks_from_db()
        self._running = True
        logger.info("🚀 定时任务调度器已启动")

        self._scheduler_task = asyncio.create_task(self._scheduler_loop())
        self._execution_task = asyncio.create_task(self._execution_loop())

    async def stop(self):
        """停止调度器"""
        self._running = False
        for loop_task in (self._scheduler_task, self._execution_task):
            if loop_task and not loop_task.done():
                loop_task.cancel()

        await asyncio.gather(
            *(task for task in (self._scheduler_task, self._execution_task) if task),
            return_exceptions=True
        )

        for task in list(self._running_tasks):
            task.cancel()

        if self._running_tasks:
            await asyncio.gather(*self._running_tasks, return_exceptions=True)

        self._scheduler_task = None
        self._execution_task = None
        self._queued_task_ids.clear()
        logger.info("⏹️ 定时任务调度器已停止")

    async def load_tasks_from_db(self) -> int:
        """Load enabled database tasks into the in-memory scheduler."""
        try:
            from sqlalchemy import and_, select
            from app.db.session import AsyncSessionLocal
            from app.models.scheduled_task import ScheduledTask as DBTaskModel

            async with AsyncSessionLocal() as db:
                query = select(DBTaskModel).where(
                    and_(
                        DBTaskModel.enabled.is_(True),
                        DBTaskModel.next_run_time.is_not(None),
                        DBTaskModel.status != TaskStatus.CANCELLED.value
                    )
                )
                result = await db.execute(query)
                db_tasks = result.scalars().all()

            loaded = 0
            for db_task in db_tasks:
                try:
                    task = self._convert_to_dataclass(db_task)
                    self._tasks[task.task_id] = task
                    loaded += 1
                except Exception as exc:
                    logger.error(
                        "Failed to load scheduled task %s: %s",
                        getattr(db_task, "task_id", None),
                        exc,
                        exc_info=True
                    )

            logger.info("Loaded %s scheduled tasks from database", loaded)
            return loaded
        except Exception as e:
            logger.error("Failed to load scheduled tasks from database: %s", e, exc_info=True)
            return 0

    async def _scheduler_loop(self):
        """调度循环"""
        while self._running:
            try:
                current_time = datetime.now(timezone.utc)

                for task_id, task in list(self._tasks.items()):
                    if not task.enabled:
                        continue

                    if task.status in (TaskStatus.RUNNING, TaskStatus.FAILED, TaskStatus.CANCELLED, TaskStatus.EXPIRED) or task_id in self._queued_task_ids:
                        continue

                    if await self._handle_deadline(task, current_time):
                        continue

                    await self._maybe_send_reminder(task, current_time)

                    if task.next_run_time:
                        next_run = task.next_run_time
                        if next_run.tzinfo is None:
                            next_run = next_run.replace(tzinfo=timezone.utc)
                        if next_run <= current_time:
                            logger.info(f"📋 触发定时任务: {task.name} ({task_id})")
                            await self._queue_task(task)

                await asyncio.sleep(60)

            except (ValueError, KeyError) as e:
                logger.error(f"❌ 调度循环数据错误: {e}", exc_info=True)
                await asyncio.sleep(60)
            except (OSError, IOError) as e:
                logger.error(f"❌ 调度循环IO错误: {e}", exc_info=True)
                await asyncio.sleep(60)
            except Exception as e:
                logger.error(f"❌ 调度循环异常: {e}", exc_info=True)
                await asyncio.sleep(60)

    async def _execution_loop(self):
        """任务执行循环"""
        while self._running:
            try:
                task = await asyncio.wait_for(
                    self._task_queue.get(),
                    timeout=1.0
                )

                self._queued_task_ids.discard(task.task_id)
                running_task = asyncio.create_task(self._execute_task(task))
                self._running_tasks.add(running_task)
                running_task.add_done_callback(self._running_tasks.discard)

            except asyncio.TimeoutError:
                continue
            except (ValueError, KeyError) as e:
                logger.error(f"❌ 任务执行循环数据错误: {e}", exc_info=True)
                await asyncio.sleep(1)
            except (OSError, IOError) as e:
                logger.error(f"❌ 任务执行循环IO错误: {e}", exc_info=True)
                await asyncio.sleep(1)
            except Exception as e:
                logger.error(f"❌ 任务执行循环异常: {e}", exc_info=True)
                await asyncio.sleep(1)

    async def _queue_task(self, task: ScheduledTask):
        """将任务加入执行队列"""
        if not isinstance(task, ScheduledTask):
            task = self._convert_to_dataclass(task)

        if task.task_id in self._queued_task_ids or task.status == TaskStatus.RUNNING:
            logger.info("Task already queued or running, skip duplicate enqueue: %s", task.task_id)
            return
        
        task.status = TaskStatus.PENDING
        self._queued_task_ids.add(task.task_id)
        await self._task_queue.put(task)

    async def _execute_task(self, task: ScheduledTask, is_manual: bool = False):
        """执行任务"""
        if not isinstance(task, ScheduledTask):
            task = self._convert_to_dataclass(task)
        
        start_time = datetime.now(timezone.utc)
        task.status = TaskStatus.RUNNING
        await self._sync_task_to_db(task)
        
        execution_record = {
            "task_id": task.task_id,
            "task_name": task.name,
            "start_time": start_time.isoformat(),
            "status": "running"
        }

        try:
            callback_result = None
            if not task.callback:
                raise ValueError(f"No callback registered for task type: {task.task_type}")

            if hasattr(task, 'callback') and task.callback:
                if asyncio.iscoroutinefunction(task.callback):
                    callback_result = await task.callback(task.params or {})
                else:
                    callback_result = task.callback(task.params or {})
            
            task.last_run_time = start_time
            task.status = TaskStatus.COMPLETED
            task.retry_count = 0

            execution_record["status"] = "completed"
            execution_record["end_time"] = datetime.now(timezone.utc).isoformat()
            execution_record["duration"] = (datetime.now(timezone.utc) - start_time).total_seconds()

            self._update_next_run_time(task)

            logger.info(f"✅ 任务执行成功: {task.name} ({task.task_id})")
            
            await self._sync_task_to_db(task)
            
            end_time = datetime.now(timezone.utc)
            result_message = "任务执行成功"
            callback_data = None
            if callback_result is not None:
                result_message = "任务执行成功"
                callback_data = callback_result
            
            await self._save_execution_log_to_db(
                task=task,
                status="completed",
                start_time=start_time,
                end_time=end_time,
                result_data={
                    "success": True,
                    "message": result_message,
                    "data": {
                        "task_name": task.name,
                        "callback_result": callback_data
                    }
                },
                is_manual=is_manual
            )

        except (ValueError, KeyError) as e:
            logger.error(f"❌ 任务执行数据错误: {task.name} ({task.task_id}): {e}", exc_info=True)
            task.status = TaskStatus.FAILED
            await self._sync_task_to_db(task)
            end_time = datetime.now(timezone.utc)
            await self._save_execution_log_to_db(
                task=task,
                status="failed",
                start_time=start_time,
                end_time=end_time,
                error=str(e),
                error_traceback=traceback.format_exc() if hasattr(traceback, 'format_exc') else None,
                is_manual=is_manual
            )
        except (OSError, IOError) as e:
            logger.error(f"❌ 任务执行IO错误: {task.name} ({task.task_id}): {e}", exc_info=True)
            task.status = TaskStatus.FAILED
            await self._sync_task_to_db(task)
            end_time = datetime.now(timezone.utc)
            await self._save_execution_log_to_db(
                task=task,
                status="failed",
                start_time=start_time,
                end_time=end_time,
                error=str(e),
                error_traceback=traceback.format_exc() if hasattr(traceback, 'format_exc') else None,
                is_manual=is_manual
            )
        except Exception as e:
            logger.error(f"❌ 任务执行失败: {task.name} ({task.task_id}): {e}", exc_info=True)

            task.retry_count += 1
            end_time = datetime.now(timezone.utc)

            if task.retry_count < task.max_retries:
                task.status = TaskStatus.PENDING
                logger.info(f"🔄 任务将重试 ({task.retry_count}/{task.max_retries}): {task.name}")
                await asyncio.sleep(60 * (2 ** task.retry_count))
                await self._queue_task(task)
                
                await self._save_execution_log_to_db(
                    task=task,
                    status="failed",
                    start_time=start_time,
                    end_time=end_time,
                    error=str(e),
                    error_traceback=traceback.format_exc() if hasattr(traceback, 'format_exc') else None,
                    is_manual=is_manual
                )
            else:
                task.status = TaskStatus.FAILED
                execution_record["status"] = "failed"
                execution_record["error"] = str(e)

                await self._notify_task_failure(task, e)
                
                await self._save_execution_log_to_db(
                    task=task,
                    status="failed",
                    start_time=start_time,
                    end_time=end_time,
                    error=str(e),
                    error_traceback=traceback.format_exc() if hasattr(traceback, 'format_exc') else None,
                    is_manual=is_manual
                )

            await self._sync_task_to_db(task)

            execution_record["end_time"] = datetime.now(timezone.utc).isoformat()
            execution_record["duration"] = (datetime.now(timezone.utc) - start_time).total_seconds()

        self._execution_history.append(execution_record)

        if len(self._execution_history) > 1000:
            self._execution_history = self._execution_history[-1000:]

    def _update_next_run_time(self, task: ScheduledTask):
        """更新下次执行时间"""
        if task.next_run_time is None:
            task.enabled = False
            return

        next_run_time = task.next_run_time
        if task.frequency == TaskFrequency.ONCE:
            task.next_run_time = None
            task.enabled = False
        elif task.frequency == TaskFrequency.DAILY:
            task.next_run_time = next_run_time + timedelta(days=1)
        elif task.frequency == TaskFrequency.WEEKLY:
            task.next_run_time = next_run_time + timedelta(weeks=1)
        elif task.frequency == TaskFrequency.MONTHLY:
            task.next_run_time = self._add_months(next_run_time, 1)
        elif task.frequency == TaskFrequency.QUARTERLY:
            task.next_run_time = self._add_months(next_run_time, 3)
        elif task.frequency == TaskFrequency.YEARLY:
            task.next_run_time = self._add_months(next_run_time, 12)

        repeat_until = self._as_utc(self._schedule_options(task).get("repeat_until"))
        if repeat_until and task.next_run_time and self._as_utc(task.next_run_time) > repeat_until:
            task.next_run_time = None
            task.enabled = False
            task.status = TaskStatus.COMPLETED

    def _add_months(self, date: datetime, months: int) -> datetime:
        """增加月份"""
        month = date.month - 1 + months
        year = date.year + month // 12
        month = month % 12 + 1
        day = min(date.day, [31, 29 if year % 4 == 0 and (year % 100 != 0 or year % 400 == 0) else 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31][month - 1])
        return date.replace(year=year, month=month, day=day)

    async def _notify_task_failure(self, task: ScheduledTask, error: Exception):
        """通知任务失败"""
        logger.error(f"🚨 任务失败超过最大重试次数: {task.name} ({task.task_id})")

    def create_task(
        self,
        task_id: str,
        task_type: TaskType,
        name: str,
        description: str,
        frequency: TaskFrequency,
        next_run_time: datetime,
        callback: Optional[Callable] = None,
        params: Optional[Dict[str, Any]] = None,
        enabled: bool = True
    ) -> ScheduledTask:
        """创建定时任务"""
        task = ScheduledTask(
            task_id=task_id,
            task_type=task_type,
            name=name,
            description=description,
            frequency=frequency,
            next_run_time=next_run_time,
            callback=callback or self._get_callback_for_type(task_type),
            params=params or {},
            enabled=enabled
        )

        self._tasks[task_id] = task
        logger.info(f"📋 创建定时任务: {name} ({task_id}), 下次执行: {next_run_time}")

        return task

    async def add_task(self, task: ScheduledTask) -> None:
        """添加预创建的定时任务"""
        if not isinstance(task, ScheduledTask):
            task = self._convert_to_dataclass(task)
        
        self._tasks[task.task_id] = task
        logger.info(f"📋 添加定时任务: {task.name} ({task.task_id}), 下次执行: {task.next_run_time}")
    
    def _get_callback_for_type(self, task_type: TaskType) -> Optional[Callable]:
        callbacks = {
            TaskType.HOME_SCENARIO: home_scenario_task,
            TaskType.DEVICE_STATUS_CHECK: device_status_check_task,
            TaskType.DEVICE_CONTROL: device_control_task,
        }
        return callbacks.get(task_type)

    def _convert_to_dataclass(self, db_task) -> ScheduledTask:
        """将数据库模型转换为调度器数据类"""
        
        task_type = TaskType(db_task.task_type) if isinstance(db_task.task_type, str) else db_task.task_type
        frequency = TaskFrequency(db_task.frequency) if isinstance(db_task.frequency, str) else db_task.frequency
        status = TaskStatus(db_task.status) if isinstance(db_task.status, str) else db_task.status
        params = dict(db_task.task_params or {})
        params.setdefault("user_id", str(db_task.user_id))
        params.setdefault("tenant_id", str(db_task.tenant_id))
        
        return ScheduledTask(
            task_id=db_task.task_id,
            task_type=task_type,
            name=db_task.name,
            description=db_task.description or "",
            frequency=frequency,
            next_run_time=db_task.next_run_time,
            last_run_time=db_task.last_run_time,
            callback=self._get_callback_for_type(task_type),
            params=params,
            status=status,
            enabled=db_task.enabled,
            retry_count=db_task.retry_count,
            max_retries=db_task.max_retries,
            db_id=str(db_task.id),
            user_id=str(db_task.user_id),
            tenant_id=str(db_task.tenant_id)
        )

    def get_task(self, task_id: str) -> Optional[ScheduledTask]:
        """获取任务"""
        return self._tasks.get(task_id)

    async def remove_task(self, task_id: str) -> bool:
        """移除任务"""
        if task_id in self._tasks:
            task = self._tasks[task_id]
            logger.info(f"🗑️ 移除定时任务: {task.name} ({task_id})")
            del self._tasks[task_id]
            return True
        return False

    async def run_task_now(self, task: ScheduledTask) -> str:
        """手动立即执行任务"""
        if not isinstance(task, ScheduledTask):
            task = self._convert_to_dataclass(task)
        
        execution_id = f"exec_{uuid.uuid4().hex[:12]}"
        logger.info(f"▶️ 手动执行任务: {task.name} ({task.task_id}), execution_id: {execution_id}")
        
        running_task = asyncio.create_task(self._execute_task(task, is_manual=True))
        self._running_tasks.add(running_task)
        running_task.add_done_callback(self._running_tasks.discard)
        
        return execution_id

    def _coerce_uuid(self, value: Any):
        if value is None or isinstance(value, uuid.UUID):
            return value
        return uuid.UUID(str(value))

    async def _sync_task_to_db(self, task: ScheduledTask):
        """同步任务状态到数据库"""
        try:
            from sqlalchemy import select
            from app.db.session import AsyncSessionLocal
            from app.models.scheduled_task import ScheduledTask as DBTaskModel
            
            async with AsyncSessionLocal() as db:
                query = select(DBTaskModel).where(DBTaskModel.task_id == task.task_id)
                result = await db.execute(query)
                db_task = result.scalar_one_or_none()
                
                if db_task:
                    db_task.last_run_time = task.last_run_time
                    db_task.next_run_time = task.next_run_time
                    db_task.status = task.status.value
                    db_task.enabled = task.enabled
                    db_task.task_params = {
                        key: value
                        for key, value in (task.params or {}).items()
                        if key not in {"user_id", "tenant_id"}
                    }
                    db_task.updated_at = datetime.now(timezone.utc)
                    await db.commit()
                    logger.info(f"💾 已同步任务状态到数据库: {task.name}")
        except Exception as e:
            logger.error(f"❌ 同步任务状态失败: {e}", exc_info=True)

    async def _save_execution_log_to_db(
        self,
        task: ScheduledTask,
        status: str,
        start_time: datetime,
        end_time: datetime,
        error: Optional[str] = None,
        error_traceback: Optional[str] = None,
        result_data: Optional[Dict[str, Any]] = None,
        is_manual: bool = False
    ):
        """保存任务执行日志到数据库"""
        try:
            from app.db.session import AsyncSessionLocal
            from app.models.scheduled_task import TaskExecutionLog
            
            async with AsyncSessionLocal() as db:
                duration_seconds = int((end_time - start_time).total_seconds())
                
                execution_log = TaskExecutionLog(
                    task_id=task.task_id,
                    scheduled_task_id=self._coerce_uuid(task.db_id),
                    user_id=self._coerce_uuid(task.user_id),
                    tenant_id=task.tenant_id,
                    task_type=task.task_type.value if hasattr(task.task_type, 'value') else str(task.task_type),
                    start_time=start_time,
                    end_time=end_time,
                    duration_seconds=duration_seconds,
                    status=status,
                    result=result_data,
                    error_message=error,
                    error_traceback=error_traceback,
                    execution_type="manual" if is_manual else "scheduled",
                    triggered_manually=is_manual,
                    created_at=datetime.now(timezone.utc)
                )
                
                db.add(execution_log)
                await db.commit()
                
                log_status = "成功" if status == "completed" else "失败"
                logger.info(f"📝 已保存执行日志到数据库: {task.name} - {log_status} (耗时: {duration_seconds}s)")
                
        except Exception as e:
            logger.error(f"❌ 保存执行日志失败: {e}", exc_info=True)

    def list_tasks(
        self,
        task_type: Optional[TaskType] = None,
        status: Optional[TaskStatus] = None,
        enabled: Optional[bool] = None
    ) -> List[ScheduledTask]:
        """列出任务"""
        tasks = list(self._tasks.values())

        if task_type:
            tasks = [t for t in tasks if t.task_type == task_type]

        if status:
            tasks = [t for t in tasks if t.status == status]

        if enabled is not None:
            tasks = [t for t in tasks if t.enabled == enabled]

        return tasks

    def update_task(
        self,
        task_id: str,
        enabled: Optional[bool] = None,
        next_run_time: Optional[datetime] = None,
        params: Optional[Dict[str, Any]] = None
    ) -> bool:
        """更新任务"""
        task = self._tasks.get(task_id)
        if not task:
            return False

        if enabled is not None:
            task.enabled = enabled

        if next_run_time:
            task.next_run_time = next_run_time

        if params:
            task.params.update(params)

        logger.info(f"✏️ 更新定时任务: {task.name} ({task_id})")
        return True

    def delete_task(self, task_id: str) -> bool:
        """删除任务"""
        if task_id in self._tasks:
            task = self._tasks.pop(task_id)
            logger.info(f"🗑️ 删除定时任务: {task.name} ({task_id})")
            return True
        return False

    def pause_task(self, task_id: str) -> bool:
        """暂停任务"""
        return self.update_task(task_id, enabled=False)

    def resume_task(self, task_id: str) -> bool:
        """恢复任务"""
        return self.update_task(task_id, enabled=True)

    def get_execution_history(
        self,
        task_id: Optional[str] = None,
        limit: int = 100
    ) -> List[Dict[str, Any]]:
        """获取执行历史"""
        if task_id:
            history = [h for h in self._execution_history if h["task_id"] == task_id]
        else:
            history = self._execution_history

        return history[-limit:]

    async def execute_task_now(self, task_id: str) -> bool:
        """立即执行任务"""
        task = self._tasks.get(task_id)
        if not task:
            return False

        await self._queue_task(task)
        logger.info(f"🚀 立即执行任务: {task.name} ({task_id})")
        return True


task_scheduler = TaskScheduler()


class TaskManager:
    """任务管理器 - 业务层面的任务配置封装"""

    def __init__(self):
        logger.info("✅ 任务管理器初始化完成")

    def setup_home_scenario(
        self,
        tenant_id: str,
        user_id: str,
        scenario: str,
        run_at: datetime,
    ) -> str:
        """拒绝创建已下线的旧场景任务。"""

        del tenant_id, user_id, scenario, run_at
        raise ValueError("home_scenario tasks are retired; use device_control")

    def setup_device_status_check(
        self,
        tenant_id: str,
        user_id: str,
        frequency: TaskFrequency = TaskFrequency.DAILY,
    ) -> str:
        """设置智能家居设备状态检查任务。"""
        task_id = f"device_status_check_{tenant_id}"
        next_run = datetime.now() + timedelta(days=1)
        task_scheduler.create_task(
            task_id=task_id,
            task_type=TaskType.DEVICE_STATUS_CHECK,
            name="智能家居设备状态检查",
            description=f"定期检查租户 {tenant_id} 的设备状态",
            frequency=frequency,
            next_run_time=next_run,
            callback=device_status_check_task,
            params={"tenant_id": tenant_id, "user_id": user_id},
            enabled=True,
        )
        return task_id

    def list_tenant_tasks(self, tenant_id: str):
        """列出租户的所有任务"""
        all_tasks = task_scheduler.list_tasks()

        tenant_tasks = [
            task for task in all_tasks
            if task.params and task.params.get("tenant_id") == tenant_id
        ]

        return {
            "tenant_id": tenant_id,
            "tasks": [task.to_dict() for task in tenant_tasks],
            "total_count": len(tenant_tasks)
        }

    def cancel_tenant_tasks(self, tenant_id: str):
        """取消租户的所有任务"""
        all_tasks = task_scheduler.list_tasks()

        cancelled = []
        for task in all_tasks:
            if task.params and task.params.get("tenant_id") == tenant_id:
                task_scheduler.delete_task(task.task_id)
                cancelled.append(task.task_id)

        logger.info(f"✅ 已取消{len(cancelled)}个租户任务: {tenant_id}")
        return cancelled


task_manager = TaskManager()

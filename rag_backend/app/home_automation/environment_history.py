"""环境快照的短期历史缓存。"""

from datetime import datetime, timedelta, timezone

from .device_models import EnvironmentSnapshot


class EnvironmentHistoryService:
    """保留最近一段时间的环境快照，不落盘、不改变既有快照。"""

    def __init__(self, max_samples: int = 120) -> None:
        if max_samples < 1:
            raise ValueError("max_samples must be at least 1")
        self._max_samples = max_samples
        self._snapshots: tuple[EnvironmentSnapshot, ...] = ()

    def append(self, snapshot: EnvironmentSnapshot) -> None:
        """追加快照，并将缓存限制在最近的 max_samples 条。"""

        self._snapshots = (*self._snapshots, snapshot)[-self._max_samples :]

    def list_snapshots(
        self,
        room: str | None = None,
        minutes: int = 10,
        now: datetime | None = None,
    ) -> list[EnvironmentSnapshot]:
        """按房间和时间窗口返回从旧到新的快照。"""

        if minutes < 1 or minutes > 1440:
            raise ValueError("minutes must be between 1 and 1440")
        current_time = _as_utc(now or datetime.now(timezone.utc))
        cutoff = current_time - timedelta(minutes=minutes)
        return [
            snapshot
            for snapshot in self._snapshots
            if (room is None or snapshot.room == room)
            and _as_utc(snapshot.generated_at) >= cutoff
            and _as_utc(snapshot.generated_at) <= current_time
        ]


def _as_utc(value: datetime) -> datetime:
    """将时区缺失的时间按 UTC 解释，避免比较时抛出异常。"""

    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


__all__ = ["EnvironmentHistoryService"]

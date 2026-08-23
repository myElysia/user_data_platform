"""安全域仓储接口 — 由基础设施层实现"""

from abc import ABC, abstractmethod


class AuditRepository(ABC):
    """审计日志仓储抽象接口"""

    @abstractmethod
    async def add(self, **event) -> None:
        """写入结构化审计事件"""

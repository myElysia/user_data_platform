import random
import re
import string
from threading import Lock
from typing import Never

from casbin import AsyncEnforcer
from casbin.persist.adapters.asyncio import AsyncAdapter


def validate_password(password: str):
    if len(password) < 8:
        raise ValueError('Password must be at least 8 characters')
    elif not re.search(r'[A-Z]', password):
        raise ValueError('密码中缺少大写字符')
    elif not re.search(r'[a-z]', password):
        raise ValueError('密码中缺少小写字符')
    elif not re.search(r'[0-9]', password):
        raise ValueError('密码中缺少数字')
    elif not re.search(r'[!@#$%^&*_]', password):
        raise ValueError('密码中应该包含特殊字符')


def generate_random_string(length: int) -> str:
    return ''.join(random.choices(string.ascii_letters + string.digits, k=length))


class SystemEnforcer(AsyncEnforcer):
    """
    继承自AsyncEnforcer, 带线程锁而非协程锁,保证线程安全
    """
    _instance: "SystemEnforcer" = None
    _lock: Lock = Lock()

    def __init__(self, adapter: AsyncAdapter, **kwargs):
        super().__init__(**kwargs)
        self.adapter = adapter

    @classmethod
    async def get_instance(cls):
        """
        单例Enforcer, 首次使用需要AsyncEnforcer进行初始化
        """
        if not cls._instance:
            raise RuntimeError("Enforcer not initialized.")
        return cls._instance

    @classmethod
    async def init(cls, adapter: AsyncAdapter, /, **kwargs) -> Never:
        with cls._lock:
            if not cls._instance:
                cls._instance = cls.__new__(cls)
                cls._instance.__init__(adapter, **kwargs)
                await cls._instance.load_policy()
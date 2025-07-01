from asyncio import Lock
from enum import Enum
from typing import Never, Any

from casbin import persist, Model
from casbin.persist.adapters.asyncio import AsyncAdapter
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.local import BaseSettings
from app.local.database import Settings as SessionMaker
from app.models import CasbinRule

session_maker = SessionMaker()

# casbin属性列表
casbin_attrs = ["ptype", *[f"v{i}" for i in range(6)]]


class PtypeEnum(str, Enum):
    Policy = "p"  # Policy Rule, 定义具体访问规则
    Grouping = "g"  # Grouping 角色定义规则


class DBAdapter(AsyncAdapter):
    _lock: Lock = Lock()  # 协程锁保证数据安全

    async def load_policy(self, model: Model) -> Never:
        """
        加载所有数据库策略
        :param model:
        :return:
        """
        async with session_maker.session() as session:
            rules = (await session.exec(select(CasbinRule))).all()

            # 清空模型现有策略
            model.clear_policy()
            # 加载所有数据
            for rule in rules:
                line_data = [value for i in casbin_attrs if (value := getattr(rule, i))]
                line = ", ".join(line_data)
                persist.load_policy_line(line, model)

    async def save_policy(self, model: Model) -> Never:
        """
        保存策略到数据库中,并写入内存.用校验是否可替换的方式来实现减少数据操作
        :param model:
        :return:
        """
        model_policy = await self._extract_policy_from_model(model)

        async with self._lock, session_maker.session() as session:
            db_result = await self._extract_policy_from_db(session)
            db_policy = set(db_result.keys())

            to_add = model_policy - db_policy

            to_delete = db_policy - model_policy

    @staticmethod
    async def _extract_policy_from_model(model: Model) -> set[tuple[Any, Any]]:
        """
        返回模型中已存在的策略
        :param model:
        :return:
        """
        policy_list = [
            (ptype, *rule)
            for sec in [PtypeEnum.Policy.value, PtypeEnum.Grouping.value]
            for ptype, ast in model.model[sec].items() if sec in model.model
            for rule in ast.policy
        ]
        return set(policy_list)

    @staticmethod
    async def _extract_policy_from_db(session: AsyncSession) -> dict[Any, Any]:
        result = {}
        for rule in (await session.exec(select(CasbinRule))).all():
            data = (value for attr in casbin_attrs if (value := getattr(rule, attr)))
            result[data] = rule.id
        return result

    async def add_policy(self, sec, ptype, rule):
        pass

    async def remove_policy(self, sec, ptype, rule):
        pass

    async def remove_filtered_policy(self, sec, ptype, field_index, *field_values):
        pass


class Settings(BaseSettings):
    """
    Security数据类, 实现获取AsyncAdapter等数据安全内容
    """
    CASBIN_CONF: str = 'casbin.conf'

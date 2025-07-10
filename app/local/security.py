from enum import Enum
from typing import Never, Any

from casbin import persist, Model, AsyncEnforcer
from casbin.persist.adapters.asyncio import AsyncAdapter
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.models import CasbinRule
from app.utils.loop import async_func

# casbin属性列表
casbin_attrs = ["ptype", *[f"v{i}" for i in range(6)]]


class PtypeEnum(str, Enum):
    Policy = "p"  # Policy Rule, 定义具体访问规则
    Grouping = "g"  # Grouping 角色定义规则


class DBAdapter(AsyncAdapter):
    session: AsyncSession = None

    def __init__(self, session: AsyncSession):
        super().__init__()
        self.session = session

    async def load_policy(self, model: Model) -> Never:
        """
        加载所有数据库策略
        :param model:
        :return:
        """
        rules = (await self.session.exec(select(CasbinRule))).all()

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

        db_result = await self._extract_policy_from_db(self.session)
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

    async def update_policy(self, sec, pytpe, old_rule, new_rule):
        """
        更新规则
        :param sec:
        :param pytpe:
        :param old_rule:
        :param new_rule:
        :return:
        """
        pass


class Settings:
    """
    Security数据类, 实现获取AsyncAdapter等数据安全内容
    """
    CASBIN_CONF: str = 'casbin.conf'
    _enforcer: AsyncEnforcer = None

    @classmethod
    def get_enforcer(cls, session: AsyncSession) -> AsyncEnforcer:
        """
        获取一个enforcer.需要保证session有上下文
        :param session:
        :return:
        """
        adapter = DBAdapter(session)

        if not cls._enforcer:
            cls._enforcer = AsyncEnforcer(cls.CASBIN_CONF, adapter=adapter)
            cls.load_policy()
        else:
            cls._enforcer.adapter = adapter

        return cls._enforcer

    @classmethod
    @async_func
    def load_policy(cls, async_runner: callable) -> Never:
        """
        初始化策略, 通过开启一个协程循环的方式进行加载
        :return:
        """
        except_ = None
        while (retry := 0) < 3:
            try:
                async_runner(cls._enforcer.load_policy())
            except Exception as e:
                retry += 1
                except_ = e

        if except_:
            raise except_

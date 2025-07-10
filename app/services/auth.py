from casbin import AsyncEnforcer
from sqlmodel.ext.asyncio.session import AsyncSession

from app.local.security import Settings as CasbinFactory
from app.models import (
    CasbinRule
)
from app.services import ModelService


class PolicyService(ModelService[CasbinRule]):
    _enforcer: AsyncEnforcer

    def __init__(self, session: AsyncSession):
        super().__init__(session)
        self._enforcer = CasbinFactory.get_enforcer(session)

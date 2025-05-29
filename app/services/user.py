from fastapi import Depends
from sqlmodel.ext.asyncio.session import AsyncSession

from app.local.database import Settings as Session
from app.models import User
from app.services import BaseService

session_maker = Session()


def get_user_service(session: AsyncSession = Depends(session_maker.depends)) -> "UserService":
    return UserService(session)


class UserService(BaseService[User]):
    ...

from fastapi import APIRouter
from app.services.user import UserService

router = APIRouter(prefix="/v1", )


class UserViewSet:
    @staticmethod
    @router.get("/user")
    async def list():
        return await UserService().query_list()

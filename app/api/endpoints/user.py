from fastapi import APIRouter, Depends

from app.models.response import response_handler
from app.models.user import UserMixin
from app.services.user import UserService

router = APIRouter(prefix="/v1")


@router.get("/user", summary="Get user info")
@response_handler(UserMixin)
async def user_list(user_service: UserService = Depends(UserService)):
    result = await user_service.list()
    return result

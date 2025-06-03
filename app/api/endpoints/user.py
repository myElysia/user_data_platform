from fastapi import APIRouter, Depends

from app.models.response import Response
from app.models.user import UserMixin
from app.services.user import UserService

router = APIRouter(prefix="/v1")


@router.get("/user", summary="Get user info")
async def user_list(user_service: UserService = Depends(UserService)) -> Response[UserMixin]:
    result = await user_service.list()
    return Response[UserMixin](data=result)

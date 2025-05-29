from fastapi import APIRouter, Depends

from app.models.response import Response
from app.models.user import UserMixin
from app.services.user import get_user_service, UserService

router = APIRouter(prefix="/v1")


@router.get("/user", summary="Get user info")
async def user_list(user_service: UserService = Depends(get_user_service)) -> Response[UserMixin]:
    result = await user_service.list()
    return Response[UserMixin](data=result)

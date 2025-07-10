from fastapi import APIRouter, Depends
from starlette.requests import Request

from app.models.response import request_hook
from app.models.user import UserMixin
from app.services.user import UserService

router = APIRouter(prefix="/v1")


@router.get("/user", summary="Get user info")
@request_hook(UserMixin)
async def user_list(request: Request, user_service: UserService = Depends(UserService)):
    result = await user_service.list()
    return result

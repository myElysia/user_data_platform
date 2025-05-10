from fastapi import APIRouter

from app.api.endpoints.user import router as user_router

router = APIRouter(
    prefix="/api",
    tags=["api"],
)

router.include_router(user_router)

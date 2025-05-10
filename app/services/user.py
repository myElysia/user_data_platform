from app.models import User
from app.schemas.user import UserOut
from app.services import BaseService


class UserService(BaseService[UserOut, User]):
    ...

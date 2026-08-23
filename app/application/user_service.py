from app.infrastructure.persistence.models import User
from app.infrastructure.persistence.base import ModelService


class UserService(ModelService[User]):
    ...

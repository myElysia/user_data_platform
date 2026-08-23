from functools import wraps
from typing import (
    TypeVar,
    Generic,
    Type,
    ClassVar,
    get_args,
    get_origin,
    cast,
    Callable,
    Awaitable,
    Any,
)

from fastapi.params import Depends
from sqlalchemy.exc import NoResultFound
from sqlmodel import SQLModel, select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.infrastructure.database import get_db_session

_MODEL = TypeVar('_MODEL', bound=SQLModel)


def atomic(func: Callable[..., Awaitable[Any]]):
    """
    事务装饰器：自动管理 begin/commit/rollback。
    被装饰的方法不再需要手动调用 session.commit()。
    """
    @wraps(func)
    async def wrapper(self, *args, **kwargs):
        async with self.session.begin():
            result = await func(self, *args, **kwargs)
        return result

    return wrapper


class BaseService:
    """
    服务基础类, 实现了session注入
    """
    session: AsyncSession | None = None

    def __init__(self, session: AsyncSession = Depends(get_db_session)) -> None:
        self.session = session


class ModelService(BaseService, Generic[_MODEL]):
    """
    服务模型公共类, 实现了基础的 create/update/delete/select方法
    """
    _model: ClassVar[Type[_MODEL]]

    def __init_subclass__(cls, **kwargs):
        super().__init_subclass__(**kwargs)
        for base in getattr(cls, "__orig_bases__", ()):
            if get_origin(base) is ModelService:
                args = get_args(base)
                if args:
                    cls._model = args[0]
                    return
        raise TypeError(f"{cls.__name__} 必须指定泛型模型参数, 例如: ModelService[User]")

    @property
    def model(self) -> Type[_MODEL]:
        """获取绑定的模型类型"""
        return self._model

    @atomic
    async def create(self, data: _MODEL):
        self.session.add(data)
        await self.session.flush()  # 立即生成 ID
        return data

    @atomic
    async def update(self, data: _MODEL):
        db_data = await self.session.get(self.model, data.id)
        if not db_data:
            raise NoResultFound(f"不存在的操作对象id: {self.model.__name__} - {data.id}")

        for attr, value in data.model_dump(exclude_unset=True).items():
            setattr(db_data, attr, value)

        return data

    @atomic
    async def delete(self, _id: int):
        db_data = await self.session.get(self.model, _id)
        if not db_data:
            raise NoResultFound(f"不存在的操作对象id: {self.model.__name__} - {_id}")

        await self.session.delete(db_data)

    async def get(self, _id: int):
        db_data = await self.session.get(self.model, _id)
        if not db_data:
            raise NoResultFound(f"不存在的操作对象id: {self.model.__name__} - {_id}")

        return cast(_MODEL, db_data)

    async def list(self):
        datas = await self.session.exec(select(self.model))
        return datas.all()

from functools import wraps
from typing import (
    TypeVar,
    Generic,
    Type,
    get_args,
    ClassVar,
    Tuple,
    cast,
    Callable,
    Awaitable,
    Any,
    get_origin
)

from sqlalchemy.exc import NoResultFound
from sqlmodel import SQLModel, select
from sqlmodel.ext.asyncio.session import AsyncSession

_MODEL = TypeVar('_MODEL', bound=SQLModel)


def atomic(func: Callable[..., Awaitable[Any]]):
    @wraps(func)
    async def wrapper(self, *args, **kwargs):
        # 事务已经实现了rollback方法,不需要额外实现
        # 另外, commit 通过session实现了,不需要额外实现
        async with self.session.begin():
            result = await func(self, *args, **kwargs)
            # 在事务内刷新
            if 'data' in kwargs:
                await self.session.refresh(kwargs['data'])
            elif 'data' in locals():
                await self.session.refresh(locals()['data'])
        return result

    return wrapper


class BaseService(Generic[_MODEL]):
    """
    基础的服务公共类, 实现了基础的 create/update/delete/select方法
    """
    __bases__: ClassVar[Tuple[Type[object], ...]]  # 明确类型提示
    __orig_bases__: ClassVar[Tuple[object, ...]]  # 泛型基类信息
    session: AsyncSession | None = None

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    @classmethod
    def _get_generic_args(cls, index: int) -> Type:
        for base in cls.__orig_bases__:
            origin = get_origin(base)
            if origin and issubclass(origin, Generic):
                args = get_args(base)
                if len(args) > index:
                    return args[index]
        raise NotImplementedError("未指定泛型参数")

    @property
    def model(self) -> Type[_MODEL]:
        """获取泛型参数中的模型类型"""
        model_type = self._get_generic_args(0)
        return cast(Type[_MODEL], model_type)

    @atomic
    async def create(self, data: _MODEL):
        self.session.add(data)
        await self.session.flush()  # 立即生成 ID
        db_data = data.model_copy()
        await self.session.commit()
        return db_data

    @atomic
    async def update(self, data: _MODEL):
        db_data = await self.session.get(self.model, data.id)
        if not db_data:
            raise NoResultFound(f"不存在的操作对象id: {self.model.__name__} - {data.id}")

        for attr, value in data.model_dump(exclude_unset=True).items():
            setattr(db_data, attr, value)

        await self.session.commit()
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
        return datas

from typing import (
    TypeVar,
    Dict,
    List,
    Generic,
    Set,
    Type,
    get_args,
    ClassVar,
    Tuple,
    cast,
    Union, Optional, Any
)

from pydantic import BaseModel
from tortoise import Model
from tortoise.exceptions import DoesNotExist
from tortoise.transactions import atomic

_SCHEMA = TypeVar('_SCHEMA', bound=BaseModel)
_MODEL = TypeVar('_MODEL', bound=Model)


class BaseService(Generic[_SCHEMA, _MODEL]):
    __bases__: ClassVar[Tuple[Type[object], ...]]  # 明确类型提示
    __orig_bases__: ClassVar[Tuple[object, ...]]  # 泛型基类信息

    @classmethod
    def _get_generic_args(cls, index: int) -> Type:
        # 获取当前类的泛型参数
        for base in cls.__orig_bases__:  # type: ignore
            if hasattr(base, "__args__"):
                args = get_args(base)
                if len(args) >= index:
                    arg = args[index]
                    if isinstance(arg, type):
                        return arg
        raise NotImplementedError("未指定泛型参数")

    @property
    def schema(self) -> Type[_SCHEMA]:
        """获取泛型参数中的schema类型"""
        schema_type = self._get_generic_args(0)
        return cast(Type[_SCHEMA], schema_type)

    @property
    def model(self) -> Type[_MODEL]:
        """获取泛型参数中的model类型"""
        # 获取当前类的泛型参数
        model_type = self._get_generic_args(1)
        return cast(Type[_MODEL], model_type)

    def exclude_fields(self, *extra) -> Set[str]:
        return set(*extra, *self.prefetch_fields)

    @property
    def prefetch_fields(self) -> Set[str]:
        """获取需要预取的关联字段集合（所有类型共有的字段）"""
        check_fk = ['m2m_fields', 'o2o_fields', 'fk_fields']
        fields_sets = [set(getattr(self.model, field, set())) for field in check_fk]
        return set.intersection(*fields_sets) if fields_sets else set()

    async def query_list(
            self,
            filters: Optional[Dict[str, Any]] = None,
            order_by: Optional[List[str]] = None,
            exclude: Optional[Set[str]] = None,
            limit: Optional[int] = None,
            offset: Optional[int] = None,
    ) -> List[_SCHEMA]:
        queryset = self.model
        if filters:
            queryset = queryset.filter(**filters)
        if order_by:
            queryset = queryset.order_by(*order_by)
        if limit is not None:
            queryset = queryset.limit(limit)
        if offset is not None:
            queryset = queryset.offset(offset)
        objs = await queryset.all().prefetch_related(*self.prefetch_fields)
        return [self.schema.model_validate(obj).model_dump(exclude=exclude) for obj in objs]

    async def query_one(self, filters: Dict[str, any]) -> _SCHEMA:
        queryset = await self.model.filter(**filters).prefetch_related(*self.prefetch_fields).first()
        return self.schema.model_validate(queryset)

    @atomic()
    async def create(self, data: _SCHEMA) -> Union[_SCHEMA, _MODEL]:
        obj = await self.model.create(**data.model_dump(exclude=self.exclude_fields("id")))
        return obj

    @atomic()
    async def update(self, data: _SCHEMA) -> int:
        count = await self.model.filter(id=data.id).update(**data.model_dump(exclude=self.exclude_fields("id")))
        if count == 0:
            raise DoesNotExist(f"No record found for {data}")
        return count

    @atomic()
    async def delete(self, data: list[int]) -> int:
        count = await self.model.filter(id__in=data).delete()
        return count

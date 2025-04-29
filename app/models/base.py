from tortoise import Model, fields


class Base(Model):
    id = fields.IntField(pk=True)

    # 抽象类，不生成表数据
    class Meta:
        abstract = True


class WithTimeBase(Base):
    created_at = fields.DatetimeField(auto_now_add=True)
    updated_at = fields.DatetimeField(auto_now=True)
    deleted_at = fields.DatetimeField(null=True)

    class Meta:
        abstract = True

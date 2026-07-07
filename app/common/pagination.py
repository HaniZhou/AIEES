from sqlalchemy import desc
from sqlmodel import func, select
from sqlmodel.ext.asyncio.session import AsyncSession


async def paginate(
    session: AsyncSession,
    model_cls: type, # ORM 模型类
    page: int, # 当前页码
    size: int = 30,
    filters: list | None = None, # 查询过滤条件列表（where 条件）
    order_col=None, # 排序字段（ORM列对象）
    desc_order: bool = False, # 是否倒序
) -> tuple[list, int]:
    query = select(model_cls)
    count_query = select(func.count()).select_from(model_cls) # SQL COUNT(*)
    if filters:
        query = query.where(*filters)
        count_query = count_query.where(*filters) # 拼接过滤条件
    total = (await session.exec(count_query)).one()
    if order_col:
        query = query.order_by(desc(order_col) if desc_order else order_col)
    query = query.offset((page - 1) * size).limit(size)
    rows = (await session.exec(query)).all()
    return list(rows), total

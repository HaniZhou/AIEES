from sqlalchemy import desc
from sqlmodel import func, select
from sqlmodel.ext.asyncio.session import AsyncSession


async def paginate(
    session: AsyncSession,
    model_cls: type,
    page: int,
    size: int = 30,
    filters: list | None = None,
    order_col=None,
    desc_order: bool = False,
) -> tuple[list, int]:
    query = select(model_cls)
    count_query = select(func.count()).select_from(model_cls)
    if filters:
        query = query.where(*filters)
        count_query = count_query.where(*filters)
    total = (await session.exec(count_query)).one()
    if order_col:
        query = query.order_by(desc(order_col) if desc_order else order_col)
    query = query.offset((page - 1) * size).limit(size)
    rows = (await session.exec(query)).all()
    return list(rows), total

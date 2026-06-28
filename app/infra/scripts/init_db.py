"""数据库建表 + 初始化数据

手动运行: python -m app.infra.scripts.init_db
"""
import asyncio

from sqlmodel import SQLModel

from app.core.database import db
from app.infra.scripts.init_data import init_mock_data


async def create_tables():
    async with db.engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.create_all)


async def seed_data():
    await init_mock_data()


if __name__ == "__main__":
    from app.core.logging import configure_logging
    configure_logging()

    async def main():
        await create_tables()
        print("✓ 数据表创建完成")
        await seed_data()
        print("✓ 初始数据写入完成")

    asyncio.run(main())

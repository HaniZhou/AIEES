from sqlmodel import select

from app.core.config import SecretConfig
from app.core.database import async_session_factory
from app.core.security import get_password_hash
from app.model.models import Admin


async def init_mock_data():
    async with async_session_factory() as session:
        if not (await session.exec(select(Admin).where(Admin.id == "Admin"))).one_or_none():
            session.add(Admin(
                id="Admin",
                username=SecretConfig.ADMIN_NAME,
                hashed_password=get_password_hash(SecretConfig.ADMIN_PASSWORD),
            ))
            await session.commit()

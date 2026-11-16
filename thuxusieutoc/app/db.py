
from pathlib import Path

from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase

from app.config import settings


class Base(DeclarativeBase):
    """Base class cho toàn bộ model của ứng dụng."""
    pass


def ensure_database_directory():
    """
    Tạo thư mục chứa SQLite nếu chưa tồn tại.
    Chỉ áp dụng cho SQLite.
    """
    prefix = "sqlite+aiosqlite:///"

    if settings.database_url.startswith(prefix):
        database_path = settings.database_url[len(prefix):]

        if database_path != ":memory:":
            path = Path(database_path)

            if not path.is_absolute():
                path = Path.cwd() / path

            path.parent.mkdir(parents=True, exist_ok=True)


ensure_database_directory()


engine = create_async_engine(
    settings.database_url,
    echo=False,
    pool_pre_ping=True,
)


AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False,
)


async def get_db():
    """
    Dependency cung cấp database session.
    Tự động đóng session sau khi xử lý xong.
    """
    async with AsyncSessionLocal() as session:
        yield session


async def init_db():
    """
    Tạo các bảng database nếu chưa tồn tại.

    Các model phải được import trước khi gọi hàm này
    để SQLAlchemy nhận diện đầy đủ bảng.
    """
    import app.models  # noqa: F401

    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)


async def close_db():
    """Đóng kết nối database khi ứng dụng dừng."""
    await engine.dispose()

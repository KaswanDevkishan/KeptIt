from collections.abc import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import get_settings

settings = get_settings()
engine_options: dict[str, object] = {"pool_pre_ping": True}
if not settings.database_url.startswith("sqlite"):
    engine_options.update(
        pool_size=5,
        max_overflow=2,
        pool_recycle=300,
        connect_args={"connect_timeout": settings.database_connect_timeout_seconds},
    )
engine = create_engine(settings.database_url, **engine_options)
SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


def get_db() -> Generator[Session, None, None]:
    """Provide a database session for a request and always close it afterward."""
    with SessionLocal() as session:
        yield session

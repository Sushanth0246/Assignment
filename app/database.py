"""Database engine/session setup.

`configure()` lets tests point the app at a temporary database. Always access
`database.SessionLocal` / `database.engine` through the module (not via
`from ... import`) so a re-configure is picked up everywhere.
"""
from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from app.config import settings


class Base(DeclarativeBase):
    pass


engine = None
SessionLocal = None


def configure(url: str) -> None:
    global engine, SessionLocal
    if engine is not None:
        engine.dispose()
    # check_same_thread=False: the request thread and the background worker
    # thread each open their own session, but SQLite needs this flag.
    connect_args = {"check_same_thread": False} if url.startswith("sqlite") else {}
    engine = create_engine(url, connect_args=connect_args)
    SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


def init_db() -> None:
    from app import models  # noqa: F401  (registers tables on Base.metadata)

    Base.metadata.create_all(bind=engine)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


configure(settings.database_url)

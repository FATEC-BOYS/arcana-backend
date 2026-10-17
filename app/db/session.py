from functools import lru_cache

from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session

from app.core.config import get_settings


@lru_cache
def get_engine():
    url = get_settings().database_url
    engine = create_engine(
        url,
        pool_pre_ping=True,
        hide_parameters=True,
        connect_args={"check_same_thread": False} if url.startswith("sqlite") else {},
    )
    if url.startswith("sqlite"):

        @event.listens_for(engine, "connect")
        def foreign_keys(connection, _):
            connection.execute("PRAGMA foreign_keys=ON")

    return engine


def get_session():
    with Session(get_engine()) as session:
        yield session

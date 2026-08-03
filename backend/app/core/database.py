"""Base de dados local (SQLite via SQLAlchemy)."""
from __future__ import annotations

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from app.core import config


class Base(DeclarativeBase):
    pass


engine = create_engine(
    f"sqlite:///{config.db_path()}", connect_args={"check_same_thread": False}
)
SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db() -> None:
    from app.models import db  # noqa: F401 — regista as tabelas

    Base.metadata.create_all(engine)

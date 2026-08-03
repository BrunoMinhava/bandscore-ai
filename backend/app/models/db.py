"""Modelos de base de dados (projetos, páginas, biblioteca)."""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class Project(Base):
    __tablename__ = "projects"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(200))
    composer: Mapped[str] = mapped_column(String(200), default="")
    ensemble: Mapped[str] = mapped_column(String(100), default="banda")
    source_type: Mapped[str] = mapped_column(String(20), default="pdf")  # pdf|foto|scan|partitura
    status: Mapped[str] = mapped_column(String(30), default="novo")
    dir_path: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    pages: Mapped[list[Page]] = relationship(
        back_populates="project", cascade="all, delete-orphan", order_by="Page.index"
    )


class Page(Base):
    __tablename__ = "pages"

    id: Mapped[int] = mapped_column(primary_key=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id"))
    index: Mapped[int] = mapped_column(Integer)
    original_path: Mapped[str] = mapped_column(Text)
    processed_path: Mapped[str] = mapped_column(Text, default="")
    status: Mapped[str] = mapped_column(String(30), default="importada")
    report_json: Mapped[str] = mapped_column(Text, default="{}")

    project: Mapped[Project] = relationship(back_populates="pages")


class LibraryEntry(Base):
    __tablename__ = "library"

    id: Mapped[int] = mapped_column(primary_key=True)
    title: Mapped[str] = mapped_column(String(300))
    composer: Mapped[str] = mapped_column(String(200), default="")
    ensemble: Mapped[str] = mapped_column(String(100), default="banda")  # banda|orquestra|…
    year: Mapped[int | None] = mapped_column(Integer, nullable=True)
    publisher: Mapped[str] = mapped_column(String(200), default="")
    difficulty: Mapped[str] = mapped_column(String(50), default="")
    instruments_json: Mapped[str] = mapped_column(Text, default="[]")
    tags: Mapped[str] = mapped_column(Text, default="")
    project_id: Mapped[int | None] = mapped_column(ForeignKey("projects.id"), nullable=True)

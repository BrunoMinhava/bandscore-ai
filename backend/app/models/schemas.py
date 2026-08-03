"""Esquemas Pydantic da API."""
from __future__ import annotations

import json
from datetime import datetime

from pydantic import BaseModel

from app.core import config
from app.models import db as dbm


class ProjectCreate(BaseModel):
    name: str
    composer: str = ""
    ensemble: str = "banda"
    source_type: str = "pdf"


class PageOut(BaseModel):
    id: int
    index: int
    status: str
    original_url: str
    processed_url: str
    report: dict

    @classmethod
    def from_row(cls, page: dbm.Page) -> PageOut:
        try:
            report = json.loads(page.report_json or "{}")
        except Exception:
            report = {}
        return cls(
            id=page.id,
            index=page.index,
            status=page.status,
            original_url=config.file_url(page.original_path),
            processed_url=config.file_url(page.processed_path) if page.processed_path else "",
            report=report,
        )


class ProjectOut(BaseModel):
    id: int
    name: str
    composer: str
    ensemble: str
    source_type: str
    status: str
    created_at: datetime
    updated_at: datetime
    pages: list[PageOut] = []

    @classmethod
    def from_row(cls, p: dbm.Project, with_pages: bool = True) -> ProjectOut:
        return cls(
            id=p.id,
            name=p.name,
            composer=p.composer,
            ensemble=p.ensemble,
            source_type=p.source_type,
            status=p.status,
            created_at=p.created_at,
            updated_at=p.updated_at,
            pages=[PageOut.from_row(pg) for pg in p.pages] if with_pages else [],
        )


class PreprocessOptions(BaseModel):
    perspective: bool = True
    shadows: bool = True
    denoise: bool = True
    contrast: bool = True
    deskew: bool = True
    split_double_pages: bool = True


class ImportPaths(BaseModel):
    paths: list[str]


class ResolveNote(BaseModel):
    note_id: str
    pitch: str


class NoteUpdate(BaseModel):
    pitch: str | None = None
    duration: float | None = None
    offset: float | None = None
    dynamic: str | None = None
    accidental: str | None = None
    articulations: list[str] | None = None
    voice: int | None = None


class PartUpdate(BaseModel):
    name: str


class NoteCreate(BaseModel):
    part_id: str
    measure_number: int
    pitch: str
    duration: float = 1.0
    offset: float = 0.0
    voice: int = 1


class ExportRequest(BaseModel):
    formats: list[str]
    part_ids: list[str] | None = None
    separate: bool = False


class LibraryEntryIn(BaseModel):
    title: str
    composer: str = ""
    ensemble: str = "banda"
    year: int | None = None
    publisher: str = ""
    difficulty: str = ""
    instruments: list[str] = []
    tags: str = ""
    project_id: int | None = None


class LibraryEntryOut(LibraryEntryIn):
    id: int

    @classmethod
    def from_row(cls, e: dbm.LibraryEntry) -> LibraryEntryOut:
        try:
            instruments = json.loads(e.instruments_json or "[]")
        except Exception:
            instruments = []
        return cls(
            id=e.id, title=e.title, composer=e.composer, ensemble=e.ensemble,
            year=e.year, publisher=e.publisher, difficulty=e.difficulty,
            instruments=instruments, tags=e.tags, project_id=e.project_id,
        )

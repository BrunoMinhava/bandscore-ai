"""Biblioteca interna — pesquisa por compositor, obra, instrumento,
dificuldade, formação, ano e editor."""
from __future__ import annotations

import json

from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.models import db as dbm
from app.models.schemas import LibraryEntryIn


def search(
    db: Session,
    q: str = "",
    composer: str = "",
    instrument: str = "",
    difficulty: str = "",
    ensemble: str = "",
    year: int | None = None,
    publisher: str = "",
) -> list[dbm.LibraryEntry]:
    query = db.query(dbm.LibraryEntry)
    if q:
        like = f"%{q}%"
        query = query.filter(or_(
            dbm.LibraryEntry.title.ilike(like),
            dbm.LibraryEntry.composer.ilike(like),
            dbm.LibraryEntry.tags.ilike(like),
        ))
    if composer:
        query = query.filter(dbm.LibraryEntry.composer.ilike(f"%{composer}%"))
    if instrument:
        query = query.filter(dbm.LibraryEntry.instruments_json.ilike(f"%{instrument}%"))
    if difficulty:
        query = query.filter(dbm.LibraryEntry.difficulty == difficulty)
    if ensemble:
        query = query.filter(dbm.LibraryEntry.ensemble == ensemble)
    if year is not None:
        query = query.filter(dbm.LibraryEntry.year == year)
    if publisher:
        query = query.filter(dbm.LibraryEntry.publisher.ilike(f"%{publisher}%"))
    return query.order_by(dbm.LibraryEntry.title).all()


def upsert_for_project(
    db: Session,
    project: dbm.Project,
    title: str,
    composer: str,
    instruments: list[str],
) -> dbm.LibraryEntry:
    """Regista (ou atualiza) automaticamente a obra reconhecida de um projeto."""
    row = (
        db.query(dbm.LibraryEntry)
        .filter(dbm.LibraryEntry.project_id == project.id)
        .first()
    )
    if row is None:
        row = dbm.LibraryEntry(title=title or project.name)
        db.add(row)
    row.title = title or project.name
    row.composer = composer or project.composer
    row.ensemble = project.ensemble
    row.instruments_json = json.dumps(instruments, ensure_ascii=False)
    row.project_id = project.id
    db.commit()
    db.refresh(row)
    return row


def upsert(db: Session, entry: LibraryEntryIn, entry_id: int | None = None) -> dbm.LibraryEntry:
    row = db.get(dbm.LibraryEntry, entry_id) if entry_id else None
    if row is None:
        row = dbm.LibraryEntry(title=entry.title)
        db.add(row)
    row.title = entry.title
    row.composer = entry.composer
    row.ensemble = entry.ensemble
    row.year = entry.year
    row.publisher = entry.publisher
    row.difficulty = entry.difficulty
    row.instruments_json = json.dumps(entry.instruments, ensure_ascii=False)
    row.tags = entry.tags
    row.project_id = entry.project_id
    db.commit()
    db.refresh(row)
    return row

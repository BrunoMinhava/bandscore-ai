"""Biblioteca interna de obras."""
from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.library import catalog
from app.models.schemas import LibraryEntryIn, LibraryEntryOut

router = APIRouter(prefix="/api/library", tags=["library"])


@router.get("", response_model=list[LibraryEntryOut])
def search_library(
    q: str = "",
    composer: str = "",
    instrument: str = "",
    difficulty: str = "",
    ensemble: str = "",
    year: int | None = None,
    publisher: str = "",
    db: Session = Depends(get_db),
):
    rows = catalog.search(db, q, composer, instrument, difficulty, ensemble, year, publisher)
    return [LibraryEntryOut.from_row(r) for r in rows]


@router.post("", response_model=LibraryEntryOut)
def add_entry(body: LibraryEntryIn, db: Session = Depends(get_db)):
    return LibraryEntryOut.from_row(catalog.upsert(db, body))

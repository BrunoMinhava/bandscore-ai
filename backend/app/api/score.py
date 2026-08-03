"""Acesso e edição da partitura reconhecida (motor musical)."""
from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app import engine
from app.api.projects import get_project_or_404
from app.core.database import get_db
from app.engine import music21_bridge as bridge
from app.engine.model import Measure, NoteEvent, ScoreDoc
from app.engine.navigation import expand_playback_order
from app.exporters.exporter import export_part_list
from app.models.schemas import NoteCreate, NoteUpdate, PartUpdate
from app.pipeline.recognition import confidence, instruments
from app.validation.validator import validate_score

router = APIRouter(prefix="/api/score", tags=["score"])


def _load(db: Session, project_id: int) -> tuple[ScoreDoc, str]:
    project = get_project_or_404(db, project_id)
    doc = engine.load_score(project.dir_path)
    if doc is None:
        raise HTTPException(404, "Este projeto ainda não tem partitura reconhecida")
    return doc, project.dir_path


@router.get("/{project_id}")
def get_score(project_id: int, db: Session = Depends(get_db)):
    doc, _ = _load(db, project_id)
    return {
        "title": doc.title,
        "composer": doc.composer,
        "pages": doc.pages,
        "parts": export_part_list(doc),
        "doubtful_measures": confidence.doubtful_measures(doc),
    }


@router.get("/{project_id}/full")
def get_score_full(project_id: int, db: Session = Depends(get_db)):
    doc, _ = _load(db, project_id)
    return doc


@router.get("/{project_id}/musicxml")
def get_musicxml(project_id: int, part_id: str | None = None, db: Session = Depends(get_db)):
    """Partitura completa ou, com ``part_id``, apenas o papel de um instrumento."""
    doc, dir_path = _load(db, project_id)
    name = f"_preview_{part_id}.musicxml" if part_id else "_preview.musicxml"
    out = Path(dir_path) / "exports" / name
    out.parent.mkdir(exist_ok=True)
    bridge.write_musicxml(doc, out, [part_id] if part_id else None)
    return FileResponse(out, media_type="application/xml", filename="partitura.musicxml")


@router.get("/{project_id}/midi")
def get_midi(project_id: int, db: Session = Depends(get_db)):
    doc, dir_path = _load(db, project_id)
    out = Path(dir_path) / "exports" / "_preview.mid"
    out.parent.mkdir(exist_ok=True)
    bridge.write_midi(doc, out)
    return FileResponse(out, media_type="audio/midi", filename="partitura.mid")


@router.get("/{project_id}/validate")
def validate(project_id: int, db: Session = Depends(get_db)):
    doc, _ = _load(db, project_id)
    return validate_score(doc)


@router.get("/{project_id}/playback-order")
def playback_order(project_id: int, db: Session = Depends(get_db)):
    doc, _ = _load(db, project_id)
    if not doc.parts:
        return {"order": []}
    return {"order": expand_playback_order(doc.parts[0].measures)}


@router.patch("/{project_id}/part/{part_id}")
def update_part(
    project_id: int, part_id: str, body: PartUpdate, db: Session = Depends(get_db)
):
    """Atribui manualmente o instrumento a uma parte (ex.: «Pauta 3» → «Trompete 2»)."""
    doc, dir_path = _load(db, project_id)
    part = doc.get_part(part_id)
    if part is None:
        raise HTTPException(404, "Parte não encontrada")
    part.name = body.name.strip() or part.name
    canonical, voice, _ = instruments.identify(part.name)
    part.canonical_instrument = canonical
    part.voice_number = voice
    part.confidence = 1.0  # atribuição manual é definitiva
    meta = instruments.CANONICAL.get(canonical)
    if meta:
        part.midi_program = meta["midi"]
        part.is_percussion = bool(meta.get("percussion"))
        part.transposition = meta.get("transposition", 0)
    for meas in part.measures:
        for note in meas.notes:
            note.instrument = part.display_name
    engine.save_score(doc, dir_path)
    return {
        "id": part.id,
        "name": part.display_name,
        "canonical": part.canonical_instrument,
        "confidence": part.confidence,
    }


@router.patch("/{project_id}/note/{note_id}")
def update_note(
    project_id: int, note_id: str, body: NoteUpdate, db: Session = Depends(get_db)
):
    doc, dir_path = _load(db, project_id)
    found = doc.find_note(note_id)
    if found is None:
        raise HTTPException(404, "Nota não encontrada")
    _, _, note = found
    for field, value in body.model_dump(exclude_none=True).items():
        setattr(note, field, value)
    note.confidence = 1.0
    engine.save_score(doc, dir_path)
    return note


@router.post("/{project_id}/note")
def add_note(project_id: int, body: NoteCreate, db: Session = Depends(get_db)):
    doc, dir_path = _load(db, project_id)
    part = doc.get_part(body.part_id)
    if part is None:
        raise HTTPException(404, "Parte não encontrada")
    measure = next((m for m in part.measures if m.number == body.measure_number), None)
    if measure is None:
        measure = Measure(number=body.measure_number)
        part.measures.append(measure)
        part.measures.sort(key=lambda m: m.number)
    note = NoteEvent(
        pitch=body.pitch, duration=body.duration, offset=body.offset,
        voice=body.voice, measure_number=body.measure_number,
        instrument=part.display_name,
    )
    measure.notes.append(note)
    engine.save_score(doc, dir_path)
    return note


@router.delete("/{project_id}/note/{note_id}")
def delete_note(project_id: int, note_id: str, db: Session = Depends(get_db)):
    doc, dir_path = _load(db, project_id)
    found = doc.find_note(note_id)
    if found is None:
        raise HTTPException(404, "Nota não encontrada")
    _, measure, note = found
    measure.notes.remove(note)
    engine.save_score(doc, dir_path)
    return {"ok": True}


@router.post("/{project_id}/undo")
def undo(project_id: int, db: Session = Depends(get_db)):
    project = get_project_or_404(db, project_id)
    doc = engine.undo(project.dir_path)
    if doc is None:
        raise HTTPException(400, "Não há mais alterações para desfazer")
    return {"ok": True}

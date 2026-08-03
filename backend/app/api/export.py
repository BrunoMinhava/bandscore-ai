"""Exportação — obra completa ou instrumentos separados."""
from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app import engine
from app.api.projects import get_project_or_404
from app.core import config
from app.core.database import get_db
from app.exporters import exporter
from app.exporters.musescore import MuseScoreNotFound
from app.models.schemas import ExportRequest

router = APIRouter(prefix="/api/export", tags=["export"])


@router.post("/{project_id}")
def export_project(project_id: int, body: ExportRequest, db: Session = Depends(get_db)):
    project = get_project_or_404(db, project_id)
    doc = engine.load_score(project.dir_path)
    if doc is None:
        raise HTTPException(404, "Este projeto ainda não tem partitura reconhecida")
    out_dir = Path(project.dir_path) / "exports"
    try:
        files = exporter.export_score(
            doc, out_dir, body.formats, body.part_ids, body.separate
        )
    except MuseScoreNotFound as e:
        raise HTTPException(424, str(e)) from e
    except ValueError as e:
        raise HTTPException(400, str(e)) from e
    return {
        "files": [
            {"name": f.name, "url": config.file_url(f)} for f in files
        ]
    }

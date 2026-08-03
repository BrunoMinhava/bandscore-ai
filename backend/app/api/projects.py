"""Gestão de projetos."""
from __future__ import annotations

import re
import shutil
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core import config
from app.core.database import get_db
from app.models import db as dbm
from app.models.schemas import ProjectCreate, ProjectOut

router = APIRouter(prefix="/api/projects", tags=["projects"])


def _slug(name: str) -> str:
    return re.sub(r"[^\w\-]+", "-", name.strip().lower()).strip("-")[:60] or "projeto"


def get_project_or_404(db: Session, project_id: int) -> dbm.Project:
    p = db.get(dbm.Project, project_id)
    if p is None:
        raise HTTPException(404, "Projeto não encontrado")
    return p


@router.post("", response_model=ProjectOut)
def create_project(body: ProjectCreate, db: Session = Depends(get_db)):
    p = dbm.Project(
        name=body.name, composer=body.composer,
        ensemble=body.ensemble, source_type=body.source_type,
    )
    db.add(p)
    db.commit()
    db.refresh(p)
    d = config.projects_dir() / f"{p.id:04d}-{_slug(p.name)}"
    (d / "pages").mkdir(parents=True, exist_ok=True)
    (d / "exports").mkdir(parents=True, exist_ok=True)
    p.dir_path = str(d)
    db.commit()
    return ProjectOut.from_row(p)


@router.get("", response_model=list[ProjectOut])
def list_projects(db: Session = Depends(get_db)):
    rows = db.query(dbm.Project).order_by(dbm.Project.updated_at.desc()).all()
    return [ProjectOut.from_row(p, with_pages=False) for p in rows]


@router.get("/recent", response_model=list[ProjectOut])
def recent_projects(db: Session = Depends(get_db)):
    rows = (
        db.query(dbm.Project).order_by(dbm.Project.updated_at.desc()).limit(12).all()
    )
    return [ProjectOut.from_row(p, with_pages=False) for p in rows]


@router.get("/{project_id}", response_model=ProjectOut)
def get_project(project_id: int, db: Session = Depends(get_db)):
    return ProjectOut.from_row(get_project_or_404(db, project_id))


@router.delete("/{project_id}")
def delete_project(project_id: int, db: Session = Depends(get_db)):
    p = get_project_or_404(db, project_id)
    if p.dir_path and Path(p.dir_path).is_dir():
        shutil.rmtree(p.dir_path, ignore_errors=True)
    # a obra permanece na biblioteca (arquivo), apenas desligada do projeto
    db.query(dbm.LibraryEntry).filter(
        dbm.LibraryEntry.project_id == project_id
    ).update({"project_id": None})
    db.delete(p)
    db.commit()
    return {"ok": True}

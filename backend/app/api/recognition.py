"""Reconhecimento OMR e revisão de notas duvidosas."""
from __future__ import annotations

import json
import threading
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app import engine
from app.api.projects import get_project_or_404
from app.core import jobs
from app.core.database import SessionLocal, get_db
from app.exporters.exporter import export_part_list
from app.library import catalog
from app.models import db as dbm
from app.models.schemas import PreprocessOptions, ResolveNote
from app.pipeline.preprocessing import image_quality_problem, preprocess_pages
from app.pipeline.recognition import confidence, recognize_project
from app.pipeline.recognition.audiveris import AudiverisNotFound

router = APIRouter(prefix="/api/recognize", tags=["recognize"])


def _omr_inputs(pages) -> list[Path]:
    """Imagens a entregar ao OMR — uma página dupla contribui com as duas
    metades, pela ordem de leitura."""
    inputs: list[Path] = []
    for page in pages:
        try:
            report = json.loads(page.report_json or "{}")
        except Exception:
            report = {}
        paths = report.get("omr_inputs") or []
        if paths:
            inputs.extend(Path(p) for p in paths)
        else:
            inputs.append(Path(page.processed_path or page.original_path))
    return inputs


@router.post("/{project_id}/start")
def start_recognition(
    project_id: int, options: PreprocessOptions | None = None, db: Session = Depends(get_db)
):
    """Prepara as páginas e reconhece-as, num só passo e em segundo plano.

    Devolve logo o controlo; o progresso consulta-se em /progress.
    """
    project = get_project_or_404(db, project_id)
    if jobs.is_running(project_id):
        raise HTTPException(409, "Este projeto já está a ser processado")
    if not project.pages and not engine.has_score(project.dir_path):
        raise HTTPException(400, "O projeto ainda não tem páginas importadas")

    job = jobs.start(project_id)
    job.plan(max(1, len(project.pages) * 2 + 1))
    opts = options or PreprocessOptions()
    threading.Thread(
        target=_run_pipeline, args=(project_id, opts), daemon=True
    ).start()
    return {"started": True, "pages": len(project.pages)}


@router.get("/{project_id}/progress")
def recognition_progress(project_id: int):
    job = jobs.get(project_id)
    if job is None:
        return {"idle": True}
    return job.snapshot()


def _run_pipeline(project_id: int, options: PreprocessOptions) -> None:
    """Corre em segundo plano: preparar → reconhecer → organizar."""
    job = jobs.get(project_id)
    db = SessionLocal()
    try:
        project = db.get(dbm.Project, project_id)
        pages = list(project.pages)

        if pages:
            job.set_phase("preparar")
            out_dir = Path(project.dir_path) / "processed"
            reports = preprocess_pages(
                [(Path(p.original_path), out_dir) for p in pages],
                options,
                on_page=job.advance,
            )
            for page, report in zip(pages, reports, strict=True):
                page.report_json = json.dumps(report, ensure_ascii=False)
                if "processed_path" in report:
                    page.processed_path = report["processed_path"]
                    page.status = "processada"
                else:
                    page.status = "erro"
            project.status = "processado"
            db.commit()

            inputs = _omr_inputs(pages)
            problems = [p for p in (image_quality_problem(i) for i in inputs[:3]) if p]
            if problems and len(problems) == len(inputs[:3]):
                job.fail(problems[0])
                return

            job.set_phase("reconhecer")
            job.plan(len(pages) + len(inputs) + 1)
            doc = recognize_project(project.dir_path, inputs, on_page=job.advance)
            project.status = "reconhecido"
            db.commit()
        else:
            doc = engine.load_score(project.dir_path)

        job.set_phase("concluir")
        catalog.upsert_for_project(
            db, project, doc.title, doc.composer, [p.display_name for p in doc.parts]
        )
        job.complete({
            "title": doc.title,
            "composer": doc.composer,
            "pages": doc.pages,
            "parts": export_part_list(doc),
            "doubts": len(confidence.doubts(doc)),
            "warning": doc.metadata.get("aviso"),
        })
    except AudiverisNotFound as e:
        job.fail(str(e))
    except Exception as e:
        job.fail(str(e))
    finally:
        db.close()


@router.post("/{project_id}/accept-all")
def accept_all_doubts(project_id: int, db: Session = Depends(get_db)):
    """Aceita todas as leituras duvidosas de uma só vez.

    Sem isto, uma obra com centenas de dúvidas obrigaria a confirmar nota a
    nota; os compassos afetados continuam assinalados no passo Separar.
    """
    project = get_project_or_404(db, project_id)
    doc = engine.load_score(project.dir_path)
    if doc is None:
        raise HTTPException(404, "Ainda não existe reconhecimento para este projeto")
    accepted = confidence.accept_all(doc)
    engine.save_score(doc, project.dir_path)
    return {"accepted": accepted}


@router.get("/{project_id}/doubts")
def list_doubts(project_id: int, db: Session = Depends(get_db)):
    project = get_project_or_404(db, project_id)
    doc = engine.load_score(project.dir_path)
    if doc is None:
        raise HTTPException(404, "Ainda não existe reconhecimento para este projeto")
    return confidence.doubts(doc)


@router.post("/{project_id}/resolve")
def resolve_doubt(project_id: int, body: ResolveNote, db: Session = Depends(get_db)):
    """Aceita ou altera a leitura de uma nota duvidosa."""
    project = get_project_or_404(db, project_id)
    doc = engine.load_score(project.dir_path)
    if doc is None:
        raise HTTPException(404, "Ainda não existe reconhecimento para este projeto")
    found = doc.find_note(body.note_id)
    if found is None:
        raise HTTPException(404, "Nota não encontrada")
    _, _, note = found
    note.pitch = body.pitch
    note.confidence = 1.0
    note.alternatives = []
    engine.save_score(doc, project.dir_path)
    return {"ok": True, "remaining": len(confidence.doubts(doc))}

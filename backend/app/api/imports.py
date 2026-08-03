"""Importação de ficheiros: PDF, imagens, MusicXML, MXL, MSCZ.

Dois caminhos de entrada: caminhos locais (Electron) ou upload multipart
(fallback do navegador). PDFs são rasterizados página a página; ficheiros
de partitura digitais entram diretamente no motor musical.
"""
from __future__ import annotations

import shutil
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, UploadFile
from sqlalchemy.orm import Session

from app import engine
from app.api.projects import get_project_or_404
from app.core import config
from app.core.database import get_db
from app.engine import music21_bridge as bridge
from app.exporters import musescore
from app.library import catalog
from app.models import db as dbm
from app.models.schemas import ImportPaths, ProjectOut
from app.pipeline.recognition import finalize_document

router = APIRouter(prefix="/api/imports", tags=["imports"])

PROBE_DPI = 150
MIN_DPI, MAX_DPI = 200, 600
# O Audiveris rejeita folhas acima de ~5000 px por lado ("Sheet ignored", sem
# erro explícito). Medido: 3509×4963 passa, 4094×5790 é ignorada. Ficamos com
# folga — de nada serve rasterizar num DPI que o motor OMR depois recusa.
MAX_SHEET_PX = 4900

IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".bmp", ".tiff", ".tif"}
SCORE_EXTS = {".musicxml", ".xml", ".mxl", ".mscz"}
ACCEPTED = IMAGE_EXTS | SCORE_EXTS | {".pdf"}


@router.post("/{project_id}/paths", response_model=ProjectOut)
def import_paths(project_id: int, body: ImportPaths, db: Session = Depends(get_db)):
    project = get_project_or_404(db, project_id)
    for raw in body.paths:
        path = Path(raw).expanduser()
        if not path.is_file():
            raise HTTPException(400, f"Ficheiro não encontrado: {raw}")
        _import_file(db, project, path)
    db.commit()
    db.refresh(project)
    return ProjectOut.from_row(project)


@router.post("/{project_id}/upload", response_model=ProjectOut)
async def import_upload(
    project_id: int, files: list[UploadFile], db: Session = Depends(get_db)
):
    project = get_project_or_404(db, project_id)
    inbox = Path(project.dir_path) / "inbox"
    inbox.mkdir(exist_ok=True)
    for f in files:
        dest = inbox / (f.filename or "ficheiro")
        dest.write_bytes(await f.read())
        _import_file(db, project, dest)
    db.commit()
    db.refresh(project)
    return ProjectOut.from_row(project)


def _import_file(db: Session, project: dbm.Project, path: Path) -> None:
    ext = path.suffix.lower()
    if ext not in ACCEPTED:
        raise HTTPException(400, f"Formato não suportado: {ext}")
    pages_dir = Path(project.dir_path) / "pages"
    pages_dir.mkdir(parents=True, exist_ok=True)
    next_index = len(project.pages) + 1

    if ext == ".pdf":
        for i, png in enumerate(_rasterize_pdf(path, pages_dir, start=next_index)):
            db.add(dbm.Page(project_id=project.id, index=next_index + i, original_path=str(png)))
        project.status = "importado"
    elif ext in IMAGE_EXTS:
        dest = pages_dir / f"page-{next_index:03d}{ext}"
        shutil.copy2(path, dest)
        db.add(dbm.Page(project_id=project.id, index=next_index, original_path=str(dest)))
        project.status = "importado"
    else:
        doc = _import_score_file(project, path)
        project.status = "reconhecido"
        catalog.upsert_for_project(
            db, project, doc.title, doc.composer,
            [p.display_name for p in doc.parts],
        )
    db.flush()


def _best_dpi(pdf_path: Path) -> int:
    """Descobre a que resolução a pauta fica com a altura de que o OMR precisa.

    Rasteriza uma página de sondagem, mede a distância entre linhas da pauta e
    extrapola. Vale mais rasterizar o PDF na resolução certa do que ampliar
    depois uma imagem pequena — ampliar interpola pixels, rasterizar acrescenta
    detalhe verdadeiro.
    """
    import fitz
    import numpy as np

    from app.pipeline.preprocessing import TARGET_INTERLINE
    from app.pipeline.preprocessing.steps import binarize, to_gray
    from app.pipeline.recognition.staffs import detect_staves

    try:
        with fitz.open(str(pdf_path)) as doc:
            page = doc[min(1, len(doc) - 1)]  # a 1ª página costuma ser capa
            pix = page.get_pixmap(dpi=PROBE_DPI)
            buf = np.frombuffer(pix.samples, dtype=np.uint8)
            img = buf.reshape(pix.height, pix.width, pix.n)
        staves = detect_staves(binarize(to_gray(img[:, :, :3])))
        if not staves:
            return config.RASTER_DPI
        interline = float(np.median([s["spacing"] for s in staves]))
        if interline <= 1:
            return config.RASTER_DPI
        dpi = round(PROBE_DPI * TARGET_INTERLINE / interline)
        dpi = max(MIN_DPI, min(MAX_DPI, dpi))

        # não ultrapassar o tamanho de folha que o OMR aceita
        longest = max(pix.width, pix.height)
        if longest > 0:
            dpi_limit = round(PROBE_DPI * MAX_SHEET_PX / longest)
            dpi = min(dpi, max(MIN_DPI, dpi_limit))
        return dpi
    except Exception:
        return config.RASTER_DPI


def _rasterize_pdf(pdf_path: Path, pages_dir: Path, start: int) -> list[Path]:
    import fitz  # PyMuPDF

    dpi = _best_dpi(pdf_path)
    out: list[Path] = []
    with fitz.open(str(pdf_path)) as doc:
        for i, page in enumerate(doc):
            pix = page.get_pixmap(dpi=dpi)
            p = pages_dir / f"page-{start + i:03d}.png"
            pix.save(str(p))
            out.append(p)
    return out


def _import_score_file(project: dbm.Project, path: Path):
    """MusicXML/MXL entram diretamente; MSCZ é convertido pelo MuseScore CLI."""
    source = path
    if path.suffix.lower() == ".mscz":
        target = Path(project.dir_path) / "imported.musicxml"
        source = musescore.convert(path, target)[0]
    doc = bridge.load_score_file(source)
    if not doc.title:
        doc.title = project.name
    finalize_document(doc)
    engine.save_score(doc, project.dir_path, snapshot=False)
    return doc

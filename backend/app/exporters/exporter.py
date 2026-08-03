"""Exportação da obra ou de partes separadas.

Formatos suportados: MusicXML, MXL, MIDI diretamente (music21);
PDF, MSCZ, PNG, SVG via MuseScore CLI.
"""
from __future__ import annotations

import re
from pathlib import Path

from app.engine import music21_bridge as bridge
from app.engine.model import Part, ScoreDoc
from app.exporters import musescore

DIRECT_FORMATS = {"musicxml", "mxl", "midi"}
MUSESCORE_FORMATS = {"pdf", "mscz", "png", "svg"}
ALL_FORMATS = DIRECT_FORMATS | MUSESCORE_FORMATS


def _safe_name(name: str) -> str:
    return re.sub(r"[^\w\s\-.]", "", name).strip().replace("  ", " ") or "obra"


def export_score(
    doc: ScoreDoc,
    out_dir: Path,
    formats: list[str],
    part_ids: list[str] | None = None,
    separate: bool = False,
) -> list[Path]:
    """Exporta a obra completa, uma seleção de instrumentos, ou cada
    instrumento em ficheiros individuais (``separate=True``)."""
    out_dir.mkdir(parents=True, exist_ok=True)
    formats = [f.lower() for f in formats if f.lower() in ALL_FORMATS]
    if not formats:
        raise ValueError("Nenhum formato válido pedido")

    selected = [p for p in doc.parts if not part_ids or p.id in part_ids]
    jobs: list[tuple[str, list[str] | None]] = []
    title = _safe_name(doc.title or "obra")
    if separate:
        for part in selected:
            jobs.append((f"{title} - {_safe_name(part.display_name)}", [part.id]))
    else:
        ids = [p.id for p in selected] if part_ids else None
        jobs.append((title, ids))  # obra completa

    produced: list[Path] = []
    for base_name, ids in jobs:
        produced.extend(_export_one(doc, out_dir, base_name, formats, ids))
    return produced


def _export_one(
    doc: ScoreDoc, out_dir: Path, base_name: str, formats: list[str], ids: list[str] | None
) -> list[Path]:
    produced: list[Path] = []
    xml_path = out_dir / f"{base_name}.musicxml"
    bridge.write_musicxml(doc, xml_path, ids)
    if "musicxml" in formats:
        produced.append(xml_path)

    if "mxl" in formats:
        mxl_path = _compress_mxl(xml_path)
        produced.append(mxl_path)

    if "midi" in formats:
        midi_path = out_dir / f"{base_name}.mid"
        bridge.write_midi(doc, midi_path, ids)
        produced.append(midi_path)

    for fmt in formats:
        if fmt in MUSESCORE_FORMATS:
            produced.extend(musescore.convert(xml_path, out_dir / f"{base_name}.{fmt}"))
    return produced


def _compress_mxl(xml_path: Path) -> Path:
    """Empacota MusicXML em MXL (contentor ZIP normalizado)."""
    import zipfile

    mxl_path = xml_path.with_suffix(".mxl")
    container = (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<container><rootfiles>'
        f'<rootfile full-path="{xml_path.name}" '
        'media-type="application/vnd.recordare.musicxml+xml"/>'
        "</rootfiles></container>"
    )
    with zipfile.ZipFile(mxl_path, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("META-INF/container.xml", container)
        z.write(xml_path, xml_path.name)
    return mxl_path


def export_part_list(doc: ScoreDoc) -> list[dict]:
    """Instrumentos encontrados, para o utilizador escolher o que exportar."""
    return [
        {
            "id": p.id,
            "name": p.display_name,
            "raw_name": p.name,
            "canonical": p.canonical_instrument,
            "confidence": p.confidence,
            "measures": len(p.measures),
            "is_percussion": p.is_percussion,
        }
        for p in doc.parts
    ]


def part_summary(part: Part) -> dict:
    return {"id": part.id, "name": part.display_name, "measures": len(part.measures)}

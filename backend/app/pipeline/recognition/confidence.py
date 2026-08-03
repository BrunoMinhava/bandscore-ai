"""Sistema de validação por confiança.

Analisa a partitura reconhecida, marca notas duvidosas com alternativas e
probabilidades, para o utilizador aceitar ou alterar no interface.
"""
from __future__ import annotations

from fractions import Fraction

import music21 as m21

from app.engine.model import Alternative, ScoreDoc
from app.pipeline.recognition.instruments import instrument_range

DOUBT_THRESHOLD = 0.9


def _midi_of(pitch: str) -> int | None:
    try:
        return m21.pitch.Pitch(pitch).midi
    except Exception:
        return None


def _expected_duration(time_signature: str | None) -> float | None:
    if not time_signature or "/" not in time_signature:
        return None
    try:
        num, den = time_signature.split("/")
        return float(Fraction(int(num), int(den)) * 4)
    except Exception:
        return None


def annotate(doc: ScoreDoc) -> ScoreDoc:
    """Atribui níveis de confiança e alternativas às notas duvidosas."""
    from app.validation import cross_staff

    # o desacordo entre pautas é o sinal mais forte de leitura errada
    cross_staff.apply_confidence(doc)

    for part in doc.parts:
        rng = instrument_range(part.canonical_instrument)
        current_ts: str | None = None
        for measure in part.measures:
            if measure.time_signature:
                current_ts = measure.time_signature
            expected = _expected_duration(current_ts)

            # duração real do compasso (voz 1) vs compasso indicado
            v1 = [n for n in measure.notes if n.voice == 1]
            actual = max((n.offset + n.duration for n in v1), default=0.0)
            measure_suspicious = expected is not None and v1 and abs(actual - expected) > 1e-3

            for note in measure.notes:
                if measure_suspicious:
                    note.confidence = min(note.confidence, 0.8)
                if note.is_rest or not note.pitch:
                    continue
                midi = _midi_of(note.pitch)
                if midi is None or rng is None:
                    continue
                low, high = rng
                if midi < low or midi > high:
                    # nota fora do âmbito do instrumento — provável erro de oitava
                    note.confidence = min(note.confidence, 0.55)
                    p = m21.pitch.Pitch(note.pitch)
                    shift = 12 if midi < low else -12
                    oitava_alt = p.octave + (1 if shift > 0 else -1)
                    note.alternatives = [
                        Alternative(pitch=note.pitch, probability=0.55),
                        Alternative(pitch=f"{p.name}{oitava_alt}", probability=0.40),
                    ]
    return doc


def doubtful_measures(doc: ScoreDoc) -> dict[str, list[dict]]:
    """Por parte: compassos que contêm notas abaixo do limiar de confiança."""
    out: dict[str, list[dict]] = {}
    for part in doc.parts:
        rows = []
        for meas in part.measures:
            bad = [n for n in meas.notes if not n.is_rest and n.confidence < DOUBT_THRESHOLD]
            if bad:
                rows.append({
                    "measure": meas.number,
                    "notes": len(bad),
                    "min_confidence": round(min(n.confidence for n in bad), 3),
                })
        if rows:
            out[part.id] = rows
    return out


def accept_all(doc: ScoreDoc) -> int:
    """Aceita todas as leituras duvidosas tal como estão. Devolve o nº aceite."""
    n = 0
    for _, _, note in doc.all_notes():
        if not note.is_rest and note.confidence < DOUBT_THRESHOLD:
            note.confidence = 1.0
            note.alternatives = []
            n += 1
    return n


def doubts(doc: ScoreDoc) -> list[dict]:
    """Lista de notas com confiança abaixo do limiar, para revisão manual."""
    out: list[dict] = []
    for part, measure, note in doc.all_notes():
        if note.is_rest or note.confidence >= DOUBT_THRESHOLD:
            continue
        out.append({
            "note_id": note.id,
            "part": part.display_name,
            "part_id": part.id,
            "measure": measure.number,
            "pitch": note.pitch,
            "confidence": round(note.confidence, 3),
            "alternatives": [
                {"pitch": a.pitch, "probability": round(a.probability, 3)}
                for a in note.alternatives
            ],
        })
    out.sort(key=lambda d: d["confidence"])
    return out

"""Validação cruzada entre pautas.

Numa partitura de maestro todas as pautas são metricamente idênticas: no
mesmo compasso têm a mesma métrica e a mesma duração total. Quando uma pauta
discorda das restantes, o erro é dela — e as outras dizem-nos qual devia ser o
valor correto. É a fonte de verdade mais forte que existe para detetar barras
de compasso que o reconhecimento ótico falhou.
"""
from __future__ import annotations

from collections import Counter
from fractions import Fraction

from pydantic import BaseModel

from app.engine.model import Measure, Part, ScoreDoc

MIN_PARTS = 3          # abaixo disto não há maioria em que confiar
AGREEMENT = 0.6        # fração de pautas que tem de concordar


class MeasureDisagreement(BaseModel):
    measure: int
    part: str
    part_id: str
    actual: float          # duração lida nesta pauta
    expected: float        # duração em que as restantes concordam
    agreeing_parts: int
    total_parts: int
    likely_missing_barlines: int


def measure_duration(meas: Measure, voice: int = 1) -> float:
    notes = [n for n in meas.notes if n.voice == voice] or meas.notes
    if not notes:
        return 0.0
    return max(n.offset + n.duration for n in notes)


def expected_duration(ts: str | None) -> float | None:
    if not ts or "/" not in ts:
        return None
    try:
        num, den = ts.split("/")
        return float(Fraction(int(num), int(den)) * 4)
    except Exception:
        return None


def _consensus(values: list[float]) -> tuple[float, int] | None:
    """Duração em que a maioria das pautas concorda."""
    usable = [round(v, 3) for v in values if v > 0]
    if len(usable) < MIN_PARTS:
        return None
    value, count = Counter(usable).most_common(1)[0]
    if count / len(usable) < AGREEMENT:
        return None
    return value, count


def find_disagreements(doc: ScoreDoc) -> list[MeasureDisagreement]:
    """Compassos em que uma pauta destoa da maioria."""
    if len(doc.parts) < MIN_PARTS:
        return []

    out: list[MeasureDisagreement] = []
    max_measures = max(len(p.measures) for p in doc.parts)
    for index in range(max_measures):
        durations: list[tuple[Part, Measure, float]] = []
        for part in doc.parts:
            if index < len(part.measures):
                meas = part.measures[index]
                durations.append((part, meas, measure_duration(meas)))

        consensus = _consensus([d for _, _, d in durations])
        if consensus is None:
            continue
        expected, agreeing = consensus

        for part, meas, actual in durations:
            if actual <= 0 or abs(actual - expected) <= 1e-3:
                continue
            missing = 0
            if expected > 0 and actual > expected:
                ratio = actual / expected
                if abs(ratio - round(ratio)) < 0.05 and round(ratio) >= 2:
                    missing = round(ratio) - 1
            out.append(MeasureDisagreement(
                measure=meas.number,
                part=part.display_name,
                part_id=part.id,
                actual=round(actual, 3),
                expected=round(expected, 3),
                agreeing_parts=agreeing,
                total_parts=len(durations),
                likely_missing_barlines=missing,
            ))
    return out


def apply_confidence(doc: ScoreDoc) -> int:
    """Baixa a confiança das notas nos compassos em que a pauta destoa."""
    flagged = {(d.part_id, d.measure) for d in find_disagreements(doc)}
    if not flagged:
        return 0
    touched = 0
    for part in doc.parts:
        for meas in part.measures:
            if (part.id, meas.number) not in flagged:
                continue
            for note in meas.notes:
                note.confidence = min(note.confidence, 0.5)
                touched += 1
    return touched


def summary(doc: ScoreDoc) -> dict:
    issues = find_disagreements(doc)
    by_part = Counter(i.part for i in issues)
    return {
        "compassos_em_desacordo": len(issues),
        "pautas_afetadas": len(by_part),
        "piores_pautas": dict(by_part.most_common(5)),
        "barras_em_falta_estimadas": sum(i.likely_missing_barlines for i in issues),
    }

"""Verificação automática antes de exportar.

Confirma durações de compassos, armaduras, ligaduras, repetições, âmbitos
dos instrumentos e produz um relatório final.
"""
from __future__ import annotations

from fractions import Fraction

import music21 as m21
from pydantic import BaseModel

from app.engine.model import ScoreDoc
from app.pipeline.recognition.instruments import instrument_range
from app.validation import cross_staff


class Issue(BaseModel):
    severity: str        # erro | aviso
    type: str
    part: str
    measure: int | None = None
    message: str


class ValidationReport(BaseModel):
    ok: bool
    issues: list[Issue]
    summary: dict


def _expected_duration(ts: str | None) -> float | None:
    if not ts or "/" not in ts:
        return None
    try:
        num, den = ts.split("/")
        return float(Fraction(int(num), int(den)) * 4)
    except Exception:
        return None


def validate_score(doc: ScoreDoc) -> ValidationReport:
    issues: list[Issue] = []

    for part in doc.parts:
        pname = part.display_name
        rng = instrument_range(part.canonical_instrument)
        current_ts: str | None = None
        open_repeat = False
        pending_tie = False

        for meas in part.measures:
            if meas.time_signature:
                current_ts = meas.time_signature
            expected = _expected_duration(current_ts)

            v1 = [n for n in meas.notes if n.voice == 1]
            if expected is not None and v1:
                actual = max(n.offset + n.duration for n in v1)
                if actual - expected > 1e-3:
                    issues.append(Issue(
                        severity="erro", type="compasso_excedido", part=pname,
                        measure=meas.number,
                        message=(
                            f"Compasso {meas.number}: duração {actual:g} excede "
                            f"o compasso {current_ts} ({expected:g})"
                        ),
                    ))
                elif expected - actual > 1e-3:
                    issues.append(Issue(
                        severity="aviso", type="compasso_incompleto", part=pname,
                        measure=meas.number,
                        message=(
                            f"Compasso {meas.number}: duração {actual:g} inferior "
                            f"ao compasso {current_ts} ({expected:g})"
                        ),
                    ))

            if not meas.notes:
                issues.append(Issue(
                    severity="aviso", type="compasso_vazio", part=pname,
                    measure=meas.number,
                    message=f"Compasso {meas.number} sem qualquer nota ou pausa",
                ))

            if meas.repeat_start:
                open_repeat = True
            if meas.repeat_end:
                if not open_repeat and meas.number > 1:
                    # convenção: repetição sem início explícito volta ao começo
                    issues.append(Issue(
                        severity="aviso", type="repeticao_sem_inicio", part=pname,
                        measure=meas.number,
                        message=(
                            f"Barra de repetição no compasso {meas.number} sem "
                            "início explícito (assume-se o início da obra)"
                        ),
                    ))
                open_repeat = False

            for note in meas.notes:
                if note.is_rest or not note.pitch:
                    if pending_tie:
                        pending_tie = False
                    continue
                if note.tie == "start":
                    pending_tie = True
                elif note.tie in ("stop", "continue"):
                    pending_tie = note.tie == "continue"
                if rng is not None:
                    try:
                        midi = m21.pitch.Pitch(note.pitch).midi
                    except Exception:
                        issues.append(Issue(
                            severity="erro", type="nota_invalida", part=pname,
                            measure=meas.number,
                            message=(
                                f"Compasso {meas.number}: altura ilegível "
                                f"«{note.pitch}» (possível erro OCR)"
                            ),
                        ))
                        continue
                    low, high = rng
                    if midi < low - 3 or midi > high + 3:
                        issues.append(Issue(
                            severity="aviso", type="nota_fora_ambito", part=pname,
                            measure=meas.number,
                            message=(
                                f"Compasso {meas.number}: {note.pitch} fora "
                                f"do âmbito de {pname}"
                            ),
                        ))

        if open_repeat:
            issues.append(Issue(
                severity="aviso", type="repeticao_aberta", part=pname,
                message="Início de repetição sem barra de fecho",
            ))

    # comparação entre pautas: a maioria diz qual devia ser a duração
    for d in cross_staff.find_disagreements(doc):
        extra = (
            f" — provável(is) {d.likely_missing_barlines} barra(s) de compasso em falta"
            if d.likely_missing_barlines else ""
        )
        issues.append(Issue(
            severity="erro" if d.likely_missing_barlines else "aviso",
            type="desacordo_entre_pautas", part=d.part, measure=d.measure,
            message=(
                f"Compasso {d.measure}: {d.actual:g} tempos, mas {d.agreeing_parts} "
                f"de {d.total_parts} pautas têm {d.expected:g}{extra}"
            ),
        ))

    doubtful = sum(1 for _, _, n in doc.all_notes() if not n.is_rest and n.confidence < 0.9)
    errors = sum(1 for i in issues if i.severity == "erro")
    return ValidationReport(
        ok=errors == 0,
        issues=issues,
        summary={
            "partes": len(doc.parts),
            "compassos": max((len(p.measures) for p in doc.parts), default=0),
            "notas": sum(1 for _, _, n in doc.all_notes() if not n.is_rest),
            "erros": errors,
            "avisos": sum(1 for i in issues if i.severity == "aviso"),
            "notas_duvidosas": doubtful,
            **cross_staff.summary(doc),
        },
    )

"""Modelo de dados musical interno do BandScore AI.

Representação digital completa da obra, independente de qualquer formato
externo. Serializável em JSON (score.json em cada projeto).
"""
from __future__ import annotations

import uuid
from collections.abc import Iterator

from pydantic import BaseModel, Field


def _new_id() -> str:
    return uuid.uuid4().hex[:12]


class Alternative(BaseModel):
    """Leitura alternativa de uma nota, com probabilidade (nível de confiança)."""

    pitch: str
    probability: float


class TupletInfo(BaseModel):
    """Quiáltera tal como está escrita na partitura original.

    ``actual``/``normal`` são a proporção (3:2 tercina, 6:4 sextina) e
    ``placement`` o lado onde o número aparece impresso — o OMR lê os dois e
    devem ser respeitados em vez de recalculados.
    """

    actual: int = 3
    normal: int = 2
    type: str | None = None        # start | stop | None (nota interior)
    placement: str | None = None   # above | below
    bracket: bool = True


class NoteEvent(BaseModel):
    id: str = Field(default_factory=_new_id)
    is_rest: bool = False
    pitch: str | None = None          # ex.: "G4" — altura + oitava (None = pausa)
    octave: int | None = None
    duration: float = 1.0             # em semínimas (quarterLength)
    offset: float = 0.0               # posição/tempo dentro do compasso
    measure_number: int = 1
    page: int | None = None           # página de origem
    instrument: str = ""
    voice: int = 1                    # voz
    layer: int = 1                    # camada
    dynamic: str | None = None        # dinâmica ativa (p, mf, ff, …)
    articulations: list[str] = Field(default_factory=list)  # staccato, accent, fermata…
    tie: str | None = None            # start | stop | continue (ligadura de prolongação)
    slur: str | None = None           # start | stop (ligadura de expressão)
    wedge: str | None = None          # cresc_start | cresc_stop | dim_start | dim_stop
    accidental: str | None = None     # sharp | flat | natural | …
    tuplet: TupletInfo | None = None  # tercina, sextina, quintina…
    confidence: float = 1.0
    alternatives: list[Alternative] = Field(default_factory=list)


class Measure(BaseModel):
    number: int
    time_signature: str | None = None      # ex.: "4/4"
    key_signature: int | None = None       # nº de sustenidos (negativo = bemóis)
    clef: str | None = None                # G2 | F4 | C3 | …
    tempo_bpm: float | None = None
    tempo_text: str | None = None          # Allegro, Andante, …
    repeat_start: bool = False
    repeat_end: bool = False
    repeat_times: int = 2
    segno: bool = False
    coda: bool = False
    to_coda: bool = False
    fine: bool = False
    direction: str | None = None           # "D.C. al Fine", "D.S. al Coda", …
    texts: list[str] = Field(default_factory=list)
    notes: list[NoteEvent] = Field(default_factory=list)


class Part(BaseModel):
    id: str = Field(default_factory=_new_id)
    name: str                               # nome impresso na partitura
    canonical_instrument: str = ""          # instrumento reconhecido
    voice_number: int | None = None         # Trompete I/II/III
    midi_program: int = 0
    is_percussion: bool = False
    transposition: int = 0                  # meios-tons (escrito → real)
    confidence: float = 1.0
    measures: list[Measure] = Field(default_factory=list)

    @property
    def display_name(self) -> str:
        base = self.canonical_instrument or self.name
        if self.voice_number:
            numeral = "I" * self.voice_number if self.voice_number <= 3 else self.voice_number
            return f"{base} {numeral}"
        return base


class ScoreDoc(BaseModel):
    title: str = ""
    composer: str = ""
    parts: list[Part] = Field(default_factory=list)
    pages: int = 0
    metadata: dict = Field(default_factory=dict)

    def all_notes(self) -> Iterator[tuple[Part, Measure, NoteEvent]]:
        for part in self.parts:
            for measure in part.measures:
                for note in measure.notes:
                    yield part, measure, note

    def find_note(self, note_id: str) -> tuple[Part, Measure, NoteEvent] | None:
        for part, measure, note in self.all_notes():
            if note.id == note_id:
                return part, measure, note
        return None

    def get_part(self, part_id: str) -> Part | None:
        return next((p for p in self.parts if p.id == part_id), None)

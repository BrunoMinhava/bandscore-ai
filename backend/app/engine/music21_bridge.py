"""Ponte entre o modelo interno (ScoreDoc) e music21.

Permite carregar MusicXML/MXL (ex.: exportado pelo Audiveris) para o modelo
interno e reconstruir uma partitura music21 para exportação (MusicXML, MIDI,
e conversões via MuseScore CLI).
"""
from __future__ import annotations

import contextlib
from fractions import Fraction
from itertools import pairwise
from pathlib import Path

import music21 as m21

from app.engine.model import Measure, NoteEvent, Part, ScoreDoc, TupletInfo


def _safe_ql(value: float | None, default: float = 1.0) -> float:
    """Aproxima uma duração ao valor exprimível mais próximo.

    O OMR produz frequentemente durações com ruído de vírgula flutuante
    (ex.: 0.3333333 ou 1.9999998) que o MusicXML não consegue representar.
    Tenta grelhas cada vez mais grossas: tercinas de fusa → … → semínima.
    """
    if value is None or value <= 0:
        return default
    for denom in (12, 8, 4, 2, 1):
        v = Fraction(value).limit_denominator(denom)
        if v <= 0:
            continue
        try:
            if m21.duration.Duration(float(v)).type != "inexpressible":
                return float(v)
        except Exception:
            continue
    return default


def _safe_offset(value: float) -> float:
    """Alinha a posição na grelha rítmica (elimina ruído do OMR)."""
    if value <= 0:
        return 0.0
    return float(Fraction(value).limit_denominator(24))

_DIRECTION_LABELS = [
    ("DaCapoAlCoda", "D.C. al Coda"),
    ("DaCapoAlFine", "D.C. al Fine"),
    ("DaCapo", "D.C."),
    ("DalSegnoAlCoda", "D.S. al Coda"),
    ("DalSegnoAlFine", "D.S. al Fine"),
    ("DalSegno", "D.S."),
]

_ARTICULATION_BUILDERS = {
    "staccato": m21.articulations.Staccato,
    "accent": m21.articulations.Accent,
    "tenuto": m21.articulations.Tenuto,
    "staccatissimo": m21.articulations.Staccatissimo,
    "strong accent": m21.articulations.StrongAccent,
}


# ---------------------------------------------------------------------------
# MusicXML → ScoreDoc
# ---------------------------------------------------------------------------

def load_score_file(path: str | Path) -> ScoreDoc:
    """Lê MusicXML/MXL para o modelo interno completo."""
    s = m21.converter.parse(str(path))
    doc = ScoreDoc()
    if s.metadata is not None:
        doc.title = s.metadata.title or ""
        doc.composer = s.metadata.composer or ""

    for p in s.parts:
        part = Part(name=(p.partName or "Instrumento").strip())
        try:
            inst = p.getInstrument(returnDefault=True)
            if inst is not None and inst.midiProgram is not None:
                part.midi_program = inst.midiProgram
        except Exception:
            pass

        current_dynamic: str | None = None
        for m in p.getElementsByClass(m21.stream.Measure):
            meas = Measure(number=m.number if m.number is not None else len(part.measures) + 1)
            _read_measure_attributes(m, meas)
            current_dynamic = _read_notes(m, meas, part.name, current_dynamic)
            part.measures.append(meas)

        _fix_codas(part)
        doc.parts.append(part)
    return doc


def _read_measure_attributes(m: m21.stream.Measure, meas: Measure) -> None:
    if m.timeSignature is not None:
        meas.time_signature = m.timeSignature.ratioString
    if m.keySignature is not None:
        meas.key_signature = m.keySignature.sharps
    if m.clef is not None and getattr(m.clef, "sign", None):
        meas.clef = f"{m.clef.sign}{m.clef.line or ''}"

    for mm in m.getElementsByClass(m21.tempo.MetronomeMark):
        if mm.number is not None:
            meas.tempo_bpm = float(mm.number)
        if mm.text:
            meas.tempo_text = mm.text

    lb, rb = m.leftBarline, m.rightBarline
    if isinstance(lb, m21.bar.Repeat) and lb.direction == "start":
        meas.repeat_start = True
    if isinstance(rb, m21.bar.Repeat) and rb.direction == "end":
        meas.repeat_end = True
        meas.repeat_times = rb.times or 2

    for rm in m.getElementsByClass(m21.repeat.RepeatMark):
        cls = type(rm).__name__
        if cls == "Segno":
            meas.segno = True
        elif cls == "Coda":
            meas.coda = True
        elif cls == "Fine":
            meas.fine = True
        else:
            for name, label in _DIRECTION_LABELS:
                if cls == name:
                    meas.direction = label
                    break

    for te in m.getElementsByClass(m21.expressions.TextExpression):
        if te.content:
            meas.texts.append(str(te.content))


def _read_notes(
    m: m21.stream.Measure, meas: Measure, instrument: str, current_dynamic: str | None
) -> str | None:
    dynamics = sorted(
        ((float(d.offset), d.value) for d in m.recurse().getElementsByClass(m21.dynamics.Dynamic)),
        key=lambda t: t[0],
    )

    def dyn_at(offset: float) -> str | None:
        nonlocal current_dynamic
        for off, val in dynamics:
            if off <= offset + 1e-6:
                current_dynamic = val
        return current_dynamic

    voices = list(m.voices) or [m]
    for vi, v in enumerate(voices, start=1):
        for el in v.notesAndRests:
            off = float(el.offset)
            common = dict(  # noqa: C408
                duration=float(el.quarterLength),
                offset=off,
                measure_number=meas.number,
                instrument=instrument,
                voice=vi,
                dynamic=dyn_at(off),
            )
            if isinstance(el, m21.note.Rest):
                # as forquilhas de cresc./dim. começam muitas vezes numa pausa
                rest = NoteEvent(is_rest=True, **common)
                _read_spanners(el, rest)
                _read_tuplet(el, rest)
                meas.notes.append(rest)
            elif isinstance(el, m21.note.Note):
                meas.notes.append(_note_event(el, el.pitch, common))
            elif isinstance(el, m21.chord.Chord):
                for pitch in el.pitches:
                    meas.notes.append(_note_event(el, pitch, common))
    return current_dynamic


def _note_event(el, pitch: m21.pitch.Pitch, common: dict) -> NoteEvent:
    ev = NoteEvent(pitch=pitch.nameWithOctave, octave=pitch.octave, **common)
    if pitch.accidental is not None:
        ev.accidental = pitch.accidental.name
    if el.tie is not None:
        ev.tie = el.tie.type
    for a in el.articulations:
        ev.articulations.append(getattr(a, "name", type(a).__name__.lower()))
    for ex in el.expressions:
        if isinstance(ex, m21.expressions.Fermata):
            ev.articulations.append("fermata")
    _read_spanners(el, ev)
    _read_tuplet(el, ev)
    return ev


def _read_tuplet(el, ev: NoteEvent) -> None:
    """Guarda a quiáltera como o OMR a leu — proporção, delimitação e lado."""
    try:
        tuplets = el.duration.tuplets
    except Exception:
        return
    if not tuplets:
        return
    t = tuplets[0]
    ev.tuplet = TupletInfo(
        actual=int(t.numberNotesActual),
        normal=int(t.numberNotesNormal),
        type=t.type if t.type in ("start", "stop") else None,
        placement=getattr(t, "placement", None),
        bracket=bool(getattr(t, "bracket", True)),
    )


def _read_spanners(el, ev: NoteEvent) -> None:
    """Ligaduras de expressão e forquilhas de crescendo/diminuendo.

    Vale para notas e para pausas — o OMR ancora frequentemente o início de
    uma forquilha numa pausa.
    """
    try:
        for sp in el.getSpannerSites():
            if isinstance(sp, m21.spanner.Slur):
                if sp.isFirst(el):
                    ev.slur = "start"
                elif sp.isLast(el):
                    ev.slur = "stop"
            elif isinstance(sp, m21.dynamics.DynamicWedge):
                kind = "cresc" if isinstance(sp, m21.dynamics.Crescendo) else "dim"
                if sp.isFirst(el):
                    ev.wedge = f"{kind}_start"
                elif sp.isLast(el):
                    ev.wedge = f"{kind}_stop"
    except Exception:
        pass


def _fix_codas(part: Part) -> None:
    """O primeiro símbolo de Coda numa obra com salto 'al Coda' é o "To Coda"."""
    coda_measures = [m for m in part.measures if m.coda]
    if len(coda_measures) >= 2:
        coda_measures[0].coda = False
        coda_measures[0].to_coda = True


# ---------------------------------------------------------------------------
# ScoreDoc → music21
# ---------------------------------------------------------------------------

def to_music21(doc: ScoreDoc, part_ids: list[str] | None = None) -> m21.stream.Score:
    sc = m21.stream.Score()
    md = m21.metadata.Metadata()
    md.title = doc.title or "Sem título"
    md.composer = doc.composer or ""
    sc.insert(0, md)

    for part in doc.parts:
        if part_ids and part.id not in part_ids:
            continue
        sc.insert(0, _build_part(part))
    return sc


def _build_part(part: Part) -> m21.stream.Part:
    p = m21.stream.Part()
    p.partName = part.display_name
    inst = m21.instrument.Instrument()
    inst.partName = part.display_name
    inst.midiProgram = part.midi_program
    if part.is_percussion:
        inst.midiChannel = 9
    p.insert(0, inst)

    prev_ts: str | None = None
    prev_ks: int | None = None
    prev_dyn: str | None = None
    open_slur: m21.note.GeneralNote | None = None
    open_wedge: tuple[str, m21.note.GeneralNote] | None = None
    spanners: list[m21.spanner.Spanner] = []
    for meas in part.measures:
        m = m21.stream.Measure(number=meas.number)
        if meas.time_signature and meas.time_signature != prev_ts:
            try:
                m.timeSignature = m21.meter.TimeSignature(meas.time_signature)
                prev_ts = meas.time_signature
            except Exception:
                pass
        if meas.key_signature is not None and meas.key_signature != prev_ks:
            m.insert(0, m21.key.KeySignature(meas.key_signature))
            prev_ks = meas.key_signature
        if meas.clef:
            with contextlib.suppress(Exception):
                m.insert(0, m21.clef.clefFromString(meas.clef))
        if meas.tempo_bpm or meas.tempo_text:
            m.insert(0, m21.tempo.MetronomeMark(number=meas.tempo_bpm, text=meas.tempo_text))
        if meas.repeat_start:
            m.leftBarline = m21.bar.Repeat(direction="start")
        if meas.repeat_end:
            m.rightBarline = m21.bar.Repeat(direction="end", times=meas.repeat_times)
        if meas.direction:
            m.insert(0, m21.expressions.TextExpression(meas.direction))
        for text in meas.texts:
            m.insert(0, m21.expressions.TextExpression(text))

        for offset, _duration, _voice, group in _grouped_events(meas):
            el = _build_element(group)
            safe_off = _safe_offset(offset)
            m.insert(safe_off, el)
            first = group[0]
            if first.dynamic and first.dynamic != prev_dyn:
                m.insert(safe_off, m21.dynamics.Dynamic(first.dynamic))
                prev_dyn = first.dynamic
            # ligaduras de expressão
            if first.slur == "start":
                open_slur = el
            elif first.slur == "stop" and open_slur is not None:
                spanners.append(m21.spanner.Slur(open_slur, el))
                open_slur = None
            # forquilhas de crescendo / diminuendo
            if first.wedge:
                kind, phase = first.wedge.split("_", 1)
                if phase == "start":
                    open_wedge = (kind, el)
                elif open_wedge is not None:
                    cls = (
                        m21.dynamics.Crescendo
                        if open_wedge[0] == "cresc"
                        else m21.dynamics.Diminuendo
                    )
                    spanners.append(cls(open_wedge[1], el))
                    open_wedge = None
        p.append(m)

    for sp in spanners:
        p.insert(0, sp)

    _finalize_notation(p)
    return p


# ---------------------------------------------------------------------------
# Organização da notação — quiálteras, barras de ligação, acidentes
# ---------------------------------------------------------------------------

def _apply_tuplet_info(el, info) -> None:
    """Escreve a quiáltera exatamente como estava na partitura original —
    proporção (3, 6, 5…), colchete e lado do número."""
    if info is None:
        return
    try:
        t = m21.duration.Tuplet(info.actual, info.normal, el.duration.type)
        t.bracket = info.bracket
        t.tupletActualShow = "number"
        t.tupletNormalShow = None
        if info.type in ("start", "stop"):
            t.type = info.type
        if info.placement in ("above", "below"):
            t.placement = info.placement
        el.duration.tuplets = (t,)
    except Exception:
        pass


def _finalize_notation(part: m21.stream.Part) -> None:
    """Deixa a pauta com o aspeto da partitura impressa."""
    inherited: m21.meter.TimeSignature | None = None
    for m in part.getElementsByClass(m21.stream.Measure):
        if m.timeSignature is not None:
            inherited = m.timeSignature
        _beam_measure(m, inherited)
    with contextlib.suppress(Exception):
        part.makeAccidentals(inPlace=True)


def _beat_length(ts: m21.meter.TimeSignature | None) -> float:
    if ts is None:
        return 1.0
    try:
        return float(ts.beatDuration.quarterLength)
    except Exception:
        return 1.0


def normalize_tuplets(doc: ScoreDoc) -> int:
    """Corrige a proporção das quiálteras pela delimitação lida do original.

    Um colchete que abrange 6 notas mas vem marcado 3:2 é uma sextina que o
    motor OMR partiu em duas tercinas — o número impresso deve ser 6. Grupos
    cujo colchete corresponde à proporção ficam intactos.
    """
    fixed = 0
    for part in doc.parts:
        ts: str | None = None
        for meas in part.measures:
            if meas.time_signature:
                ts = meas.time_signature
            groups = _bracket_groups(meas)
            for group in groups:
                if _fix_group_ratio(group):
                    fixed += 1
            fixed += _merge_sextuplets(groups, _beat_from_signature(ts))
    return fixed


def _beat_from_signature(ts: str | None) -> float:
    if not ts:
        return 1.0
    try:
        return float(m21.meter.TimeSignature(ts).beatDuration.quarterLength)
    except Exception:
        return 1.0


def _merge_sextuplets(groups: list[list[NoteEvent]], beat: float) -> int:
    """Junta duas tercinas contíguas numa sextina quando — e só quando —
    ocupam exatamente um tempo.

    O motor OMR lê uma sextina de semicolcheias como duas tercinas de três
    notas, cada uma com meio tempo. Somadas dão um tempo certo, e é isso que
    identifica a sextina. Duas tercinas de colcheias ocupam dois tempos e são
    mesmo duas tercinas — essas não se tocam.
    """
    merged = 0
    for first, second in pairwise(groups):
        if not first or not second or len(first) + len(second) != 6:
            continue
        if first[0].voice != second[0].voice:
            continue
        end = first[-1].offset + first[-1].duration
        if abs(second[0].offset - end) > 1e-4:
            continue
        total = sum(n.duration for n in first + second)
        if abs(total - beat) > 1e-4:
            continue
        start = first[0].offset
        if abs(start / beat - round(start / beat)) > 1e-4:
            continue
        try:
            base = m21.duration.convertTypeToQuarterLength(
                m21.duration.Duration(_safe_ql(first[0].duration)).type
            )
        except Exception:
            continue
        normal = round(total / base) if base > 0 else 0
        if normal < 1:
            continue
        combined = first + second
        for pos, ev in enumerate(combined):
            ev.tuplet.actual = 6
            ev.tuplet.normal = normal
            ev.tuplet.type = "start" if pos == 0 else ("stop" if pos == 5 else None)
        merged += 1
    return merged


def _bracket_groups(meas: Measure) -> list[list[NoteEvent]]:
    """Notas abrangidas por cada colchete de quiáltera (start → stop)."""
    groups: list[list[NoteEvent]] = []
    by_voice: dict[int, list[NoteEvent]] = {}
    for ev in meas.notes:
        if ev.tuplet is not None:
            by_voice.setdefault(ev.voice, []).append(ev)
    for events in by_voice.values():
        events.sort(key=lambda e: e.offset)
        current: list[NoteEvent] = []
        for ev in events:
            if ev.tuplet.type == "start":
                if current:
                    groups.append(current)
                current = [ev]
            elif current:
                current.append(ev)
            if ev.tuplet.type == "stop" and current:
                groups.append(current)
                current = []
        if current:
            groups.append(current)
    return groups


def _fix_group_ratio(group: list[NoteEvent]) -> bool:
    n = len(group)
    if n < 2 or group[0].tuplet is None:
        return False
    if group[0].tuplet.actual == n:
        return False  # o colchete já corresponde à proporção

    total = sum(g.duration for g in group)
    try:
        base = m21.duration.convertTypeToQuarterLength(
            m21.duration.Duration(_safe_ql(group[0].duration)).type
        )
    except Exception:
        return False
    if base <= 0:
        return False
    normal = round(total / base)
    if normal < 1 or abs(normal * base - total) > 1e-4:
        return False

    for ev in group:
        ev.tuplet.actual = n
        ev.tuplet.normal = normal
    return True


def _beam_measure(
    m: m21.stream.Measure, inherited: m21.meter.TimeSignature | None
) -> None:
    """Agrupa as notas em barras de ligação por tempo.

    Compassos que o OMR leu com duração diferente da métrica (tipicamente uma
    barra de compasso falhada) são pautados pela duração real do conteúdo —
    sem isto o music21 devolve zero barras e a pauta sai com todas as figuras
    de colchete solto.
    """
    printed = m.timeSignature
    ts = printed or inherited
    content = float(m.highestTime)
    if ts is None or abs(content - float(ts.barDuration.quarterLength)) > 1e-6:
        try:
            ts = m.bestTimeSignature()
        except Exception:
            return
    m.timeSignature = ts
    try:
        m.makeBeams(inPlace=True)
    except Exception:
        pass
    finally:
        if printed is None:
            for leftover in m.getElementsByClass(m21.meter.TimeSignature):
                m.remove(leftover)
        else:
            m.timeSignature = printed


def _grouped_events(meas: Measure):
    """Agrupa notas simultâneas (mesmo offset/duração/voz) em acordes."""
    groups: dict[tuple, list[NoteEvent]] = {}
    for ev in meas.notes:
        key = (round(ev.offset, 4), round(ev.duration, 4), ev.voice, ev.is_rest)
        groups.setdefault(key, []).append(ev)
    for (offset, duration, voice, _), group in sorted(groups.items()):
        yield offset, duration, voice, group


def _build_element(group: list[NoteEvent]):
    first = group[0]
    ql = _safe_ql(first.duration)
    if first.is_rest:
        el: m21.note.GeneralNote = m21.note.Rest(quarterLength=ql)
    elif len(group) == 1:
        el = m21.note.Note(first.pitch, quarterLength=ql)
    else:
        el = m21.chord.Chord([g.pitch for g in group if g.pitch], quarterLength=ql)

    _apply_tuplet_info(el, first.tuplet)
    if first.tie:
        el.tie = m21.tie.Tie(first.tie)
    for name in first.articulations:
        if name == "fermata":
            el.expressions.append(m21.expressions.Fermata())
        else:
            builder = _ARTICULATION_BUILDERS.get(name)
            if builder:
                el.articulations.append(builder())
    return el


# ---------------------------------------------------------------------------
# Exportação direta
# ---------------------------------------------------------------------------

def write_musicxml(doc: ScoreDoc, out_path: Path, part_ids: list[str] | None = None) -> Path:
    sc = to_music21(doc, part_ids)
    sc.write("musicxml", fp=str(out_path))
    return out_path


def write_midi(doc: ScoreDoc, out_path: Path, part_ids: list[str] | None = None) -> Path:
    sc = to_music21(doc, part_ids)
    sc.write("midi", fp=str(out_path))
    return out_path

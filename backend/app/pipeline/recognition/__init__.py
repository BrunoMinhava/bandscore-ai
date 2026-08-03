"""Orquestração do reconhecimento (OMR).

Fluxo: páginas pré-processadas → Audiveris (OMR principal) → MusicXML →
modelo interno → identificação de instrumentos → análise de confiança →
score.json no diretório do projeto.
"""
from __future__ import annotations

from collections import Counter
from pathlib import Path

from app import engine
from app.engine import music21_bridge as bridge
from app.engine.model import ScoreDoc
from app.pipeline.recognition import audiveris, confidence, instruments, staff_names


def recognize_project(
    project_dir: str | Path, page_inputs: list[Path], on_page=None
) -> ScoreDoc:
    """Reconhece todas as páginas de um projeto e grava o score.json."""
    project_dir = Path(project_dir)
    omr_dir = project_dir / "omr"

    exports = audiveris.run_audiveris(page_inputs, omr_dir, on_page=on_page)
    docs = [bridge.load_score_file(p) for p in exports]
    doc = merge_docs(docs)

    finalize_document(doc)

    # pautas que o OMR deixou sem nome: tentar ler o que está impresso na
    # margem esquerda do primeiro sistema
    if page_inputs and any(p.canonical_instrument.startswith("Pauta") for p in doc.parts):
        try:
            read = staff_names.apply_to_document(doc, page_inputs[0])
            if read:
                confidence.annotate(doc)
        except Exception:
            pass

    doc.pages = max(doc.pages, len(page_inputs))
    engine.save_score(doc, project_dir, snapshot=False)
    return doc


def finalize_document(doc: ScoreDoc) -> None:
    """Identificação de instrumentos + análise de confiança (usado também
    na importação direta de MusicXML/MXL/MSCZ)."""
    bridge.normalize_tuplets(doc)
    for part in doc.parts:
        canonical, voice, conf = instruments.identify(part.name)
        # nomes que não correspondem a nenhum instrumento conhecido são
        # preservados tal como vieram, para o utilizador os atribuir à mão
        part.canonical_instrument = canonical
        part.voice_number = voice
        part.confidence = conf
        meta = instruments.CANONICAL.get(canonical)
        if meta:
            part.midi_program = meta["midi"]
            part.is_percussion = bool(meta.get("percussion"))
            part.transposition = meta.get("transposition", 0)
    confidence.annotate(doc)


# nomes que os motores OMR usam quando a pauta não tem nome impresso
GENERIC_PART_NAMES = {
    "", "voice", "voz", "instrumento", "instrument",
    "part", "music", "unnamed", "piano",
}


def _is_generic(name: str) -> bool:
    n = name.strip().lower()
    return n in GENERIC_PART_NAMES or n.startswith(("p1", "p2", "part "))


def _merge_key(part_name: str, index: int, doc: ScoreDoc) -> str:
    """Chave de correspondência entre páginas: nome impresso quando existe e é
    único; caso contrário a posição da pauta no sistema (comum em partituras
    antigas digitalizadas, onde nenhuma pauta tem nome)."""
    base = part_name.strip().lower()
    if _is_generic(base):
        return f"@pos-{index}"
    duplicates = sum(1 for p in doc.parts if p.name.strip().lower() == base)
    return base if duplicates == 1 else f"{base}@{index}"


def _label_generic_parts(doc: ScoreDoc) -> None:
    """Pautas sem nome ficam «Pauta N» — o utilizador atribui o instrumento
    no passo Separar."""
    for i, part in enumerate(doc.parts, start=1):
        if _is_generic(part.name):
            part.name = f"Pauta {i}"
            for meas in part.measures:
                for note in meas.notes:
                    note.instrument = part.name


def merge_docs(docs: list[ScoreDoc]) -> ScoreDoc:
    """Junta documentos de várias páginas num só, alinhando partes pelo nome
    impresso ou, na falta dele, pela posição da pauta; renumera compassos e
    regista a página de origem de cada nota."""
    if not docs:
        return ScoreDoc()
    if len(docs) == 1:
        doc = docs[0]
        for _, _, note in doc.all_notes():
            if note.page is None:
                note.page = 1
        doc.pages = 1
        _label_generic_parts(doc)
        return doc

    merged = ScoreDoc(title=docs[0].title, composer=docs[0].composer)
    parts_by_key: dict[str, int] = {}

    # Páginas cujo número de pautas destoa das outras foram mal lidas pelo
    # motor OMR. Juntá-las por posição despejaria compassos inventados nas
    # primeiras pautas e corromperia a obra inteira, por isso ficam de fora e
    # são assinaladas.
    counts = Counter(len(d.parts) for d in docs if d.parts)
    expected = counts.most_common(1)[0][0] if counts else 0
    skipped: list[int] = []

    for page_no, doc in enumerate(docs, start=1):
        if expected and len(doc.parts) != expected:
            skipped.append(page_no)
            continue
        for idx, part in enumerate(doc.parts):
            key = _merge_key(part.name, idx, doc)
            if key not in parts_by_key:
                parts_by_key[key] = len(merged.parts)
                merged.parts.append(part.model_copy(update={"measures": []}))
            target = merged.parts[parts_by_key[key]]
            for meas in part.measures:
                for note in meas.notes:
                    note.page = page_no
                target.measures.append(meas)

    # renumeração final contínua
    for part in merged.parts:
        for i, meas in enumerate(part.measures, start=1):
            meas.number = i
            for note in meas.notes:
                note.measure_number = i

    merged.pages = len(docs)
    if skipped:
        merged.metadata["paginas_ignoradas"] = skipped
        merged.metadata["aviso"] = (
            f"{len(skipped)} página(s) foram lidas com um número de pautas diferente "
            f"do resto da obra ({expected}) e foram excluídas para não corromper o "
            f"alinhamento: {', '.join(map(str, skipped))}."
        )
    _label_generic_parts(merged)
    return merged

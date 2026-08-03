"""Identificação e canonicalização de instrumentos.

Reconhece os nomes impressos nas partituras (português, italiano, inglês,
abreviaturas) e mapeia-os para o instrumentário canónico de banda
filarmónica. Instrumentos desconhecidos são preservados tal como aparecem.
"""
from __future__ import annotations

import re
import unicodedata
from difflib import SequenceMatcher

# programa MIDI (General MIDI, 0-based), âmbito real (MIDI), transposição em
# meios-tons (escrito → real; ex.: Clarinete em Sib = -2)
CANONICAL: dict[str, dict] = {
    "Flautim": {"midi": 72, "range": (74, 102), "transposition": 0},
    "Flauta": {"midi": 73, "range": (59, 96), "transposition": 0},
    "Requinta": {"midi": 71, "range": (58, 94), "transposition": 3},
    "Oboé": {"midi": 68, "range": (58, 91), "transposition": 0},
    "Fagote": {"midi": 70, "range": (34, 75), "transposition": 0},
    "Clarinete": {"midi": 71, "range": (50, 94), "transposition": -2},
    "Clarinete Baixo": {"midi": 71, "range": (38, 77), "transposition": -14},
    "Sax Soprano": {"midi": 64, "range": (56, 88), "transposition": -2},
    "Sax Alto": {"midi": 65, "range": (49, 81), "transposition": -9},
    "Sax Tenor": {"midi": 66, "range": (44, 76), "transposition": -14},
    "Sax Barítono": {"midi": 67, "range": (36, 69), "transposition": -21},
    "Trompete": {"midi": 56, "range": (54, 84), "transposition": -2},
    "Cornetim": {"midi": 56, "range": (54, 84), "transposition": -2},
    "Fliscorne": {"midi": 56, "range": (54, 82), "transposition": -2},
    "Trompa": {"midi": 60, "range": (34, 77), "transposition": -7},
    "Trombone": {"midi": 57, "range": (40, 77), "transposition": 0},
    "Bombardino": {"midi": 57, "range": (34, 75), "transposition": 0},
    "Tuba": {"midi": 58, "range": (26, 65), "transposition": 0},
    "Contrabaixo": {"midi": 43, "range": (28, 67), "transposition": 0},
    "Tímpanos": {"midi": 47, "range": (36, 57), "transposition": 0},
    "Percussão": {"midi": 0, "percussion": True},
    "Bateria": {"midi": 0, "percussion": True},
}

ALIASES: dict[str, str] = {
    "piccolo": "Flautim", "picc": "Flautim", "ottavino": "Flautim", "pic": "Flautim",
    "flute": "Flauta", "flauto": "Flauta", "fl": "Flauta", "flt": "Flauta",
    "oboe": "Oboé", "ob": "Oboé", "hautbois": "Oboé",
    "bassoon": "Fagote", "fagotto": "Fagote", "fg": "Fagote", "bsn": "Fagote",
    "clarinet": "Clarinete", "clarinetto": "Clarinete", "cl": "Clarinete",
    "clarinete principal": "Clarinete", "clar": "Clarinete", "clt": "Clarinete",
    "bass clarinet": "Clarinete Baixo", "clarone": "Clarinete Baixo",
    "clarinete baixo": "Clarinete Baixo", "b cl": "Clarinete Baixo",
    "bcl": "Clarinete Baixo", "bass cl": "Clarinete Baixo",
    "eb clarinet": "Requinta", "clarinete requinta": "Requinta", "req": "Requinta",
    "trumpet": "Trompete", "tromba": "Trompete", "tpt": "Trompete", "trp": "Trompete",
    "tpte": "Trompete", "trompeta": "Trompete",
    "cornet": "Cornetim", "corneta": "Cornetim", "cornetta": "Cornetim",
    "flugelhorn": "Fliscorne", "flicorno": "Fliscorne", "fliscorne": "Fliscorne",
    "horn": "Trompa", "french horn": "Trompa", "corno": "Trompa", "hn": "Trompa",
    "trombone": "Trombone", "tbn": "Trombone", "trb": "Trombone", "tromb": "Trombone",
    "b tbn": "Trombone", "btbn": "Trombone", "bass trombone": "Trombone",
    "trombone baixo": "Trombone",
    "euphonium": "Bombardino", "baritone": "Bombardino", "eufonio": "Bombardino",
    "bombardino": "Bombardino", "euph": "Bombardino",
    "tuba": "Tuba", "bombardao": "Tuba", "sousafone": "Tuba", "sousaphone": "Tuba",
    "basso": "Tuba", "bombardino baixo": "Tuba",
    # «bass» sozinho é ambíguo numa banda (bass clarinet, bass drum, bass
    # trombone, double bass) — deliberadamente fora, para não gerar Tubas falsas
    "double bass": "Contrabaixo", "contrabaixo": "Contrabaixo",
    "contrabass": "Contrabaixo", "string bass": "Contrabaixo",
    "timpani": "Tímpanos", "timpano": "Tímpanos", "timp": "Tímpanos",
    "percussion": "Percussão", "percussao": "Percussão", "perc": "Percussão",
    "caixa": "Percussão", "snare": "Percussão", "cymbal": "Percussão",
    "prato": "Percussão", "triangulo": "Percussão", "caixa clara": "Percussão",
    "bombo": "Percussão", "pratos": "Percussão", "snare drum": "Percussão",
    "bass drum": "Percussão", "cymbals": "Percussão",
    "drum set": "Bateria", "drums": "Bateria", "drumset": "Bateria",
}

_ROMAN = {"i": 1, "ii": 2, "iii": 3, "iv": 4}
_VOICE_RE = re.compile(r"\b(i{1,3}|iv|[1-4])(?:º|ª|o|\.o|st|nd|rd|th)?\s*$", re.IGNORECASE)
_KEY_RE = re.compile(
    r"\b(?:in|em)\s+(?:bb|b|eb|es|f|c|sib|si\s?b|mib|mi\s?b|fa|fá|do|la|lá)\b", re.IGNORECASE
)


_CAMEL_RE = re.compile(r"(?<=[a-z])(?=[A-Z])")


def _norm(s: str) -> str:
    # o OCR devolve muitas vezes as palavras coladas («AltoSaxophoneII»);
    # separar nas maiúsculas repõe as fronteiras antes de baixar a caixa
    s = _CAMEL_RE.sub(" ", s)
    s = unicodedata.normalize("NFKD", s)
    s = "".join(c for c in s if not unicodedata.combining(c)).lower()
    s = _KEY_RE.sub(" ", s)
    s = re.sub(r"[^\w\s]", " ", s)
    return re.sub(r"\s+", " ", s).strip()


def _squash(s: str) -> str:
    """Forma comparável sem espaços — o OCR perde-os com frequência."""
    return _norm(s).replace(" ", "")


def identify(raw_name: str) -> tuple[str, int | None, float]:  # noqa: PLR0911
    """Devolve (instrumento canónico, nº de voz, confiança 0–1).

    A identificação é uma cascata de estratégias por ordem decrescente de
    certeza — nome exato, família dos saxofones, alias exato, alias contido,
    e por fim semelhança aproximada. Cada uma devolve assim que acerta, e é
    isso que dá os vários `return` desta função: são o próprio algoritmo.

    Instrumentos desconhecidos devolvem o nome original com confiança 0.3, em
    vez de um palpite — num nome lido por OCR, errar é pior do que não saber.
    """
    n = _norm(raw_name)
    voice: int | None = None
    vm = _VOICE_RE.search(n)
    if vm:
        token = vm.group(1).lower()
        voice = _ROMAN.get(token) or int(token)
        n = n[: vm.start()].strip()

    for canon in CANONICAL:
        if _norm(canon) == n:
            return canon, voice, 1.0

    if any(k in n for k in ("sax", "saxofone", "saxophone")):
        for key, canon in (
            ("sopran", "Sax Soprano"), ("sop", "Sax Soprano"),
            ("alto", "Sax Alto"), ("alt", "Sax Alto"),
            ("tenor", "Sax Tenor"), ("ten", "Sax Tenor"),
            ("bari", "Sax Barítono"), ("baryton", "Sax Barítono"), ("bar", "Sax Barítono"),
        ):
            if key in n:
                return canon, voice, 0.95
        return "Sax Alto", voice, 0.5

    for alias, canon in ALIASES.items():
        if _norm(alias) == n:
            return canon, voice, 0.95

    # aliases mais longos primeiro: «bass clarinet» tem de ganhar a «clarinet»
    squashed = n.replace(" ", "")
    for alias, canon in sorted(ALIASES.items(), key=lambda kv: -len(kv[0])):
        a = _squash(alias)
        if len(a) > 3 and (a in squashed or squashed in a):
            return canon, voice, 0.85

    best, score = None, 0.0
    candidates = [(c, c) for c in CANONICAL] + list(ALIASES.items())
    for cand, canon in candidates:
        r = SequenceMatcher(None, squashed, _squash(cand)).ratio()
        if r > score:
            best, score = canon, r
    if best and score >= 0.78:
        return best, voice, round(score, 2)

    return raw_name.strip() or "Desconhecido", voice, 0.3


def instrument_range(canonical: str) -> tuple[int, int] | None:
    meta = CANONICAL.get(canonical)
    if meta and "range" in meta:
        return meta["range"]
    return None

"""Leitura dos nomes dos instrumentos impressos à esquerda das pautas.

Muitas partituras antigas não trazem os nomes num formato que o motor OMR
consiga aproveitar — devolve «Voice» para todas as pautas. Os nomes estão
impressos na margem esquerda do primeiro sistema, e nós já sabemos onde cada
pauta começa e acaba, por isso basta recortar essa faixa e passar OCR.
"""
from __future__ import annotations

from pathlib import Path

import cv2
import numpy as np

from app.core import config
from app.pipeline.recognition import instruments
from app.pipeline.recognition.staffs import detect_staves

MARGIN_RATIO = 0.16      # fração da largura à esquerda onde o nome é impresso
MIN_CONFIDENCE = 0.7     # abaixo disto não vale a pena arriscar um nome errado


def _ocr(image: np.ndarray) -> str:
    import pytesseract

    exe = config.tesseract_path()
    if exe:
        pytesseract.pytesseract.tesseract_cmd = exe
    # psm 7 = uma linha de texto; a lista de caracteres evita ruído de símbolos
    cfg = (
        "--psm 7 -c tessedit_char_whitelist="
        "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789.ºª "
    )
    try:
        return pytesseract.image_to_string(image, config=cfg).strip()
    except Exception:
        return ""


def read_staff_names(page_path: str | Path) -> list[tuple[str, str, int | None, float]]:
    """Lê os nomes das pautas do primeiro sistema de uma página.

    Devolve, por pauta e de cima para baixo:
    (texto lido, instrumento canónico, nº de voz, confiança).
    """
    if not config.tesseract_path():
        return []
    img = cv2.imread(str(page_path), cv2.IMREAD_GRAYSCALE)
    if img is None:
        return []

    binary = cv2.adaptiveThreshold(
        img, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, 35, 15
    )
    staves = detect_staves(binary)
    if not staves:
        return []

    height, width = img.shape
    margin = int(width * MARGIN_RATIO)
    results: list[tuple[str, str, int | None, float]] = []

    for staff in staves:
        spacing = staff["spacing"]
        top = max(0, int(staff["top"] - spacing * 1.5))
        bottom = min(height, int(staff["bottom"] + spacing * 1.5))
        crop = img[top:bottom, 0:margin]
        if crop.size == 0:
            results.append(("", "", None, 0.0))
            continue
        # o OCR trabalha melhor com texto grande e fundo limpo
        crop = cv2.resize(crop, None, fx=2.0, fy=2.0, interpolation=cv2.INTER_CUBIC)
        crop = cv2.copyMakeBorder(crop, 10, 10, 10, 10, cv2.BORDER_CONSTANT, value=255)
        text = _ocr(crop)
        if not text:
            results.append(("", "", None, 0.0))
            continue
        canonical, voice, conf = instruments.identify(text)
        if conf < MIN_CONFIDENCE or canonical not in instruments.CANONICAL:
            results.append((text, "", None, conf))
        else:
            results.append((text, canonical, voice, conf))
    return results


def apply_to_document(doc, page_path: str | Path) -> int:
    """Atribui às pautas sem nome os instrumentos lidos por OCR.

    A correspondência é por posição: a ordem das pautas na página é a mesma
    ordem das partes no documento.
    """
    names = read_staff_names(page_path)
    if not names:
        return 0
    applied = 0
    for part, (_text, canonical, voice, conf) in zip(doc.parts, names, strict=False):
        if not canonical:
            continue
        part.name = f"{canonical} {voice}" if voice else canonical
        part.canonical_instrument = canonical
        part.voice_number = voice
        part.confidence = round(conf, 2)
        meta = instruments.CANONICAL[canonical]
        part.midi_program = meta["midi"]
        part.is_percussion = bool(meta.get("percussion"))
        part.transposition = meta.get("transposition", 0)
        for meas in part.measures:
            for note in meas.notes:
                note.instrument = part.display_name
        applied += 1
    return applied

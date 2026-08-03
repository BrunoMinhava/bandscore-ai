"""Deteção de pautas por perfil de projeção horizontal."""
from __future__ import annotations

import numpy as np


def detect_staves(binary: np.ndarray) -> list[dict]:
    """Deteta pautas (grupos de 5 linhas) numa imagem binarizada.

    Devolve, para cada pauta: topo, fundo, posições das 5 linhas e o
    espaçamento médio entre linhas (útil para escalar a deteção de símbolos).
    """
    staves = _detect(binary)
    if staves:
        return staves
    # Numa fotografia ligeiramente inclinada, a projeção da largura toda
    # esborrata as linhas e não encontra nada. A faixa central costuma estar
    # nítida e chega para medir a pauta.
    w = binary.shape[1]
    if w < 300:
        return staves
    return _detect(binary[:, w // 4: 3 * w // 4])


def _detect(binary: np.ndarray) -> list[dict]:
    ink = (binary < 128).mean(axis=1)
    if ink.max() == 0:
        return []
    thr = max(0.25, float(ink.mean() + 2 * ink.std()))
    rows = np.where(ink > thr)[0]

    # agrupar filas contíguas numa linha só
    lines: list[int] = []
    if rows.size:
        start = prev = int(rows[0])
        for raw in rows[1:]:
            r = int(raw)
            if r > prev + 1:
                lines.append((start + prev) // 2)
                start = r
            prev = r
        lines.append((start + prev) // 2)

    # agrupar linhas em pautas de 5 pelo espaçamento regular
    staves: list[dict] = []
    i = 0
    while i + 4 < len(lines):
        gaps = np.diff(lines[i: i + 5])
        if gaps.max() < 3 * max(1, gaps.min()):
            staves.append({
                "top": int(lines[i]),
                "bottom": int(lines[i + 4]),
                "lines": [int(l) for l in lines[i: i + 5]],
                "spacing": float(np.mean(gaps)),
            })
            i += 5
        else:
            i += 1
    return staves

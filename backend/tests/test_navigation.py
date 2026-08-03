from app.engine.model import Measure
from app.engine.navigation import expand_playback_order


def _measures(n: int) -> list[Measure]:
    return [Measure(number=i + 1) for i in range(n)]


def test_sem_marcadores():
    assert expand_playback_order(_measures(4)) == [1, 2, 3, 4]


def test_repeticao_simples():
    ms = _measures(4)
    ms[1].repeat_start = True
    ms[2].repeat_end = True
    assert expand_playback_order(ms) == [1, 2, 3, 2, 3, 4]


def test_repeticao_sem_inicio_volta_ao_principio():
    ms = _measures(3)
    ms[1].repeat_end = True
    assert expand_playback_order(ms) == [1, 2, 1, 2, 3]


def test_da_capo_al_fine():
    ms = _measures(4)
    ms[3].direction = "D.C. al Fine"
    ms[1].fine = True
    assert expand_playback_order(ms) == [1, 2, 3, 4, 1, 2]


def test_dal_segno_al_coda():
    ms = _measures(6)
    ms[1].segno = True
    ms[2].to_coda = True
    ms[4].direction = "D.S. al Coda"
    ms[5].coda = True
    assert expand_playback_order(ms) == [1, 2, 3, 4, 5, 2, 3, 6]


def test_repeticoes_nao_se_retomam_apos_da_capo():
    ms = _measures(3)
    ms[1].repeat_end = True
    ms[2].direction = "D.C."
    order = expand_playback_order(ms)
    assert order == [1, 2, 1, 2, 3, 1, 2, 3]


def test_orientacao_nao_vira_paginas_boas():
    """Regressão: a deteção de 180° por OCR virava páginas legíveis ao
    contrário (8 em 24 numa partitura real) e destruía o reconhecimento."""
    import cv2
    import numpy as np

    from app.pipeline.preprocessing.steps import detect_orientation

    page = np.full((1400, 1000), 255, np.uint8)
    for top in (200, 500, 800):
        for k in range(5):
            cv2.line(page, (80, top + k * 18), (920, top + k * 18), 0, 2)
    assert detect_orientation(page) == 0

    deitada = cv2.rotate(page, cv2.ROTATE_90_COUNTERCLOCKWISE)
    assert detect_orientation(deitada) == 90

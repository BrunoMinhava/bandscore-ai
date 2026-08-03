"""Expansão da navegação musical — repetições, D.C., D.S., Coda, Fine —
para a ordem real de execução dos compassos."""
from __future__ import annotations

from app.engine.model import Measure

MAX_STEPS = 10000


def expand_playback_order(measures: list[Measure]) -> list[int]:
    """Devolve os números de compasso pela ordem em que devem ser tocados,
    respeitando repetições, Da Capo, Dal Segno, Coda e Fine."""
    if not measures:
        return []
    segno_i = next((i for i, m in enumerate(measures) if m.segno), 0)
    coda_i = next((i for i, m in enumerate(measures) if m.coda), None)
    fine_i = next((i for i, m in enumerate(measures) if m.fine), None)

    order: list[int] = []
    i = 0
    repeat_counts: dict[int, int] = {}
    pending_start: list[int] = []   # pilha de inícios de repetição
    jump_taken = False              # já saltámos por D.C./D.S.?
    to_coda_armed = False           # depois do salto, saltar no "To Coda"
    honor_fine = False
    steps = 0

    while 0 <= i < len(measures) and steps < MAX_STEPS:
        steps += 1
        m = measures[i]
        if m.repeat_start and (not pending_start or pending_start[-1] != i):
            pending_start.append(i)
        order.append(m.number)

        # Fine e To Coda avaliam-se depois de tocar o compasso
        if honor_fine and fine_i is not None and i == fine_i:
            break
        if to_coda_armed and m.to_coda and coda_i is not None:
            i = coda_i
            to_coda_armed = False
            continue

        # repetições convencionais não se retomam após D.C./D.S.
        if m.repeat_end and not jump_taken:
            start = pending_start[-1] if pending_start else 0
            done = repeat_counts.get(i, 1)
            if done < m.repeat_times:
                repeat_counts[i] = done + 1
                i = start
                continue
            if pending_start:
                pending_start.pop()

        if m.direction and not jump_taken:
            d = m.direction.lower().replace(".", "")
            jump_taken = True
            honor_fine = "fine" in d
            to_coda_armed = "coda" in d
            # D.S. volta ao Segno; D.C. (Da Capo) volta ao início
            i = segno_i if ("ds" in d or "dal segno" in d) else 0
            continue

        i += 1
    return order

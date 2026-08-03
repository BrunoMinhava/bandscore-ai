"""Adaptador para o motor OMR Audiveris (CLI).

O Audiveris faz o reconhecimento ótico principal (pautas, notas, símbolos)
e exporta MusicXML, que é depois carregado no modelo interno e refinado
pelos módulos de instrumentos e confiança.
"""
from __future__ import annotations

import hashlib
import os
import subprocess
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from app.core import config


# O Audiveris já usa cerca de 3 núcleos por processo e ocupa ~2 GB de memória
# com páginas grandes, por isso lançar um processo por núcleo seria contra-
# producente. Três a quatro em paralelo é o ponto de equilíbrio.
def _worker_count(pages: int) -> int:
    cores = os.cpu_count() or 4
    return max(1, min(4, cores // 3, pages))


class AudiverisNotFound(RuntimeError):
    pass


INSTALL_HINT = (
    "Audiveris não encontrado. Descarregue o instalador (.dmg no macOS) de "
    "https://github.com/Audiveris/audiveris/releases e coloque a app em /Applications, "
    "ou defina a variável de ambiente BANDSCORE_AUDIVERIS com o caminho do executável."
)


def _page_hash(path: Path) -> str:
    h = hashlib.sha1()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()[:16]


def _export_of(page_dir: Path) -> Path | None:
    found = sorted(page_dir.rglob("*.mxl")) + sorted(page_dir.rglob("*.xml"))
    found = [p for p in found if "META-INF" not in p.parts]
    return found[0] if found else None


def _run_one(exe: str, page: Path, out_dir: Path, timeout: int) -> tuple[Path, Path | None, str]:
    """Reconhece uma página. Reutiliza o resultado se a página não mudou."""
    page_dir = out_dir / _page_hash(page)
    cached = _export_of(page_dir)
    if cached is not None:
        return page, cached, ""

    page_dir.mkdir(parents=True, exist_ok=True)
    # nota: -swap parece poupar memória mas quebra o passo de exportação
    # ("Error in export"), por isso fica de fora deliberadamente
    cmd = [exe, "-batch", "-export", "-output", str(page_dir), "--", str(page)]
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        err = (proc.stderr or proc.stdout or "")[-800:]
    except subprocess.TimeoutExpired:
        return page, None, f"tempo esgotado ({timeout}s)"
    return page, _export_of(page_dir), err


def run_audiveris(
    inputs: list[Path], out_dir: Path, timeout: int = 1800, on_page=None
) -> list[Path]:
    """Reconhece as páginas em paralelo e devolve as exportações pela ordem
    de entrada. Páginas já reconhecidas (mesmo conteúdo) são reaproveitadas."""
    exe = config.audiveris_path()
    if not exe:
        raise AudiverisNotFound(INSTALL_HINT)

    out_dir.mkdir(parents=True, exist_ok=True)
    workers = _worker_count(len(inputs))
    results: dict[Path, Path | None] = {}
    errors: list[str] = []

    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures = [pool.submit(_run_one, exe, p, out_dir, timeout) for p in inputs]
        for fut in futures:
            page, export, err = fut.result()
            results[page] = export
            if on_page:
                on_page()
            if export is None and err:
                errors.append(f"{page.name}: {err}")

    exports = [results[p] for p in inputs if results.get(p) is not None]
    if not exports:
        failed = [p for p in inputs if results.get(p) is None]
        raise RuntimeError(_explain_failure(failed, errors))
    return exports


def _explain_failure(failed: list[Path], errors: list[str]) -> str:
    """Traduz as falhas do Audiveris para uma explicação útil.

    O motor limita-se a atirar «Error in export» com um rasto de Java quando
    ignora uma folha, sem dizer porquê — a causa é quase sempre a resolução.
    """
    from app.pipeline.preprocessing import MAX_SHEET_PX, image_quality_problem

    for page in failed:
        problem = image_quality_problem(page)
        if problem:
            return problem
        try:
            import cv2

            img = cv2.imread(str(page), cv2.IMREAD_GRAYSCALE)
            if img is not None and max(img.shape[:2]) > MAX_SHEET_PX:
                return (
                    f"A página {page.name} tem {img.shape[1]}×{img.shape[0]} px e o "
                    f"motor de reconhecimento não aceita folhas acima de "
                    f"{MAX_SHEET_PX} px por lado. Reduza a imagem ou divida a página."
                )
        except Exception:
            pass

    detail = " | ".join(errors)
    if "Sheet ignored" in detail or "Error in export" in detail:
        return (
            "O motor de reconhecimento rejeitou a(s) página(s). Costuma acontecer "
            "quando a imagem tem pouca resolução, está desfocada, muito inclinada "
            "ou não contém pautas legíveis. Experimente digitalizar a 300 DPI."
        )
    return "O reconhecimento falhou. " + detail[-500:]

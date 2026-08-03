"""Orquestrador do pré-processamento de páginas.

Aplica, pela ordem correta, os passos escolhidos (perspetiva, sombras, ruído,
contraste, rotação), normaliza a escala para a janela em que o motor OMR
trabalha melhor, corta páginas duplas e produz um relatório com avisos.
"""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import cv2
import numpy as np

from app.models.schemas import PreprocessOptions
from app.pipeline.preprocessing import steps
from app.pipeline.recognition.staffs import detect_staves

# O reconhecimento ótico mede a distância entre linhas da pauta (interline) e
# é aí que joga toda a deteção seguinte. Abaixo de ~14 px falha símbolos e
# barras de compasso; acima de ~30 px não ganha nada e só custa tempo, porque
# o custo cresce com o número de pixels.
TARGET_INTERLINE = 20.0
MIN_INTERLINE = 16.0
MAX_INTERLINE = 30.0
# abaixo disto o motor OMR rejeita a folha; ampliar não resolve porque
# interpolar não acrescenta detalhe nenhum a uma fotografia pequena
MIN_WORKABLE_INTERLINE = 11.0
# o Audiveris ignora folhas acima de ~5000 px por lado
MAX_SHEET_PX = 4900
# ampliar por interpolação não acrescenta detalhe, só custo — para PDFs a
# resolução certa é escolhida na importação; aqui só se corrige fotos e scans
MIN_SCALE, MAX_SCALE = 0.35, 1.8


def preprocess_page(original_path: Path, out_dir: Path, options: PreprocessOptions) -> dict:
    img = cv2.imread(str(original_path), cv2.IMREAD_COLOR)
    if img is None:
        return {"error": f"Não foi possível ler a imagem: {original_path.name}", "warnings": []}

    report: dict = {"warnings": [], "steps": []}
    gray = steps.to_gray(img)

    # antes de tudo: pôr a página direita (fotos de telemóvel vêm deitadas)
    orientation = steps.detect_orientation(gray)
    if orientation:
        gray = steps.apply_orientation(gray, orientation)
        report["orientation"] = orientation
        report["steps"].append(f"rodada {orientation}°")

    if options.perspective:
        gray = steps.correct_perspective(gray)
        report["steps"].append("perspetiva")
    if options.shadows:
        gray = steps.remove_shadows(gray)
        report["steps"].append("sombras")
    if options.denoise:
        gray = steps.denoise(gray)
        report["steps"].append("ruído")
    if options.contrast:
        gray = steps.enhance_contrast(gray)
        report["steps"].append("contraste")
    if options.deskew:
        angle = steps.estimate_skew_angle(gray)
        gray = steps.deskew(gray, angle)
        report["skew_angle"] = round(angle, 2)
        report["steps"].append("rotação")

    binary = steps.binarize(gray)
    staves = detect_staves(binary)

    gray, binary, staves = _normalize_scale(gray, binary, staves, report)

    out_dir.mkdir(parents=True, exist_ok=True)
    stem = original_path.stem
    omr_inputs: list[Path] = []

    split_x = steps.detect_double_page(binary) if options.split_double_pages else None
    if split_x is not None:
        report["double_page_split_x"] = split_x
        report["warnings"].append("Página dupla detetada — dividida em duas metades")
        for side, part in (("a", gray[:, :split_x]), ("b", gray[:, split_x:])):
            path = out_dir / f"{stem}.proc-{side}.png"
            cv2.imwrite(str(path), part)
            omr_inputs.append(path)
    else:
        path = out_dir / f"{stem}.proc.png"
        cv2.imwrite(str(path), gray)
        omr_inputs.append(path)

    binary_path = out_dir / f"{stem}.bin.png"
    cv2.imwrite(str(binary_path), binary)

    report["staves"] = len(staves)
    if not staves:
        report["warnings"].append("Nenhuma pauta detetada — verificar a qualidade da imagem")
    else:
        problem = quality_problem(gray, staves)
        if problem:
            report["quality_error"] = problem
            report["warnings"].append(problem)

    cuts = steps.detect_cut_edges(binary)
    if cuts:
        report["warnings"].append(f"Possível corte nas margens: {', '.join(cuts)}")

    report["processed_path"] = str(omr_inputs[0])
    report["omr_inputs"] = [str(p) for p in omr_inputs]
    report["binary_path"] = str(binary_path)
    return report


def _normalize_scale(
    gray: np.ndarray, binary: np.ndarray, staves: list[dict], report: dict
) -> tuple[np.ndarray, np.ndarray, list[dict]]:
    """Redimensiona a página para o interline cair na janela ideal do OMR.

    Reduzir quando a digitalização é maior do que o necessário poupa tempo
    proporcional ao número de pixels, sem perder informação; ampliar quando a
    pauta é pequena demais evita símbolos e barras de compasso falhados.
    """
    h0, w0 = gray.shape
    # o motor OMR ignora folhas acima de ~5000 px por lado, mesmo com a pauta
    # do tamanho certo — este teto aplica-se sempre
    limit = MAX_SHEET_PX / max(h0, w0)

    if not staves:
        if limit < 1.0:
            gray = cv2.resize(
                gray, (int(w0 * limit), int(h0 * limit)), interpolation=cv2.INTER_AREA
            )
            binary = steps.binarize(gray)
            report["scale_applied"] = round(limit, 3)
            report["steps"].append(f"escala {limit:.2f}× (limite do motor OMR)")
        return gray, binary, staves

    interline = float(np.median([s["spacing"] for s in staves]))
    report["interline"] = round(interline, 1)
    scale = 1.0
    if interline > 0 and not (MIN_INTERLINE <= interline <= MAX_INTERLINE):
        scale = max(MIN_SCALE, min(MAX_SCALE, TARGET_INTERLINE / interline))
    scale = min(scale, limit)
    if abs(scale - 1.0) < 0.05:
        return gray, binary, staves

    interp = cv2.INTER_AREA if scale < 1 else cv2.INTER_CUBIC
    h, w = gray.shape
    gray = cv2.resize(gray, (max(1, int(w * scale)), max(1, int(h * scale))), interpolation=interp)
    binary = steps.binarize(gray)
    staves = detect_staves(binary) or staves
    report["scale_applied"] = round(scale, 3)
    report["steps"].append(f"escala {scale:.2f}×")
    return gray, binary, staves


def quality_problem(gray: np.ndarray, staves: list[dict] | None = None) -> str | None:
    """Diz, em português e com números concretos, porque é que uma imagem não
    serve para reconhecimento — antes de gastar minutos a tentar."""
    if staves is None:
        staves = detect_staves(steps.binarize(gray))
    if not staves:
        return (
            "Não foi possível encontrar pautas nesta imagem. "
            "Confirme que a fotografia mostra a partitura direita e bem iluminada."
        )
    interline = float(np.median([s["spacing"] for s in staves]))
    if interline >= MIN_WORKABLE_INTERLINE:
        return None

    h, w = gray.shape
    needed = TARGET_INTERLINE / max(interline, 0.1)
    return (
        f"Imagem com pouca resolução para reconhecimento musical: as linhas da "
        f"pauta estão a {interline:.1f} pixels de distância e são precisos pelo "
        f"menos {MIN_WORKABLE_INTERLINE:.0f}. "
        f"Esta imagem tem {w}×{h} px; para esta partitura seriam precisos cerca "
        f"de {int(w * needed)}×{int(h * needed)} px. "
        "Fotografe mais perto (uma página de cada vez), ou digitalize a 300 DPI."
    )


def image_quality_problem(path: str | Path) -> str | None:
    """Mesma verificação a partir de um ficheiro."""
    img = cv2.imread(str(path), cv2.IMREAD_GRAYSCALE)
    if img is None:
        return f"Não foi possível ler a imagem: {Path(path).name}"
    return quality_problem(img)


def preprocess_pages(
    jobs: list[tuple[Path, Path]],
    options: PreprocessOptions,
    workers: int | None = None,
    on_page=None,
) -> list[dict]:
    """Pré-processa várias páginas em paralelo (OpenCV liberta o GIL)."""

    def one(job: tuple[Path, Path]) -> dict:
        report = preprocess_page(job[0], job[1], options)
        if on_page:
            on_page()
        return report

    if len(jobs) == 1:
        return [one(jobs[0])]
    workers = workers or min(8, max(1, (len(jobs) + 1) // 2))
    with ThreadPoolExecutor(max_workers=workers) as pool:
        return list(pool.map(one, jobs))

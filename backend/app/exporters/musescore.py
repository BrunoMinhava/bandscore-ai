"""Adaptador para o MuseScore CLI — conversões PDF, MSCZ, PNG, SVG."""
from __future__ import annotations

import subprocess
from pathlib import Path

from app.core import config


class MuseScoreNotFound(RuntimeError):
    pass


INSTALL_HINT = (
    "MuseScore não encontrado. Instale a partir de https://musescore.org "
    "(no macOS: brew install --cask musescore) ou defina a variável de ambiente "
    "BANDSCORE_MUSESCORE com o caminho do executável."
)


def convert(input_path: Path, output_path: Path, timeout: int = 600) -> list[Path]:
    """Converte via MuseScore CLI (``mscore -o saída entrada``).

    Devolve os ficheiros produzidos — PNG/SVG podem gerar um por página.
    """
    exe = config.musescore_path()
    if not exe:
        raise MuseScoreNotFound(INSTALL_HINT)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    proc = subprocess.run(
        [exe, "-o", str(output_path), str(input_path)],
        capture_output=True, text=True, timeout=timeout,
    )
    produced = _collect_outputs(output_path)
    if not produced:
        raise RuntimeError(
            f"O MuseScore não produziu {output_path.name}. "
            f"Saída de erro: {(proc.stderr or proc.stdout)[-1500:]}"
        )
    return produced


def _collect_outputs(output_path: Path) -> list[Path]:
    if output_path.exists():
        return [output_path]
    # MuseScore numera páginas: obra-1.png, obra-2.png, …
    pattern = f"{output_path.stem}-*{output_path.suffix}"
    return sorted(output_path.parent.glob(pattern))

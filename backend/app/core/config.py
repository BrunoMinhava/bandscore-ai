"""Configuração global do BandScore AI.

Todo o processamento é local. As ferramentas externas (Audiveris, MuseScore,
Tesseract) são detetadas automaticamente, mas podem ser definidas por
variáveis de ambiente: BANDSCORE_AUDIVERIS, BANDSCORE_MUSESCORE,
BANDSCORE_TESSERACT.
"""
from __future__ import annotations

import os
import platform
import shutil
from functools import lru_cache
from pathlib import Path

APP_NAME = "BandScoreAI"
API_PORT = 8765
RASTER_DPI = 300


def data_dir() -> Path:
    system = platform.system()
    if system == "Darwin":
        base = Path.home() / "Library" / "Application Support"
    elif system == "Windows":
        base = Path(os.environ.get("APPDATA", str(Path.home())))
    else:
        base = Path(os.environ.get("XDG_DATA_HOME", str(Path.home() / ".local" / "share")))
    d = base / APP_NAME
    d.mkdir(parents=True, exist_ok=True)
    return d


def projects_dir() -> Path:
    d = data_dir() / "projects"
    d.mkdir(parents=True, exist_ok=True)
    return d


def models_dir() -> Path:
    """Modelos de IA locais (ONNX / TFLite / PyTorch)."""
    d = data_dir() / "models"
    d.mkdir(parents=True, exist_ok=True)
    return d


def db_path() -> Path:
    return data_dir() / "bandscore.sqlite3"


def file_url(path: str | Path) -> str:
    """Converte um caminho dentro do diretório de dados num URL /files/…"""
    try:
        rel = Path(path).resolve().relative_to(data_dir().resolve())
        return "/files/" + str(rel)
    except ValueError:
        return ""


def _first_existing(paths: list[str]) -> str | None:
    for p in paths:
        if not p:
            continue
        found = shutil.which(p)
        if found:
            return found
        if Path(p).exists():
            return p
    return None


@lru_cache
def audiveris_path() -> str | None:
    return _first_existing([
        os.environ.get("BANDSCORE_AUDIVERIS", ""),
        "audiveris",
        "Audiveris",
        "/Applications/Audiveris.app/Contents/MacOS/Audiveris",
        str(Path.home() / "Applications/Audiveris.app/Contents/MacOS/Audiveris"),
        "/opt/homebrew/bin/audiveris",
        "C:/Program Files/Audiveris/Audiveris.exe",
    ])


@lru_cache
def musescore_path() -> str | None:
    return _first_existing([
        os.environ.get("BANDSCORE_MUSESCORE", ""),
        "mscore",
        "musescore",
        "mscore4portable",
        "/Applications/MuseScore 4.app/Contents/MacOS/mscore",
        "/Applications/MuseScore 3.app/Contents/MacOS/mscore",
        "C:/Program Files/MuseScore 4/bin/MuseScore4.exe",
    ])


@lru_cache
def tesseract_path() -> str | None:
    return _first_existing([
        os.environ.get("BANDSCORE_TESSERACT", ""),
        "tesseract",
        "/opt/homebrew/bin/tesseract",
    ])


def compute_device() -> str:
    """GPU quando existir, CPU quando não existir (importação preguiçosa)."""
    try:
        import torch  # opcional — requirements-ml.txt

        if torch.cuda.is_available():
            return "cuda"
        if getattr(torch.backends, "mps", None) and torch.backends.mps.is_available():
            return "mps"
    except Exception:
        pass
    return "cpu"


def capabilities() -> dict:
    caps: dict = {
        "audiveris": audiveris_path(),
        "musescore": musescore_path(),
        "tesseract": tesseract_path(),
        "device": compute_device(),
        "onnxruntime": False,
        "torch": False,
        "models": [
            p.name for p in models_dir().glob("*")
            if p.suffix in (".onnx", ".tflite", ".pt")
        ],
    }
    for mod in ("onnxruntime", "torch"):
        try:
            __import__(mod)
            caps[mod] = True
        except Exception:
            pass
    return caps

"""Motor musical — persistência do modelo interno (score.json) com histórico
de versões para undo."""
from __future__ import annotations

import shutil
import time
from pathlib import Path

from app.engine.model import ScoreDoc

SCORE_FILE = "score.json"
HISTORY_DIR = "history"
MAX_SNAPSHOTS = 50


def score_path(project_dir: str | Path) -> Path:
    return Path(project_dir) / SCORE_FILE


def has_score(project_dir: str | Path) -> bool:
    return score_path(project_dir).exists()


def load_score(project_dir: str | Path) -> ScoreDoc | None:
    p = score_path(project_dir)
    if not p.exists():
        return None
    return ScoreDoc.model_validate_json(p.read_text(encoding="utf-8"))


def save_score(doc: ScoreDoc, project_dir: str | Path, snapshot: bool = True) -> None:
    p = score_path(project_dir)
    if snapshot and p.exists():
        hist = Path(project_dir) / HISTORY_DIR
        hist.mkdir(exist_ok=True)
        shutil.copy2(p, hist / f"{time.time_ns()}.json")
        old = sorted(hist.glob("*.json"))
        for f in old[:-MAX_SNAPSHOTS]:
            f.unlink()
    p.write_text(doc.model_dump_json(), encoding="utf-8")


def undo(project_dir: str | Path) -> ScoreDoc | None:
    """Repõe o snapshot mais recente do histórico."""
    hist = Path(project_dir) / HISTORY_DIR
    if not hist.exists():
        return None
    snapshots = sorted(hist.glob("*.json"))
    if not snapshots:
        return None
    latest = snapshots[-1]
    doc = ScoreDoc.model_validate_json(latest.read_text(encoding="utf-8"))
    score_path(project_dir).write_text(doc.model_dump_json(), encoding="utf-8")
    latest.unlink()
    return doc

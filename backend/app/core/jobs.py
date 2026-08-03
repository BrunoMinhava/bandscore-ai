"""Acompanhamento de trabalhos demorados (preparar + reconhecer).

O reconhecimento leva minutos, por isso corre em segundo plano e o interface
pergunta o progresso. As percentagens são reais — contam páginas concluídas —
e o tempo estimado sai do ritmo da própria corrida, não de um valor fixo.
"""
from __future__ import annotations

import threading
import time
from dataclasses import dataclass, field

PHASE_LABELS = {
    "preparar": "a preparar as páginas",
    "reconhecer": "a reconhecer a música",
    "concluir": "a organizar a partitura",
}


@dataclass
class Job:
    total: int = 0
    done: int = 0
    phase: str = "preparar"
    started: float = field(default_factory=time.monotonic)
    finished: bool = False
    error: str | None = None
    result: dict | None = None
    _lock: threading.Lock = field(default_factory=threading.Lock, repr=False)

    def plan(self, total: int) -> None:
        with self._lock:
            self.total = max(1, total)

    def set_phase(self, phase: str) -> None:
        with self._lock:
            self.phase = phase

    def advance(self, step: int = 1) -> None:
        with self._lock:
            self.done = min(self.total, self.done + step)

    def fail(self, message: str) -> None:
        with self._lock:
            self.error = message
            self.finished = True

    def complete(self, result: dict) -> None:
        with self._lock:
            self.result = result
            self.done = self.total
            self.finished = True

    def snapshot(self) -> dict:
        with self._lock:
            elapsed = time.monotonic() - self.started
            percent = int(100 * self.done / self.total) if self.total else 0
            eta: int | None = None
            if self.done and not self.finished:
                eta = int(elapsed / self.done * (self.total - self.done))
            return {
                "phase": self.phase,
                "phase_label": PHASE_LABELS.get(self.phase, self.phase),
                "done": self.done,
                "total": self.total,
                "percent": 100 if self.finished and not self.error else percent,
                "elapsed_seconds": int(elapsed),
                "eta_seconds": eta,
                "finished": self.finished,
                "error": self.error,
                "result": self.result,
            }


_jobs: dict[int, Job] = {}
_registry_lock = threading.Lock()


def start(project_id: int) -> Job:
    with _registry_lock:
        job = Job()
        _jobs[project_id] = job
        return job


def get(project_id: int) -> Job | None:
    with _registry_lock:
        return _jobs.get(project_id)


def is_running(project_id: int) -> bool:
    job = get(project_id)
    return job is not None and not job.finished

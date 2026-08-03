"""Interface modular de detetores de símbolos musicais (YOLO / ONNX / TFLite).

Contrato do modelo
------------------
Deteção de objetos sobre a página inteira; as classes são o vocabulário de
símbolos musicais (SYMBOL_CLASSES). Para ativar um detetor neuronal:

1. instalar as dependências opcionais: ``pip install -r requirements-ml.txt``
2. colocar o modelo exportado (YOLOv11 → ONNX end-to-end, com NMS embutido,
   saída ``[n, 6] = x1, y1, x2, y2, confiança, classe``) em
   ``<dados>/models/*.onnx``

Sem modelo instalado, o reconhecimento principal é feito pelo Audiveris; o
detetor neuronal serve como segunda opinião para o sistema de confiança.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Protocol

import numpy as np

from app.core import config

SYMBOL_CLASSES = [
    # cabeças de nota e pausas
    "notehead_black", "notehead_half", "notehead_whole", "rest_whole", "rest_half",
    "rest_quarter", "rest_eighth", "rest_sixteenth",
    # claves, armaduras, compassos
    "clef_g", "clef_f", "clef_c", "sharp", "flat", "natural", "time_signature",
    # articulações e dinâmicas
    "staccato", "accent", "tenuto", "fermata", "dynamic_p", "dynamic_f",
    "dynamic_mf", "dynamic_ff", "dynamic_pp", "crescendo", "diminuendo",
    # estrutura
    "barline", "repeat_start", "repeat_end", "segno", "coda", "fine_text",
    "slur", "tie", "beam", "flag", "dot", "tuplet",
]


@dataclass
class Detection:
    label: str
    confidence: float
    bbox: tuple[float, float, float, float]  # x1, y1, x2, y2
    alternatives: list[tuple[str, float]] = field(default_factory=list)


class SymbolDetector(Protocol):
    def detect(self, image: np.ndarray) -> list[Detection]: ...


class OnnxSymbolDetector:
    """Executa um modelo ONNX de deteção de símbolos (GPU quando disponível)."""

    def __init__(self, model_path: Path):
        try:
            import onnxruntime as ort
        except ImportError as e:
            raise RuntimeError(
                "onnxruntime não instalado — correr: pip install -r requirements-ml.txt"
            ) from e
        providers = ["CPUExecutionProvider"]
        if config.compute_device() == "cuda":
            providers.insert(0, "CUDAExecutionProvider")
        self.session = ort.InferenceSession(str(model_path), providers=providers)
        self.input_name = self.session.get_inputs()[0].name
        shape = self.session.get_inputs()[0].shape
        self.size = int(shape[2]) if isinstance(shape[2], int) else 1280

    def detect(self, image: np.ndarray) -> list[Detection]:
        import cv2

        h, w = image.shape[:2]
        scale = self.size / max(h, w)
        resized = cv2.resize(image, (int(w * scale), int(h * scale)))
        canvas = np.full((self.size, self.size, 3), 114, dtype=np.uint8)
        if resized.ndim == 2:
            resized = cv2.cvtColor(resized, cv2.COLOR_GRAY2BGR)
        canvas[: resized.shape[0], : resized.shape[1]] = resized
        blob = canvas.transpose(2, 0, 1)[None].astype(np.float32) / 255.0

        outputs = self.session.run(None, {self.input_name: blob})[0]
        detections: list[Detection] = []
        for row in np.asarray(outputs).reshape(-1, outputs.shape[-1]):
            if len(row) < 6:
                continue
            x1, y1, x2, y2, conf, cls = row[:6]
            if conf < 0.25:
                continue
            idx = int(cls)
            label = SYMBOL_CLASSES[idx] if 0 <= idx < len(SYMBOL_CLASSES) else str(idx)
            detections.append(Detection(
                label=label,
                confidence=float(conf),
                bbox=(x1 / scale, y1 / scale, x2 / scale, y2 / scale),
            ))
        return detections


def get_detector() -> SymbolDetector | None:
    """Devolve o primeiro detetor disponível em <dados>/models, ou None."""
    for model in sorted(config.models_dir().glob("*.onnx")):
        try:
            return OnnxSymbolDetector(model)
        except RuntimeError:
            return None
    return None

"""Passos de pré-processamento de imagem (OpenCV).

Cada passo é uma função pura ndarray → ndarray em escala de cinzentos,
para poderem ser combinados livremente pelo orquestrador.
"""
from __future__ import annotations

import cv2
import numpy as np


def to_gray(img: np.ndarray) -> np.ndarray:
    if img.ndim == 3:
        return cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    return img


def correct_perspective(gray: np.ndarray) -> np.ndarray:
    """Corrige a perspetiva localizando o contorno da folha (fotos tortas).
    Em scans em que a folha ocupa toda a imagem não há nada a corrigir."""
    h, w = gray.shape
    blur = cv2.GaussianBlur(gray, (5, 5), 0)
    _, th = cv2.threshold(blur, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    contours, _ = cv2.findContours(th, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    if not contours:
        return gray
    page = max(contours, key=cv2.contourArea)
    area_ratio = cv2.contourArea(page) / float(h * w)
    if area_ratio > 0.95 or area_ratio < 0.3:
        return gray
    peri = cv2.arcLength(page, True)
    approx = cv2.approxPolyDP(page, 0.02 * peri, True)
    if len(approx) != 4:
        return gray
    pts = approx.reshape(4, 2).astype(np.float32)
    s = pts.sum(axis=1)
    d = np.diff(pts, axis=1).ravel()
    tl, br = pts[np.argmin(s)], pts[np.argmax(s)]
    tr, bl = pts[np.argmin(d)], pts[np.argmax(d)]
    wt = int(max(np.linalg.norm(br - bl), np.linalg.norm(tr - tl)))
    ht = int(max(np.linalg.norm(tr - br), np.linalg.norm(tl - bl)))
    if wt < 50 or ht < 50:
        return gray
    src = np.array([tl, tr, br, bl], dtype=np.float32)
    dst = np.array([[0, 0], [wt - 1, 0], [wt - 1, ht - 1], [0, ht - 1]], dtype=np.float32)
    M = cv2.getPerspectiveTransform(src, dst)
    return cv2.warpPerspective(gray, M, (wt, ht), borderValue=255)


def remove_shadows(gray: np.ndarray) -> np.ndarray:
    """Remove sombras e iluminação irregular dividindo pelo fundo estimado."""
    bg = cv2.medianBlur(gray, 41)
    return cv2.divide(gray, bg, scale=255)


def denoise(gray: np.ndarray) -> np.ndarray:
    return cv2.fastNlMeansDenoising(gray, None, h=10, templateWindowSize=7, searchWindowSize=21)


def enhance_contrast(gray: np.ndarray) -> np.ndarray:
    clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
    return clahe.apply(gray)


def detect_orientation(gray: np.ndarray) -> int:
    """Descobre a rotação necessária para as pautas ficarem horizontais.

    Fotografias de telemóvel apanham a partitura deitada com frequência. O
    critério é objetivo e verificável: roda-se a imagem e fica a orientação em
    que se detetam mais pautas, exigindo uma diferença clara para agir.

    Não se tenta distinguir 0° de 180°. O OCR do Tesseract dá essa resposta,
    mas numa página de música há pouco texto e ele adivinha: numa partitura de
    24 páginas devolveu 180° em 8 delas, que assim eram viradas ao contrário e
    ficavam ilegíveis para o motor OMR. Uma página ao contrário é raro; virar
    um terço das páginas boas não é aceitável.
    """
    from app.pipeline.recognition.staffs import detect_staves

    upright = len(detect_staves(binarize(gray)))
    turned = len(detect_staves(binarize(cv2.rotate(gray, cv2.ROTATE_90_CLOCKWISE))))
    return 90 if turned > max(upright * 2, upright + 2) else 0


def apply_orientation(gray: np.ndarray, angle: int) -> np.ndarray:
    if angle == 90:
        return cv2.rotate(gray, cv2.ROTATE_90_CLOCKWISE)
    if angle == 180:
        return cv2.rotate(gray, cv2.ROTATE_180)
    if angle == 270:
        return cv2.rotate(gray, cv2.ROTATE_90_COUNTERCLOCKWISE)
    return gray


def estimate_skew_angle(gray: np.ndarray) -> float:
    """Estima a rotação da página pelas linhas de pauta (quase horizontais)."""
    edges = cv2.Canny(gray, 50, 150)
    lines = cv2.HoughLinesP(
        edges, 1, np.pi / 180, threshold=120,
        minLineLength=gray.shape[1] // 3, maxLineGap=8,
    )
    if lines is None:
        return 0.0
    angles = []
    for x1, y1, x2, y2 in np.asarray(lines).reshape(-1, 4):
        ang = np.degrees(np.arctan2(y2 - y1, x2 - x1))
        if abs(ang) < 15:
            angles.append(ang)
    return float(np.median(angles)) if angles else 0.0


def deskew(gray: np.ndarray, angle: float | None = None) -> np.ndarray:
    ang = estimate_skew_angle(gray) if angle is None else angle
    if abs(ang) < 0.05:
        return gray
    h, w = gray.shape
    M = cv2.getRotationMatrix2D((w / 2, h / 2), ang, 1.0)
    return cv2.warpAffine(gray, M, (w, h), flags=cv2.INTER_CUBIC, borderValue=255)


def binarize(gray: np.ndarray) -> np.ndarray:
    return cv2.adaptiveThreshold(
        gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, 35, 15
    )


def detect_double_page(binary: np.ndarray) -> int | None:
    """Deteta página dupla: vale de tinta profundo no terço central → x de corte."""
    ink = (binary < 128).sum(axis=0).astype(np.float32)
    w = binary.shape[1]
    center = ink[w // 3: 2 * w // 3]
    if center.size == 0 or ink.max() == 0:
        return None
    kernel = np.ones(51) / 51.0
    smooth = np.convolve(center, kernel, mode="same")
    x = int(np.argmin(smooth)) + w // 3
    left_ink = ink[: w // 3].mean()
    right_ink = ink[2 * w // 3:].mean()
    if smooth.min() < 0.02 * ink.max() and left_ink > 5 and right_ink > 5:
        return x
    return None


def detect_cut_edges(binary: np.ndarray) -> list[str]:
    """Deteta possíveis cortes/folhas incompletas: tinta a tocar as margens."""
    height = binary.shape[0]
    m = max(2, height // 200)
    edges = {
        "topo": binary[:m, :],
        "fundo": binary[-m:, :],
        "esquerda": binary[:, :m],
        "direita": binary[:, -m:],
    }
    return [nome for nome, faixa in edges.items() if (faixa < 128).mean() > 0.02]

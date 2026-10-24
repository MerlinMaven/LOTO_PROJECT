"""
SmartLOTO Field Service — Service de vision par ordinateur (YOLO-World).
Détection zero-shot basée sur le vision_prompt envoyé par le casque AR Unity.
"""

from __future__ import annotations

import base64
import os
from typing import Optional, Tuple

import numpy as np
from app.config import WEIGHTS_PATH

# Initialisation du modèle YOLO-World
model: Optional[object] = None
YOLO_CONFIDENCE: float = float(os.getenv("YOLO_CONFIDENCE", "0.15"))

try:
    if os.path.exists(WEIGHTS_PATH):
        from ultralytics import YOLO
        model = YOLO(WEIGHTS_PATH)
        print(f"[OK] Modele YOLO-World charge depuis {WEIGHTS_PATH}")
    else:
        print(f"[WARN] YOLO weights not found at {WEIGHTS_PATH}; vision checks will return indeterminate.")
except Exception as exc:
    print(f"[WARN] Ultralytics could not load ({exc}); vision checks will return indeterminate.")
    model = None


def decode_base64_image(base64_str: str) -> Tuple[np.ndarray, bytes]:
    """Décode une chaîne base64 en tableau d'image et octets bruts."""
    if "," in base64_str:
        base64_str = base64_str.split(",")[1]
    try:
        img_data = base64.b64decode(base64_str, validate=True)
    except Exception as exc:
        raise ValueError("Invalid base64 image payload.") from exc
    if not img_data:
        raise ValueError("The received image is empty.")

    try:
        import cv2
        nparr = np.frombuffer(img_data, np.uint8)
        img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
        if img is None:
            raise ValueError("The backend could not decode the received image.")
    except ImportError as exc:
        raise RuntimeError("OpenCV is required to decode incoming images.") from exc

    return img, img_data


def run_detection(image: np.ndarray, vision_prompt: str) -> Tuple[bool, Optional[float]]:
    """Return candidate object presence only; this is not a state verification."""
    global model
    if model is None:
        raise RuntimeError("Modele de detection indisponible; resultat indetermine.")
    if not vision_prompt.strip():
        raise ValueError("Aucune suggestion de detection fournie.")
    try:
        model.set_classes([vision_prompt])
        results = model.predict(image, conf=YOLO_CONFIDENCE)
        boxes = results[0].boxes
        detected = len(boxes) > 0
        confidence = float(boxes[0].conf[0]) if detected else None
        return detected, confidence
    except Exception as exc:
        raise RuntimeError("Detection en echec; resultat indetermine.") from exc

"""
Vision service — YOLO-World zero-shot object detection.

The service decodes a base-64 image sent by the Quest headset, runs YOLO-World
inference to check whether the operator-specified object is present, and returns
a structured result.

Zero-shot detection: the model receives the operator's `vision_prompt` (e.g.
"red padlock", "main circuit breaker in OFF position") as the class label at
inference time.  No prior training on LOTO-specific classes is required.
"""

from __future__ import annotations

import base64

import cv2
import numpy as np
from fastapi import HTTPException

import runtime.database as database
from runtime.config import YOLO_CONFIDENCE


def decode_base64_image(base64_str: str) -> tuple[np.ndarray, bytes]:
    """
    Decode a base-64 image string into an OpenCV array and raw bytes.

    Strips the optional ``data:image/...;base64,`` prefix that some clients
    include (e.g. JavaScript canvas).
    """
    if "," in base64_str:
        base64_str = base64_str.split(",")[1]
    img_data = base64.b64decode(base64_str)
    nparr = np.frombuffer(img_data, np.uint8)
    img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
    return img, img_data


def run_detection(image: np.ndarray, vision_prompt: str) -> tuple[bool, float | None]:
    """
    Run YOLO-World zero-shot detection for `vision_prompt` on `image`.

    Returns
    -------
    (is_detected, confidence)
        `is_detected` is True when at least one bounding box is found above
        the configured confidence threshold.  `confidence` is the highest
        detection score, or None if nothing was detected.

    Raises
    ------
    HTTPException(500)
        When the YOLO model has not been initialised (missing model file or
        failed import).
    """
    if database.model is None:
        raise HTTPException(status_code=500, detail="YOLO-World model unavailable.")

    database.model.set_classes([vision_prompt])
    results = database.model.predict(image, conf=YOLO_CONFIDENCE)

    boxes = results[0].boxes
    is_detected = len(boxes) > 0
    confidence = float(boxes[0].conf[0]) if is_detected else None
    return is_detected, confidence

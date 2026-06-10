"""
VisionService port (Phase 3 extension point).

Defines the abstract interface for zero-shot visual detection.
Phase 2 provides a StubVisionService that always returns "not detected".

When Phase 3 is implemented:
1. Create YOLOWorldVisionService(VisionService) in infrastructure/
2. Swap the dependency in api/deps.py
3. Zero changes to the service or API layers.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field


@dataclass
class BoundingBox:
    x: float
    y: float
    width: float
    height: float


@dataclass
class DetectionResult:
    detected: bool
    confidence: float
    bounding_box: BoundingBox | None = None
    model_used: str | None = None
    raw_labels: list[str] = field(default_factory=list)


class VisionService(ABC):
    """
    Abstract interface for visual object detection.

    Implementations:
    - StubVisionService  (Phase 2, always returns not-detected)
    - YOLOWorldVisionService  (Phase 3, calls YOLO-World model)
    - OpenCVVisionService     (Phase 3, OpenCV-based rules engine)
    """

    @abstractmethod
    async def detect(
        self,
        image_bytes: bytes,
        prompt: str,
        confidence_threshold: float = 0.45,
    ) -> DetectionResult:
        """
        Detect whether the described object is visible in the image.

        Args:
            image_bytes: Raw image bytes (JPEG/PNG) from the Quest camera.
            prompt: Zero-shot detection prompt in English ("red safety padlock").
            confidence_threshold: Minimum confidence to consider detection valid.

        Returns:
            DetectionResult with detected=True/False and confidence score.
        """
        ...


class StubVisionService(VisionService):
    """
    Phase 2 stub — always returns 'not detected'.

    Allows the full intervention workflow to be tested and integrated
    without a GPU or YOLO model present.
    Manual overrides are the only validation path in Phase 2.
    """

    async def detect(
        self,
        image_bytes: bytes,
        prompt: str,
        confidence_threshold: float = 0.45,
    ) -> DetectionResult:
        return DetectionResult(
            detected=False,
            confidence=0.0,
            bounding_box=None,
            model_used="stub_phase2",
        )

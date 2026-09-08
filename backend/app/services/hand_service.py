"""MediaPipe Tasks em VIDEO: resultado sincrono para o mesmo frame do YOLO."""
from pathlib import Path

import cv2

from core.config import settings

# Inclui segmentos dos dedos e contorno da palma.
HAND_CONNECTIONS = (
    (0, 1), (1, 2), (2, 3), (3, 4),
    (0, 5), (5, 6), (6, 7), (7, 8),
    (5, 9), (9, 10), (10, 11), (11, 12),
    (9, 13), (13, 14), (14, 15), (15, 16),
    (13, 17), (0, 17), (17, 18), (18, 19), (19, 20),
)


class HandService:
    def __init__(self):
        if not Path(settings.HAND_MODEL_PATH).is_file():
            raise RuntimeError("Modelo da mao ausente. Execute scripts/setup_hands.py.")
        try:
            import mediapipe as mp
        except ImportError as exc:
            raise RuntimeError("Instale requirements-hands.txt para usar os pontos da mao.") from exc
        self.mp = mp
        self.last_timestamp = -1
        options = mp.tasks.vision.HandLandmarkerOptions(
            base_options=mp.tasks.BaseOptions(model_asset_path=settings.HAND_MODEL_PATH),
            running_mode=mp.tasks.vision.RunningMode.VIDEO,
            num_hands=settings.HAND_MAX_HANDS,
            min_hand_detection_confidence=0.5,
            min_hand_presence_confidence=0.5,
            min_tracking_confidence=0.5,
        )
        self.detector = mp.tasks.vision.HandLandmarker.create_from_options(options)

    def processar_frame(self, frame, timestamp):
        timestamp_ms = max(self.last_timestamp + 1, int(timestamp * 1000))
        self.last_timestamp = timestamp_ms
        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        result = self.detector.detect_for_video(
            self.mp.Image(image_format=self.mp.ImageFormat.SRGB, data=rgb), timestamp_ms)
        height, width = frame.shape[:2]
        detections = []
        for landmarks in result.hand_landmarks:
            points = [(point.x * width, point.y * height) for point in landmarks]
            detections.append(dict(
                classe="mao", landmarks=points,
                x_min=min(x for x, _ in points), y_min=min(y for _, y in points),
                x_max=max(x for x, _ in points), y_max=max(y for _, y in points),
            ))
        return detections

    def close(self):
        self.detector.close()

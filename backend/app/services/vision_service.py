import numpy as np
import pandas as pd
from ultralytics import YOLO

from utils.config import (
    CLASSES,
    EXTERNAL_CLASSES,
    MODEL_PATH,
    USE_EXTERNAL_VALIDATION_DATASET,
)


class VisionService:
    def __init__(self, caminho_pesos=MODEL_PATH):
        self.modelo = YOLO(caminho_pesos)
        self.classes = EXTERNAL_CLASSES if USE_EXTERNAL_VALIDATION_DATASET else CLASSES
        # primeira chamada ao modelo tem custo alto (JIT/threads); absorve isso aqui, fora do loop de captura.
        self.modelo(np.zeros((480, 640, 3), dtype=np.uint8), verbose=False)

    def processar_frame(self, frame):
        resultados = self.modelo(frame, verbose=False)[0]
        deteccoes = []
        for box in resultados.boxes:
            x_min, y_min, x_max, y_max = box.xyxy[0].tolist()
            classe_id = int(box.cls[0])
            if classe_id >= len(self.classes):
                continue
            deteccoes.append(
                {
                    "classe": self.classes[classe_id],
                    "confianca": float(box.conf[0]),
                    "x_min": x_min,
                    "y_min": y_min,
                    "x_max": x_max,
                    "y_max": y_max,
                }
            )
        return pd.DataFrame(deteccoes)

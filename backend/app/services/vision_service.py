"""Combina detecções de produtos e mãos em uma tabela por imagem."""
from pathlib import Path
import time

import numpy as np
import pandas as pd
from ultralytics import YOLO

from core.config import settings
from services.hand_service import ServicoMaos


class ServicoVisao:
    def __init__(self, caminho_pesos=None, device=None):
        self.predict_options = {} if device is None else {"device": device}
        self.model_path = str(Path(caminho_pesos or settings.MODEL_PATH).resolve())
        if not Path(self.model_path).is_file():
            raise FileNotFoundError(f"Pesos ausentes para {settings.MODELO_ATIVO}: {self.model_path}")
        self.modelo = YOLO(self.model_path)
        self.classes = dict(self.modelo.names)
        classes_esperadas = settings.EXTERNAL_CLASSES if settings.USE_EXTERNAL_VALIDATION_DATASET else settings.CLASSES
        if self.classes != dict(enumerate(classes_esperadas)):
            raise ValueError(f"Classes dos pesos incompativeis: {self.classes}; esperado {classes_esperadas}")
        self.model_name = settings.MODELO_ATIVO if caminho_pesos is None else Path(caminho_pesos).parent.name
        print(f"[VISAO] Modelo: {self.model_name}; pesos: {self.model_path}")
        # primeira chamada ao modelo tem custo alto (JIT/threads); absorve isso aqui, fora do loop de captura.
        self.modelo(np.zeros((480, 640, 3), dtype=np.uint8), verbose=False, **self.predict_options)

        self.hands = ServicoMaos() if settings.HAND_LANDMARKS_ENABLED else None

    def fechar(self):
        if self.hands is not None:
            self.hands.close()

    def processar_frame(self, frame, timestamp=None):
        """Usa o mesmo instante para YOLO, mãos e confirmação temporal dos eventos."""
        timestamp = time.monotonic() if timestamp is None else timestamp
        resultados = self.modelo(frame, verbose=False, **self.predict_options)[0]
        deteccoes = []
        for caixa in resultados.boxes:
            x_min, y_min, x_max, y_max = caixa.xyxy[0].tolist()
            classe_id = int(caixa.cls[0])
            if classe_id < 0 or classe_id >= len(self.classes):
                continue
            # Com MediaPipe ativo, suas mãos substituem as caixas de mão do YOLO.
            if self.hands is not None and self.classes[classe_id] == "mao":
                continue
            deteccoes.append(
                {
                    "classe": self.classes[classe_id],
                    "confianca": float(caixa.conf[0]),
                    "x_min": x_min,
                    "y_min": y_min,
                    "x_max": x_max,
                    "y_max": y_max,
                }
            )
        if self.hands is not None:
            deteccoes.extend(self.hands.processar_frame(frame, timestamp))
        tabela_deteccoes = pd.DataFrame(deteccoes)
        tabela_deteccoes.attrs["timestamp"] = timestamp
        return tabela_deteccoes

    # Compatibilidade com consumidores anteriores.
    close = fechar


# Compatibilidade de importação com os nomes anteriores.
VisionService = ServicoVisao

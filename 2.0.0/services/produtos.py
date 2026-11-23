"""Executa YOLO nos produtos e desenha as caixas detectadas."""
import logging

import cv2
import numpy as np
from ultralytics import YOLO

from config import CLASSES, YOLO_DEVICE, YOLO_IMGSZ, caminho_pesos

log = logging.getLogger(__name__)


class DetectorProdutos:
    def __init__(self):
        pesos = caminho_pesos()
        if not pesos.is_file():
            raise FileNotFoundError(f"Treine o modelo antes do monitoramento: {pesos}")
        self.modelo = YOLO(str(pesos))
        if list(self.modelo.names.values()) != CLASSES:
            raise ValueError(f"As classes do modelo devem ser {CLASSES}")
        self.opcoes = {"verbose": False, "imgsz": YOLO_IMGSZ}
        if YOLO_DEVICE:
            self.opcoes["device"] = YOLO_DEVICE
        # A primeira inferencia carrega o modelo no dispositivo; feita aqui, fora do laco de video.
        self.modelo(np.zeros((480, 640, 3), dtype=np.uint8), **self.opcoes)
        self.dispositivo = str(self.modelo.device)
        log.info("YOLO carregado em %s (imgsz=%s)", self.dispositivo, YOLO_IMGSZ)
        if self.dispositivo == "cpu" and not YOLO_DEVICE:
            log.warning("YOLO rodando na CPU: instale o PyTorch com CUDA para usar a GPU")

    def detectar(self, frame):
        produtos = []
        for caixa in self.modelo(frame, **self.opcoes)[0].boxes:
            classe = int(caixa.cls[0])
            if classe >= len(CLASSES) or CLASSES[classe] == "mao":
                continue
            x1, y1, x2, y2 = map(int, caixa.xyxy[0].tolist())
            produto = {"classe": CLASSES[classe], "caixa": (x1, y1, x2, y2)}
            produtos.append(produto)
            cv2.rectangle(frame, (x1, y1), (x2, y2), (255, 160, 0), 2)
            cv2.putText(frame, produto["classe"], (x1, max(20, y1 - 6)),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 160, 0), 2)
        return produtos

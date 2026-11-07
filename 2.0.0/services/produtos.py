"""Executa YOLO nos produtos e desenha as caixas detectadas."""
import cv2
from ultralytics import YOLO

from config import CLASSES, caminho_pesos


class DetectorProdutos:
    def __init__(self):
        pesos = caminho_pesos()
        if not pesos.is_file():
            raise FileNotFoundError(f"Treine o modelo antes do monitoramento: {pesos}")
        self.modelo = YOLO(str(pesos))
        if list(self.modelo.names.values()) != CLASSES:
            raise ValueError(f"As classes do modelo devem ser {CLASSES}")

    def detectar(self, frame):
        produtos = []
        for caixa in self.modelo(frame, verbose=False)[0].boxes:
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

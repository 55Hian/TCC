"""Detecta landmarks da mao e os desenha no quadro."""
from pathlib import Path

import cv2

from config import HAND_MODEL

LIGACOES = ((0,1),(1,2),(2,3),(3,4),(0,5),(5,6),(6,7),(7,8),(5,9),(9,10),(10,11),(11,12),(9,13),(13,14),(14,15),(15,16),(13,17),(0,17),(17,18),(18,19),(19,20))


class DetectorMaos:
    def __init__(self):
        if not HAND_MODEL.is_file():
            raise FileNotFoundError(f"Modelo de landmarks ausente: {HAND_MODEL}")
        import mediapipe as mp
        self.mp = mp
        options = mp.tasks.vision.HandLandmarkerOptions(
            base_options=mp.tasks.BaseOptions(model_asset_path=str(HAND_MODEL)),
            running_mode=mp.tasks.vision.RunningMode.VIDEO, num_hands=2,
        )
        self.detector = mp.tasks.vision.HandLandmarker.create_from_options(options)
        self.ultimo_tempo = -1

    def detectar(self, frame, agora):
        tempo = max(self.ultimo_tempo + 1, int(agora * 1000))
        self.ultimo_tempo = tempo
        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        imagem = self.mp.Image(image_format=self.mp.ImageFormat.SRGB, data=rgb)
        resultado = self.detector.detect_for_video(imagem, tempo)
        h, w = frame.shape[:2]
        maos = [[(int(p.x*w), int(p.y*h)) for p in mao] for mao in resultado.hand_landmarks]
        for mao in maos:
            for a, b in LIGACOES:
                cv2.line(frame, mao[a], mao[b], (40, 220, 80), 2)
            for ponto in mao:
                cv2.circle(frame, ponto, 3, (30, 80, 255), -1)
        return maos

    def fechar(self):
        self.detector.close()

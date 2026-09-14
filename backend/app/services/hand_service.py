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


class ServicoMaos:
    def __init__(self):
        if not Path(settings.HAND_MODEL_PATH).is_file():
            raise RuntimeError("Modelo da mao ausente. Execute scripts/setup_hands.py.")
        try:
            import mediapipe as mp
        except ImportError as erro:
            raise RuntimeError("Instale requirements-hands.txt para usar os pontos da mao.") from erro
        self.mp = mp
        self.last_timestamp = -1
        opcoes_detector = mp.tasks.vision.HandLandmarkerOptions(
            base_options=mp.tasks.BaseOptions(model_asset_path=settings.HAND_MODEL_PATH),
            running_mode=mp.tasks.vision.RunningMode.VIDEO,
            num_hands=settings.HAND_MAX_HANDS,
            min_hand_detection_confidence=0.5,
            min_hand_presence_confidence=0.5,
            min_tracking_confidence=0.5,
        )
        self.detector = mp.tasks.vision.HandLandmarker.create_from_options(opcoes_detector)

    def processar_frame(self, frame, timestamp):
        # O modo VIDEO exige milissegundos estritamente crescentes.
        instante_milissegundos = max(self.last_timestamp + 1, int(timestamp * 1000))
        self.last_timestamp = instante_milissegundos
        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        resultado = self.detector.detect_for_video(
            self.mp.Image(image_format=self.mp.ImageFormat.SRGB, data=rgb), instante_milissegundos)
        altura, largura = frame.shape[:2]
        deteccoes = []
        for landmarks in resultado.hand_landmarks:
            deteccoes.append(_converter_pontos(landmarks, largura, altura))
        return deteccoes

    def fechar(self):
        self.detector.close()

    # Compatibilidade com consumidores anteriores.
    close = fechar


def _converter_pontos(landmarks, largura, altura):
    """Converte coordenadas normalizadas do MediaPipe para pixels da imagem."""
    pontos = [(ponto.x * largura, ponto.y * altura) for ponto in landmarks]
    return dict(
        classe="mao", landmarks=pontos,
        x_min=min(x for x, _ in pontos), y_min=min(y for _, y in pontos),
        x_max=max(x for x, _ in pontos), y_max=max(y for _, y in pontos),
    )


# Compatibilidade de importação com os nomes anteriores.
HandService = ServicoMaos

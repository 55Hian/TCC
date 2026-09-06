import os
import sys
import time

import cv2

PROJ_DIR = os.path.dirname(os.path.abspath(__file__))
if PROJ_DIR not in sys.path:
    sys.path.insert(0, PROJ_DIR)

from controllers.api_controller import enviar_eventos
from services.camera_service import gerador_de_frames
from services.event_service import gerar_eventos
from services.training_service import rodar_pipeline_treinamento
from services.vision_service import VisionService
from core.config import settings


def main():
    # Para treinar, descomente as duas linhas abaixo e execute o arquivo.
    # rodar_pipeline_treinamento()
    # return

    try:
        ia_visao = VisionService()
    except Exception as exc:
        print(f"[ERRO] Arquivo de pesos YOLO nao encontrado ou invalido: {exc}")
        return

    ultimo_processamento = time.time()
    for frame in gerador_de_frames(settings.ESP32_STREAM_URL):
        cv2.imshow("Monitoramento de Estoque", frame)
        tempo_atual = time.time()
        if tempo_atual - ultimo_processamento >= settings.INTERVALO_PROCESSAMENTO:
            df_atual = ia_visao.processar_frame(frame)
            classes_detectadas = df_atual["classe"].tolist() if not df_atual.empty else []
            # print(f"[VISAO] Deteccoes: {len(df_atual)} | Classes: {classes_detectadas}")
            eventos = gerar_eventos(df_atual)
            if eventos:
                enviar_eventos(eventos)
            ultimo_processamento = tempo_atual

        if cv2.waitKey(1) & 0xFF == ord("q"):
            break

    cv2.destroyAllWindows()


if __name__ == "__main__":
    main()

import os
import sys
import time

import cv2

PROJ_DIR = os.path.dirname(os.path.abspath(__file__))
if PROJ_DIR not in sys.path:
    sys.path.insert(0, PROJ_DIR)

from controllers.api_controller import enviar_eventos
from services.camera_service import gerador_de_frames
from services.event_service import EventService
from services.training_service import rodar_pipeline_treinamento
from services.vision_service import VisionService
from services.interaction_overlay import draw_interactions
from core.config import settings


def main():
    # Para treinar, descomente as duas linhas abaixo e execute o arquivo.
    # rodar_pipeline_treinamento()
    # return

    try:
        ia_visao = VisionService()
        interacoes = EventService()
    except Exception as exc:
        print(f"[ERRO] Falha ao iniciar visao: {exc}")
        return

    ultimo_processamento = 0.0
    frames = gerador_de_frames(settings.ESP32_STREAM_URL)
    try:
        for frame in frames:
            tempo_atual = time.monotonic()
            display = frame
            if tempo_atual - ultimo_processamento >= settings.INTERVALO_PROCESSAMENTO:
                df_atual = ia_visao.processar_frame(frame)
                eventos = interacoes.processar(df_atual, df_atual.attrs.get("timestamp", tempo_atual))
                display = draw_interactions(frame, interacoes)
                if eventos:
                    enviar_eventos(eventos)
                ultimo_processamento = tempo_atual
            cv2.imshow("Monitoramento de Estoque", display)
            if cv2.waitKey(1) & 0xFF == ord("q"):
                break
    finally:
        frames.close()
        ia_visao.close()
        cv2.destroyAllWindows()



if __name__ == "__main__":
    main()

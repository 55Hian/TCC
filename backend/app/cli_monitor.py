"""Monitor local com visualização OpenCV e saída de eventos no console."""
import os
import sys
import time

import cv2

PROJ_DIR = os.path.dirname(os.path.abspath(__file__))
if PROJ_DIR not in sys.path:
    sys.path.insert(0, PROJ_DIR)

from controllers.api_controller import enviar_eventos
from services.camera_service import gerador_de_frames
from services.event_service import ServicoEventos
from services.vision_service import ServicoVisao
from services.interaction_overlay import desenhar_interacoes
from core.config import settings


def main():
    try:
        ia_visao = ServicoVisao()
        interacoes = ServicoEventos()
    except Exception as erro:
        print(f"[ERRO] Falha ao iniciar visao: {erro}")
        return

    ultimo_processamento = 0.0
    quadros = gerador_de_frames(settings.ESP32_STREAM_URL)
    try:
        for imagem in quadros:
            tempo_atual = time.monotonic()
            imagem_exibicao = imagem
            if tempo_atual - ultimo_processamento >= settings.INTERVALO_PROCESSAMENTO:
                df_atual = ia_visao.processar_frame(imagem)
                eventos = interacoes.processar(df_atual, df_atual.attrs.get("timestamp", tempo_atual))
                imagem_exibicao = desenhar_interacoes(imagem, interacoes)
                if eventos:
                    enviar_eventos(eventos)
                ultimo_processamento = tempo_atual
            cv2.imshow("Monitoramento de Estoque", imagem_exibicao)
            if cv2.waitKey(1) & 0xFF == ord("q"):
                break
    finally:
        quadros.close()
        ia_visao.fechar()
        cv2.destroyAllWindows()



if __name__ == "__main__":
    main()

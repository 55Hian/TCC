"""Worker de monitoramento (camera + visao + eventos) rodando em thread separada.

Roda em background para nao bloquear o event loop do FastAPI, ja que
`gerador_de_frames` faz I/O de rede bloqueante e a inferencia YOLO e sincrona.
"""
import threading
import time

from core.config import settings
from core.state import state
from services.camera_service import gerador_de_frames
from services.event_service import gerar_eventos
from services.vision_service import VisionService

_thread = None
_stop_flag = threading.Event()


def _loop_monitoramento():
    try:
        ia_visao = VisionService()
    except Exception as exc:
        state.monitor_status = "erro"
        state.monitor_erro = f"Falha ao carregar modelo YOLO: {exc}"
        return

    state.monitor_status = "rodando"
    state.monitor_erro = None
    ultimo_processamento = 0.0

    try:
        for frame in gerador_de_frames(settings.ESP32_STREAM_URL):
            if _stop_flag.is_set():
                break

            agora = time.time()
            if agora - ultimo_processamento >= settings.INTERVALO_PROCESSAMENTO:
                df_atual = ia_visao.processar_frame(frame)
                for evento in gerar_eventos(df_atual):
                    evento["timestamp"] = time.time()
                    state.adicionar_evento(evento)
                ultimo_processamento = agora
    except Exception as exc:
        state.monitor_status = "erro"
        state.monitor_erro = str(exc)
        return

    state.monitor_status = "parado"


def iniciar():
    """Inicia o worker em background. Retorna False se ja estiver rodando."""
    global _thread, _stop_flag
    if _thread is not None and _thread.is_alive():
        return False
    _stop_flag = threading.Event()
    _thread = threading.Thread(target=_loop_monitoramento, daemon=True, name="monitor-worker")
    _thread.start()
    return True


def parar():
    """Sinaliza para o worker parar. So tem efeito apos o proximo frame recebido."""
    global _thread
    if _thread is None or not _thread.is_alive():
        return False
    _stop_flag.set()
    return True


def esta_rodando():
    return _thread is not None and _thread.is_alive()

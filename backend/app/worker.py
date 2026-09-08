"""Worker de monitoramento (camera + visao + eventos) rodando em thread separada.

Roda em background para nao bloquear o event loop do FastAPI, ja que
A camera compartilhada faz I/O de rede em outra thread; a inferencia YOLO e sincrona.
"""
import threading
import time
from datetime import datetime, timezone

from core.config import settings
from core.state import state
from services.shared_camera import camera
from services.event_service import EventService
from services.vision_service import VisionService

_thread = None
_stop_flag = threading.Event()


def _loop_monitoramento():
    try:
        ia_visao = VisionService()
        interacoes = EventService()
        state.monitor_modelo = settings.MODELO_ATIVO
        state.monitor_pesos = settings.MODEL_PATH
    except Exception as exc:
        state.monitor_status = "erro"
        state.monitor_erro = f"Falha ao iniciar visao: {exc}"
        return

    state.monitor_status = "aguardando_camera"
    state.monitor_erro = None
    ultimo_processamento = 0.0

    token = None
    try:
        token = camera.acquire("monitoramento")
        sequence = 0
        while not _stop_flag.is_set():
            item = camera.wait_frame(sequence)
            if item is None:
                state.monitor_status = "aguardando_camera"
                state.monitor_erro = camera.status()["erro"]
                continue
            sequence, frame = item
            if _stop_flag.is_set():
                break
            state.monitor_status = "rodando"
            state.monitor_erro = None

            agora = time.monotonic()
            if agora - ultimo_processamento >= settings.INTERVALO_PROCESSAMENTO:
                df_atual = ia_visao.processar_frame(frame)
                for evento in interacoes.processar(df_atual, df_atual.attrs.get("timestamp", agora)):
                    evento["timestamp"] = datetime.now(timezone.utc).isoformat()
                    state.adicionar_evento(evento)
                ultimo_processamento = agora
                state.ultimo_processamento = time.monotonic()
    except Exception as exc:
        state.monitor_status = "erro"
        state.monitor_erro = str(exc)
        return
    finally:
        try:
            ia_visao.close()
        finally:
            if token is not None:
                camera.release(token)

    state.monitor_status = "parado"


def iniciar():
    """Inicia o worker em background. Retorna False se ja estiver rodando."""
    global _thread, _stop_flag
    if _thread is not None and _thread.is_alive():
        return False
    _stop_flag = threading.Event()
    state.monitor_status = "iniciando"
    state.ultimo_processamento = None
    _thread = threading.Thread(target=_loop_monitoramento, daemon=True, name="monitor-worker")
    _thread.start()
    return True


def parar():
    """Sinaliza para o worker parar. A espera por frames e cancelavel."""
    global _thread
    if _thread is None or not _thread.is_alive():
        return False
    _stop_flag.set()
    return True


def esta_rodando():
    return _thread is not None and _thread.is_alive()


def encerrar():
    parar()
    if _thread:
        _thread.join(timeout=5)

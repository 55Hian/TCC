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
from services.event_service import ServicoEventos
from services.vision_service import ServicoVisao

_tarefa_monitoramento = None
_sinal_parada = threading.Event()


def _loop_monitoramento():
    try:
        ia_visao = ServicoVisao()
        interacoes = ServicoEventos()
        state.monitor_modelo = settings.MODELO_ATIVO
        state.monitor_pesos = settings.MODEL_PATH
    except Exception as erro:
        state.monitor_status = "erro"
        state.monitor_erro = f"Falha ao iniciar visao: {erro}"
        return

    state.monitor_status = "aguardando_camera"
    state.monitor_erro = None
    ultimo_processamento = 0.0

    identificador_consumidor = None
    try:
        identificador_consumidor = camera.adquirir("monitoramento")
        sequencia = 0
        while not _sinal_parada.is_set():
            quadro_recebido = camera.aguardar_frame(sequencia)
            if quadro_recebido is None:
                state.monitor_status = "aguardando_camera"
                state.monitor_erro = camera.status()["erro"]
                continue
            sequencia, imagem = quadro_recebido
            if _sinal_parada.is_set():
                break
            state.monitor_status = "rodando"
            state.monitor_erro = None

            agora = time.monotonic()
            # Limita a frequência da inferência sem interromper a captura compartilhada.
            if agora - ultimo_processamento < settings.INTERVALO_PROCESSAMENTO:
                continue

            deteccoes = ia_visao.processar_frame(imagem)
            for evento in interacoes.processar(deteccoes, deteccoes.attrs.get("timestamp", agora)):
                evento["timestamp"] = datetime.now(timezone.utc).isoformat()
                state.adicionar_evento(evento)
            ultimo_processamento = agora
            state.ultimo_processamento = time.monotonic()
    except Exception as erro:
        state.monitor_status = "erro"
        state.monitor_erro = str(erro)
        return
    finally:
        # Libera os dois recursos mesmo se o processamento ou o fechamento falhar.
        try:
            ia_visao.fechar()
        finally:
            if identificador_consumidor is not None:
                camera.liberar(identificador_consumidor)

    state.monitor_status = "parado"


def iniciar():
    """Inicia o worker em background. Retorna False se ja estiver rodando."""
    global _tarefa_monitoramento, _sinal_parada
    if esta_rodando():
        return False
    _sinal_parada = threading.Event()
    state.monitor_status = "iniciando"
    state.ultimo_processamento = None
    _tarefa_monitoramento = threading.Thread(target=_loop_monitoramento, daemon=True, name="monitor-worker")
    _tarefa_monitoramento.start()
    return True


def parar():
    """Sinaliza para o worker parar. A espera por frames e cancelavel."""
    if not esta_rodando():
        return False
    _sinal_parada.set()
    return True


def esta_rodando():
    return _tarefa_monitoramento is not None and _tarefa_monitoramento.is_alive()


def encerrar():
    parar()
    if _tarefa_monitoramento:
        _tarefa_monitoramento.join(timeout=5)

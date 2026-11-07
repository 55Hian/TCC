"""Ciclo de camera, deteccao e publicacao de eventos."""
import threading
import time

import cv2

from config import CAMERA_URL
from services.camera import frames
from services.api_client import enviar_evento_camera
from services.interacoes import ConfirmadorInteracoes
from services.maos import DetectorMaos
from services.produtos import DetectorProdutos


class Monitoramento:
    def __init__(self):
        self.status = "parado"
        self.erro = None
        self.eventos = []
        self.ultimo_jpeg = None
        self.parada = threading.Event()
        self.thread = None

    def iniciar(self):
        if self.thread and self.thread.is_alive():
            return False
        self.parada = threading.Event()
        self.status, self.erro = "iniciando", None
        self.thread = threading.Thread(target=self._executar, daemon=True, name="monitoramento")
        self.thread.start()
        return True

    def parar(self):
        self.parada.set()
        if self.thread:
            self.thread.join(timeout=5)
        return self.status

    def _executar(self):
        maos = produtos = None
        try:
            produtos = DetectorProdutos()
            maos = DetectorMaos()
            interacoes = ConfirmadorInteracoes()
            self.status = "rodando"
            for frame in frames(CAMERA_URL, self.parada):
                if self.parada.is_set():
                    break
                agora = time.monotonic()
                deteccoes_produto = produtos.detectar(frame)
                deteccoes_mao = maos.detectar(frame, agora)
                novos_eventos = interacoes.atualizar(deteccoes_mao, deteccoes_produto, agora)
                for evento in novos_eventos:
                    enviar_evento_camera(evento)
                ok, jpg = cv2.imencode(".jpg", frame)
                if ok:
                    self.ultimo_jpeg = jpg.tobytes()
        except Exception as erro:
            self.erro, self.status = str(erro), "erro"
            return
        finally:
            if maos:
                maos.fechar()
        self.status = "parado"


monitor = Monitoramento()





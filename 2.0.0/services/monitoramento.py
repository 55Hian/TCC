"""Ciclo de camera, deteccao e publicacao de eventos."""
import collections
import logging
import queue
import threading
import time

import cv2

from config import CAMERA_URL
from services.camera import UltimoQuadro, decodificar
from services.api_client import enviar_evento_camera
from services.interacoes import ConfirmadorInteracoes
from services.maos import DetectorMaos
from services.produtos import DetectorProdutos

log = logging.getLogger(__name__)
QUALIDADE_JPEG_SAIDA = 80


class Medidor:
    """Media movel das ultimas amostras: FPS, tempo por etapa e latencia."""

    def __init__(self, janela=30):
        self.amostras = collections.deque(maxlen=janela)
        self.processados = 0
        self.descartados = 0

    def registrar(self, fim, etapas, latencia_ms, descartados):
        self.amostras.append((fim, etapas, latencia_ms))
        self.processados += 1
        self.descartados += descartados

    def resumo(self, dispositivo=None):
        n = len(self.amostras)
        if n == 0:
            return {}
        duracao = self.amostras[-1][0] - self.amostras[0][0]
        medias = {nome: round(sum(a[1][nome] for a in self.amostras) / n, 1) for nome in self.amostras[-1][1]}
        return {
            "fps": round((n - 1) / duracao, 1) if duracao > 0 else None,
            "latencia_ms": round(sum(a[2] for a in self.amostras) / n, 1),
            "etapas_ms": medias,
            "quadros_processados": self.processados,
            "quadros_descartados": self.descartados,
            "dispositivo_yolo": dispositivo,
        }


class Monitoramento:
    def __init__(self):
        self.status = "parado"
        self.erro = None
        self.eventos = []
        self.ultimo_jpeg = None
        self.metricas = {}
        self.parada = threading.Event()
        self.thread = None
        self._cond_quadro = threading.Condition()
        self._seq_quadro = 0
        self._fila_eventos = queue.Queue(maxsize=200)

    def ativo(self):
        return bool(self.thread and self.thread.is_alive())

    def iniciar(self):
        if self.ativo():
            return False
        self.parada = threading.Event()
        self.status, self.erro, self.metricas = "iniciando", None, {}
        self.thread = threading.Thread(target=self._executar, daemon=True, name="monitoramento")
        self.thread.start()
        return True

    def parar(self):
        self.parada.set()
        if self.thread:
            self.thread.join(timeout=5)
        with self._cond_quadro:
            self._cond_quadro.notify_all()
        return self.status

    def aguardar_quadro(self, ultimo_seq, timeout=2.0):
        """Usado pela rota de streaming: espera um quadro processado mais novo."""
        with self._cond_quadro:
            self._cond_quadro.wait_for(lambda: self._seq_quadro != ultimo_seq or not self.ativo(), timeout)
            return self._seq_quadro, self.ultimo_jpeg

    def _publicar_quadro(self, dados):
        with self._cond_quadro:
            self.ultimo_jpeg = dados
            self._seq_quadro += 1
            self._cond_quadro.notify_all()

    def _publicar_evento(self, evento):
        try:
            self._fila_eventos.put_nowait(evento)
        except queue.Full:
            log.warning("Fila de eventos cheia; evento descartado: %s", evento)

    def _enviar_eventos(self, parada, fila, prazo_final=3.0):
        """Envia os eventos fora do laco de video; falhas nao derrubam o monitoramento.

        Ao parar, os eventos pendentes ainda tem ate `prazo_final` segundos para serem enviados.
        """
        limite = None
        while True:
            if parada.is_set():
                limite = limite or time.monotonic() + prazo_final
                if fila.empty() or time.monotonic() > limite:
                    break
            try:
                evento = fila.get(timeout=0.5)
            except queue.Empty:
                continue
            for tentativa in range(1, 4):
                try:
                    enviar_evento_camera(evento)
                    break
                except Exception as erro:
                    log.warning("Falha ao enviar evento (tentativa %s/3): %s", tentativa, erro)
                    if parada.wait(1):
                        break
            else:
                log.error("Evento descartado apos 3 tentativas: %s", evento)
        descartados = fila.qsize()
        while not fila.empty():
            fila.get_nowait()
        if descartados:
            log.error("%s evento(s) nao enviados ao parar o monitoramento", descartados)

    def _executar(self):
        maos = produtos = leitor = None
        # Cada execucao tem sua propria fila: uma thread de envio antiga, ainda encerrando,
        # nao consome eventos de uma nova execucao.
        self._fila_eventos = queue.Queue(maxsize=200)
        enviador = threading.Thread(target=self._enviar_eventos, args=(self.parada, self._fila_eventos),
                                    daemon=True, name="envio-eventos")
        try:
            produtos = DetectorProdutos()
            maos = DetectorMaos()
            interacoes = ConfirmadorInteracoes()
            medidor = Medidor()
            enviador.start()
            leitor = UltimoQuadro(CAMERA_URL, self.parada).iniciar()
            self.status = "aguardando_camera"
            seq = 0
            while not self.parada.is_set():
                item = leitor.proximo(seq)
                if item is None:
                    if leitor.erro:
                        self.status, self.erro = "aguardando_camera", f"Camera principal: {leitor.erro}"
                    continue
                novo_seq, jpeg, chegada = item
                descartados = novo_seq - seq - 1 if seq else 0
                seq = novo_seq
                inicio = time.perf_counter()
                frame = decodificar(jpeg)
                if frame is None:
                    continue
                t_decod = time.perf_counter()
                agora = time.monotonic()
                deteccoes_produto = produtos.detectar(frame)
                t_yolo = time.perf_counter()
                deteccoes_mao = maos.detectar(frame, agora)
                t_maos = time.perf_counter()
                for evento in interacoes.atualizar(deteccoes_mao, deteccoes_produto, agora):
                    self._publicar_evento(evento)
                ok, jpg = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, QUALIDADE_JPEG_SAIDA])
                fim = time.perf_counter()
                if ok:
                    self._publicar_quadro(jpg.tobytes())
                self.status, self.erro = "rodando", None
                medidor.registrar(fim, {
                    "decodificacao": (t_decod - inicio) * 1000,
                    "yolo": (t_yolo - t_decod) * 1000,
                    "maos": (t_maos - t_yolo) * 1000,
                    "saida": (fim - t_maos) * 1000,
                    "total": (fim - inicio) * 1000,
                }, (fim - chegada) * 1000, descartados)
                self.metricas = medidor.resumo(produtos.dispositivo)
        except Exception as erro:
            log.exception("Monitoramento interrompido")
            self.erro, self.status = str(erro), "erro"
            return
        finally:
            self.parada.set()
            if leitor:
                leitor.aguardar(timeout=5)
            if enviador.is_alive():
                # A thread de envio tem prazo proprio para os pendentes; nao segura o encerramento.
                enviador.join(timeout=1)
            if maos:
                maos.fechar()
        self.status = "parado"


monitor = Monitoramento()





"""Buffer circular e clipes de evidencia da segunda camera USB."""
import collections
import logging
import threading
import time
from datetime import datetime
from pathlib import Path

import cv2
import numpy as np

from config import (
    CAMERA_USB_BACKEND, VIDEO_AFTER_SECONDS, VIDEO_BEFORE_SECONDS, VIDEO_BUFFER_SECONDS,
    VIDEO_DIR, camera_usb_backend, camera_usb_source,
)

log = logging.getLogger(__name__)


class CameraSecundaria:
    def __init__(self, fonte=None, pasta_saida=None, segundos_antes=None,
                 segundos_depois=None, fps_buffer=10, qualidade_jpeg=78,
                 segundos_buffer=None):
        self.fonte = camera_usb_source() if fonte is None else fonte
        self.backend_nome = CAMERA_USB_BACKEND
        self.backend = camera_usb_backend(cv2)
        self.pasta_saida = Path(pasta_saida or VIDEO_DIR)
        self.segundos_antes = VIDEO_BEFORE_SECONDS if segundos_antes is None else segundos_antes
        self.segundos_depois = VIDEO_AFTER_SECONDS if segundos_depois is None else segundos_depois
        self.segundos_buffer = VIDEO_BUFFER_SECONDS if segundos_buffer is None else segundos_buffer
        self.fps_buffer = fps_buffer
        self.qualidade_jpeg = qualidade_jpeg
        self._duracao_armazenada = self.segundos_buffer + self.segundos_antes + self.segundos_depois + 1
        self._pasta_buffer = self.pasta_saida / ".buffer"
        self._frames = collections.deque()
        self._bytes_buffer = 0
        self._lock = threading.RLock()
        self._parar = threading.Event()
        self._thread = None
        self._estado = "parado"
        self._erro = None
        self._gravacoes = {}

    def iniciar(self):
        with self._lock:
            if self._thread and self._thread.is_alive():
                return False
            self.pasta_saida.mkdir(parents=True, exist_ok=True)
            self._pasta_buffer.mkdir(parents=True, exist_ok=True)
            self._frames.clear()
            self._bytes_buffer = 0
            self._parar.clear()
            self._estado, self._erro = "conectando", None
            self._thread = threading.Thread(target=self._capturar, daemon=True, name="camera-usb")
            self._thread.start()
            return True

    def parar(self):
        self._parar.set()
        if self._thread:
            self._thread.join(timeout=5)
        with self._lock:
            self._estado = "parado"

    def _abrir_camera(self):
        if self.backend is None:
            return cv2.VideoCapture(self.fonte)
        return cv2.VideoCapture(self.fonte, self.backend)

    def _capturar(self):
        self._carregar_buffer()
        intervalo = 1 / self.fps_buffer
        proximo_frame = 0.0
        camera = None
        while not self._parar.is_set():
            try:
                camera = self._abrir_camera()
                if not camera.isOpened():
                    with self._lock:
                        self._estado, self._erro = "erro", f"Nao foi possivel abrir a camera USB {self.fonte}"
                    camera.release()
                    camera = None
                    self._parar.wait(3)
                    continue
                with self._lock:
                    self._estado, self._erro = "rodando", None
                while not self._parar.is_set():
                    sucesso, imagem = camera.read()
                    if not sucesso:
                        raise RuntimeError("Falha lendo a camera USB")
                    agora = time.time()
                    if agora < proximo_frame:
                        continue
                    proximo_frame = agora + intervalo
                    ok, jpeg = cv2.imencode(
                        ".jpg", imagem,
                        [cv2.IMWRITE_JPEG_QUALITY, self.qualidade_jpeg],
                    )
                    if ok:
                        with self._lock:
                            self._guardar_frame(agora, jpeg.tobytes())
            except Exception as erro:
                with self._lock:
                    self._estado, self._erro = "reconectando", str(erro)
                log.warning("Camera USB: %s; reconectando", erro)
                self._parar.wait(1)
            finally:
                if camera is not None:
                    camera.release()
                    camera = None
        with self._lock:
            self._estado = "parado"

    def _carregar_buffer(self):
        limite = time.time() - self._duracao_armazenada
        arquivos = []
        for caminho in self._pasta_buffer.glob("*.jpg"):
            try:
                instante = int(caminho.stem) / 1_000_000
            except ValueError:
                caminho.unlink(missing_ok=True)
                continue
            if instante < limite:
                caminho.unlink(missing_ok=True)
            else:
                arquivos.append((instante, caminho, caminho.stat().st_size))
        with self._lock:
            self._frames.extend(sorted(arquivos, key=lambda item: item[0]))
            self._bytes_buffer = sum(tamanho for _, _, tamanho in arquivos)

    def _guardar_frame(self, instante, dados):
        caminho = self._pasta_buffer / f"{int(instante * 1_000_000)}.jpg"
        caminho.write_bytes(dados)
        self._frames.append((instante, caminho, len(dados)))
        self._bytes_buffer += len(dados)
        limite = instante - self._duracao_armazenada
        while self._frames and self._frames[0][0] < limite:
            _, antigo, tamanho = self._frames.popleft()
            self._bytes_buffer -= tamanho
            antigo.unlink(missing_ok=True)

    def agendar_gravacao(self, id_evento, timestamp):
        instante = timestamp.timestamp() if isinstance(timestamp, datetime) else float(timestamp)
        agora = time.time()
        if instante > agora + 1:
            raise ValueError("O timestamp da retirada nao pode estar no futuro")
        if agora - instante > self.segundos_buffer:
            raise ValueError("O timestamp esta fora do periodo de retencao do buffer")
        caminho = self.pasta_saida / f"evento_{id_evento}.mp4"
        with self._lock:
            if self._estado != "rodando":
                raise RuntimeError("A camera USB nao esta pronta")
            if caminho.exists() or id_evento in self._gravacoes:
                raise ValueError("Ja existe uma gravacao para esse evento")
            if not self._frames or self._frames[0][0] > instante - self.segundos_antes:
                raise RuntimeError("O buffer ainda nao tem todos os segundos anteriores ao evento")
            if instante + self.segundos_depois <= agora and self._frames[-1][0] < instante + self.segundos_depois:
                raise RuntimeError("O buffer ainda nao contem o periodo posterior ao evento")
            job = {"id_evento": id_evento, "status": "agendada", "caminho": None, "erro": None}
            self._gravacoes[id_evento] = job
        tarefa = threading.Thread(
            target=self._gravar, args=(id_evento, instante),
            daemon=True, name=f"video-evento-{id_evento}",
        )
        tarefa.start()
        return dict(job)

    def _gravar(self, id_evento, instante):
        caminho = None
        erro = None
        try:
            fim = instante + self.segundos_depois
            espera = fim - time.time()
            if espera > 0 and self._parar.wait(espera):
                raise RuntimeError("A API encerrou antes do fim do clipe")
            inicio = instante - self.segundos_antes
            with self._lock:
                janela = [(t, caminho.read_bytes()) for t, caminho, _ in self._frames if inicio <= t <= fim]
            self._validar_janela(janela, inicio, fim)
            caminho = self._escrever_video(id_evento, janela)
        except Exception as falha:
            erro = str(falha)
            log.exception("Falha gravando clipe do evento %s", id_evento)
        with self._lock:
            self._gravacoes[id_evento].update(
                status="concluida" if caminho else "erro",
                caminho=caminho,
                erro=erro,
            )
        try:
            from services.database import atualizar_video_evento
            atualizar_video_evento(id_evento, caminho, "concluida" if caminho else "erro")
        except Exception:
            log.exception("Nao foi possivel atualizar o registro do clipe do evento %s", id_evento)

    def _validar_janela(self, janela, inicio, fim):
        tolerancia = max(0.25, 2 / self.fps_buffer)
        if len(janela) < 2 or janela[0][0] > inicio + tolerancia or janela[-1][0] < fim - tolerancia:
            raise RuntimeError("O buffer nao contem todo o intervalo do clipe")
        maior_intervalo = max(1.0, 5 / self.fps_buffer)
        for anterior, atual in zip(janela, janela[1:]):
            if atual[0] - anterior[0] > maior_intervalo:
                raise RuntimeError("Ha uma interrupcao no buffer durante o intervalo do clipe")

    def _escrever_video(self, id_evento, janela):
        if len(janela) < 2:
            raise RuntimeError("Nao ha frames suficientes para montar o clipe")
        primeiro = cv2.imdecode(np.frombuffer(janela[0][1], np.uint8), cv2.IMREAD_COLOR)
        if primeiro is None:
            raise RuntimeError("O primeiro frame do clipe esta corrompido")
        altura, largura = primeiro.shape[:2]
        duracao = janela[-1][0] - janela[0][0]
        fps = (len(janela) - 1) / duracao if duracao > 0 else self.fps_buffer
        caminho = self.pasta_saida / f"evento_{id_evento}.mp4"
        escritor = cv2.VideoWriter(
            str(caminho), cv2.VideoWriter_fourcc(*"mp4v"), fps, (largura, altura)
        )
        if not escritor.isOpened():
            raise RuntimeError(f"Nao foi possivel criar o video {caminho.name}")
        try:
            for _, dados in janela:
                frame = cv2.imdecode(np.frombuffer(dados, np.uint8), cv2.IMREAD_COLOR)
                if frame is not None:
                    escritor.write(frame)
        finally:
            escritor.release()
        return str(caminho)

    def status(self):
        with self._lock:
            duracao_buffer = self._frames[-1][0] - self._frames[0][0] if len(self._frames) > 1 else 0
            return {
                "status": self._estado,
                "erro": self._erro,
                "fonte": str(self.fonte),
                "backend": self.backend_nome,
                "frames_buffer": len(self._frames),
                "segundos_buffer": round(duracao_buffer, 1),
                "segundos_retencao": self.segundos_buffer,
                "segundos_antes": self.segundos_antes,
                "segundos_depois": self.segundos_depois,
                "megabytes_buffer": round(self._bytes_buffer / (1024 * 1024), 1),
            }

    def status_gravacao(self, id_evento):
        with self._lock:
            job = self._gravacoes.get(id_evento)
            return None if job is None else dict(job)


camera_secundaria = CameraSecundaria()

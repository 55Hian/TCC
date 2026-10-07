"""
Gravação do vídeo de retirada de produtos.

Uso no backend da balança:

    from gravador_retirada import GravadorRetirada

    gravador = GravadorRetirada(fonte=0, pasta_saida="videos")
    gravador.iniciar()                      # uma vez, na inicialização do backend

    # logo depois de inserir (e confirmar) o evento no banco:
    gravador.gravar_retirada(id_evento, ao_concluir=salvar_caminho_no_banco)

O vídeo é evidência anexada ao evento: se a gravação falhar, o erro vai para
o log e o backend segue normalmente. Nenhuma exceção sai de gravar_retirada().
"""

import collections
import logging
import re
import threading
import time
from datetime import datetime
from pathlib import Path

import cv2
import numpy as np

log = logging.getLogger(__name__)


class GravadorRetirada:

    def __init__(
        self,
        fonte=0,
        pasta_saida="videos",
        segundos_antes=30,
        segundos_depois=3,
        fps_buffer=10,
        qualidade_jpeg=80,
        backend=None,
    ):
        self.fonte = fonte  # índice da webcam, URL MJPEG ou RTSP
        # Backend do OpenCV (ex.: cv2.CAP_DSHOW no Windows). None = padrão do OpenCV.
        self.backend = backend
        self.pasta_saida = Path(pasta_saida)
        self.segundos_antes = segundos_antes
        self.segundos_depois = segundos_depois
        self.fps_buffer = fps_buffer
        self.qualidade_jpeg = qualidade_jpeg

        # Margem de 10 s: enquanto uma gravação espera o "pós-evento", o buffer
        # continua andando e não pode descartar o início da janela.
        tamanho = int((segundos_antes + segundos_depois + 10) * fps_buffer)
        self._buffer = collections.deque(maxlen=tamanho)
        self._lock = threading.Lock()
        self._parar = threading.Event()
        self._thread = None

    # ------------------------------------------------------------------
    # Captura contínua
    # ------------------------------------------------------------------

    def iniciar(self):
        if self._thread is not None and self._thread.is_alive():
            return
        self.pasta_saida.mkdir(parents=True, exist_ok=True)
        self._parar.clear()
        self._thread = threading.Thread(
            target=self._capturar, name="captura-video", daemon=True
        )
        self._thread.start()

    def parar(self):
        self._parar.set()
        if self._thread is not None:
            self._thread.join(timeout=5)

    def _capturar(self):
        camera = None
        ultimo = 0.0
        intervalo = 1.0 / self.fps_buffer

        while not self._parar.is_set():
            if camera is None:
                if self.backend is None:
                    camera = cv2.VideoCapture(self.fonte)
                else:
                    camera = cv2.VideoCapture(self.fonte, self.backend)
                if not camera.isOpened():
                    log.error("Não foi possível abrir a câmera %s. Nova tentativa em 5 s.", self.fonte)
                    camera.release()
                    camera = None
                    self._parar.wait(5)
                    continue

            ok, frame = camera.read()
            if not ok:
                log.warning("Falha na leitura da câmera; reabrindo.")
                camera.release()
                camera = None
                self._parar.wait(1)
                continue

            # Lê todos os frames (para a câmera não acumular atraso), mas só
            # guarda fps_buffer por segundo: o vídeo de evidência não precisa de mais.
            agora = time.time()
            if agora - ultimo < intervalo:
                continue
            ultimo = agora

            ok, jpeg = cv2.imencode(
                ".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, self.qualidade_jpeg]
            )
            if ok:
                with self._lock:
                    self._buffer.append((agora, jpeg.tobytes()))

        if camera is not None:
            camera.release()

    # ------------------------------------------------------------------
    # Gravação do evento
    # ------------------------------------------------------------------

    def gravar_retirada(self, id_evento, instante=None, ao_concluir=None):
        """
        Agenda a gravação e retorna imediatamente.

        instante:    horário da retirada (epoch em segundos ou datetime).
                     Padrão: agora.
        ao_concluir: função opcional chamada como ao_concluir(id_evento, caminho),
                     com caminho=None se não foi possível gravar. Use para
                     gravar o caminho do vídeo na tabela evento.
        """
        try:
            if isinstance(instante, datetime):
                instante = instante.timestamp()
            elif instante is None:
                instante = time.time()

            # Thread não-daemon: se o backend for encerrado durante a espera
            # do pós-evento, o clipe ainda é gravado.
            threading.Thread(
                target=self._gravar,
                args=(id_evento, instante, ao_concluir),
                name=f"gravacao-{id_evento}",
            ).start()
        except Exception:
            log.exception("Não foi possível agendar a gravação do evento %s", id_evento)

    def _gravar(self, id_evento, instante, ao_concluir):
        caminho = None
        try:
            espera = instante + self.segundos_depois - time.time()
            if espera > 0:
                time.sleep(espera)

            inicio = instante - self.segundos_antes
            fim = instante + self.segundos_depois
            with self._lock:
                janela = [(ts, jpg) for ts, jpg in self._buffer if inicio <= ts <= fim]

            caminho = self._escrever_video(id_evento, janela)
        except Exception:
            log.exception("Falha ao gravar o vídeo do evento %s", id_evento)

        if ao_concluir is not None:
            try:
                ao_concluir(id_evento, caminho)
            except Exception:
                log.exception("Falha no callback do evento %s", id_evento)

    def _escrever_video(self, id_evento, janela):
        if len(janela) < 2:
            log.warning("Evento %s: frames insuficientes na janela; vídeo não gerado.", id_evento)
            return None

        # O FPS do arquivo vem dos timestamps reais. Webcams raramente entregam
        # o FPS nominal e, com um valor fixo, o vídeo tocaria acelerado ou lento.
        duracao = janela[-1][0] - janela[0][0]
        fps = (len(janela) - 1) / duracao if duracao > 0 else self.fps_buffer

        primeiro = cv2.imdecode(np.frombuffer(janela[0][1], np.uint8), cv2.IMREAD_COLOR)
        altura, largura = primeiro.shape[:2]

        self.pasta_saida.mkdir(parents=True, exist_ok=True)
        nome = re.sub(r"[^\w\-]", "_", str(id_evento))
        caminho = self.pasta_saida / f"evento_{nome}.mp4"

        escritor = cv2.VideoWriter(
            str(caminho), cv2.VideoWriter_fourcc(*"mp4v"), fps, (largura, altura)
        )
        if not escritor.isOpened():
            raise RuntimeError(f"VideoWriter não abriu {caminho}")

        try:
            for _, jpg in janela:
                escritor.write(cv2.imdecode(np.frombuffer(jpg, np.uint8), cv2.IMREAD_COLOR))
        finally:
            escritor.release()

        log.info("Evento %s: vídeo salvo em %s (%d frames, %.1f fps)", id_evento, caminho, len(janela), fps)
        return str(caminho)

    # ------------------------------------------------------------------
    # Retenção
    # ------------------------------------------------------------------

    def apagar_antigos(self, dias):
        """Apaga clipes com mais de `dias` dias. Chame na inicialização ou periodicamente."""
        limite = time.time() - dias * 86400
        for arquivo in self.pasta_saida.glob("evento_*.mp4"):
            if arquivo.stat().st_mtime < limite:
                arquivo.unlink()
                log.info("Clipe antigo removido: %s", arquivo)

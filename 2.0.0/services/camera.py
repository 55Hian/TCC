"""Leitura e reconexao do stream MJPEG da camera."""
import logging
import threading
import time
import urllib.request

import cv2
import numpy as np

log = logging.getLogger(__name__)
TAMANHO_MAXIMO_JPEG = 4 * 1024 * 1024


def decodificar(jpeg):
    return cv2.imdecode(np.frombuffer(jpeg, np.uint8), cv2.IMREAD_COLOR)


def frames(url, stop=None):
    """Entrega todos os quadros em sequencia (usado na captura para treino)."""
    stop = stop or threading.Event()
    while not stop.is_set():
        try:
            with urllib.request.urlopen(url, timeout=4) as response:
                for jpeg in _jpegs(response, stop):
                    image = decodificar(jpeg)
                    if image is not None:
                        yield image
        except Exception as error:
            print(f"[camera] {error}; tentando novamente")
            stop.wait(2)


def _jpegs(response, stop):
    """Separa os JPEGs do fluxo MJPEG; trata varios quadros por bloco lido."""
    buffer = bytearray()
    while not stop.is_set():
        chunk = response.read1(65536)
        if not chunk:
            raise ConnectionError("Stream da camera encerrou")
        buffer += chunk
        while True:
            start = buffer.find(b"\xff\xd8")
            if start < 0:
                del buffer[:-1]
                break
            end = buffer.find(b"\xff\xd9", start + 2)
            if end < 0:
                del buffer[:start]
                if len(buffer) > TAMANHO_MAXIMO_JPEG:
                    raise ValueError("Quadro JPEG maior que 4 MB")
                break
            jpeg = bytes(buffer[start:end + 2])
            del buffer[:end + 2]
            yield jpeg


class UltimoQuadro:
    """Le o stream em uma thread propria e guarda somente o JPEG mais recente.

    Quem consome pede sempre o quadro mais novo; quadros que chegaram enquanto o
    consumidor processava o anterior sao descartados, evitando atraso acumulado.
    """

    def __init__(self, url, parada):
        self.url = url
        self.parada = parada
        self.erro = None
        self._cond = threading.Condition()
        self._jpeg = None
        self._chegada = 0.0
        self._seq = 0
        self._thread = threading.Thread(target=self._ler, daemon=True, name="leitor-camera")

    def iniciar(self):
        self._thread.start()
        return self

    def aguardar(self, timeout=None):
        self._thread.join(timeout)

    def _ler(self):
        while not self.parada.is_set():
            try:
                with urllib.request.urlopen(self.url, timeout=4) as response:
                    for jpeg in _jpegs(response, self.parada):
                        with self._cond:
                            self._jpeg, self._chegada = jpeg, time.perf_counter()
                            self._seq += 1
                            self.erro = None
                            self._cond.notify_all()
            except Exception as error:
                self.erro = str(error)
                log.warning("Camera principal: %s; tentando novamente", error)
                self.parada.wait(2)
        with self._cond:
            self._cond.notify_all()

    def proximo(self, ultimo_seq, timeout=1.0):
        """Espera um quadro mais novo que ultimo_seq e devolve (seq, jpeg, chegada) ou None."""
        with self._cond:
            self._cond.wait_for(lambda: self._seq != ultimo_seq or self.parada.is_set(), timeout)
            if self._seq == ultimo_seq:
                return None
            return self._seq, self._jpeg, self._chegada


"""Uma conexao por processo, com ultimo frame compartilhado entre consumidores."""
import threading
import time

from core.config import settings
from services.camera_service import gerador_de_frames


IDADE_MAXIMA_FRAME_SEGUNDOS = 3


class CameraCompartilhada:
    def __init__(self, url, source=gerador_de_frames):
        self.url = url
        self.source = source
        self._trava_ciclo = threading.RLock()
        self._consumidores = {}
        self._condicao = threading.Condition()
        self._sinal_parada = threading.Event()
        self._tarefa = None
        self._imagem = None
        self._sequencia = 0
        self._ultimo_recebimento = None
        self._status = "parado"
        self._erro = None

    def iniciar(self):
        with self._condicao:
            if self._tarefa and self._tarefa.is_alive():
                return
            self._sinal_parada.clear()
            self._imagem = None
            self._ultimo_recebimento = None
            self._status = "conectando"
            self._tarefa = threading.Thread(target=self._ler_imagens, name="camera-reader", daemon=True)
            self._tarefa.start()

    def adquirir(self, name):
        # Impede fechar a câmera durante uma aquisição de consumidor.
        with self._trava_ciclo:
            identificador_consumidor = object()
            self.iniciar()
            self._consumidores[identificador_consumidor] = name
            return identificador_consumidor

    def liberar(self, token):
        with self._trava_ciclo:
            self._consumidores.pop(token, None)
            if not self._consumidores:
                self.fechar()

    def _registrar_status(self, status, error=None):
        with self._condicao:
            self._status, self._erro = status, error
            self._imagem = None
            self._condicao.notify_all()

    def _ler_imagens(self):
        try:
            for imagem in self.source(self.url, self._sinal_parada, self._registrar_status):
                if self._sinal_parada.is_set():
                    break
                with self._condicao:
                    self._imagem = imagem.copy()
                    self._sequencia += 1
                    self._ultimo_recebimento = time.monotonic()
                    self._status, self._erro = "recebendo", None
                    self._condicao.notify_all()
        except Exception as erro:
            self._registrar_status("erro", str(erro))
        finally:
            if self._sinal_parada.is_set():
                self._registrar_status("parado")

    def _tem_frame_novo(self, sequencia):
        """Consulta sob a condição adquirida; impede imagens antigas ou repetidas."""
        return (self._imagem is not None and self._sequencia > sequencia
                and time.monotonic() - self._ultimo_recebimento <= IDADE_MAXIMA_FRAME_SEGUNDOS)

    def aguardar_frame(self, sequence=0, timeout=0.5):
        """Retorna copia independente; nunca entrega frame com mais de 3 segundos."""
        with self._condicao:
            self._condicao.wait_for(
                lambda: self._sinal_parada.is_set() or self._tem_frame_novo(sequence),
                timeout=timeout,
            )
            if self._sinal_parada.is_set() or not self._tem_frame_novo(sequence):
                return None
            return self._sequencia, self._imagem.copy()

    def gerar_frames(self, stop_event=None, timeout=15):
        identificador_consumidor = self.adquirir("captura")
        try:
            sequencia = 0
            ultimo = time.monotonic()
            while not self._sinal_parada.is_set() and not (stop_event and stop_event.is_set()):
                item = self.aguardar_frame(sequencia)
                if item is None:
                    if time.monotonic() - ultimo >= timeout:
                        raise TimeoutError("Camera sem novos frames")
                    continue
                sequencia, imagem = item
                ultimo = time.monotonic()
                yield imagem
        finally:
            self.liberar(identificador_consumidor)

    def status(self):
        with self._trava_ciclo, self._condicao:
            idade = None if self._ultimo_recebimento is None else time.monotonic() - self._ultimo_recebimento
            status = self._status
            if status == "recebendo" and idade is not None and idade > IDADE_MAXIMA_FRAME_SEGUNDOS:
                status = "sem_frames"
            return {"status": status, "erro": self._erro,
                    "consumidores": list(self._consumidores.values()),
                    "idade_frame_segundos": idade, "frames_recebidos": self._sequencia}

    def fechar(self):
        with self._trava_ciclo:
            self._sinal_parada.set()
            with self._condicao:
                self._condicao.notify_all()
            if self._tarefa:
                self._tarefa.join(timeout=5)
            if self._tarefa and self._tarefa.is_alive():
                raise RuntimeError("Leitor da camera nao encerrou no prazo")
            self._consumidores.clear()
            self._registrar_status("parado")

    # Compatibilidade com consumidores anteriores.
    start = iniciar
    acquire = adquirir
    release = liberar
    _report = _registrar_status
    _run = _ler_imagens
    wait_frame = aguardar_frame
    frames = gerar_frames
    close = fechar



camera = CameraCompartilhada(settings.ESP32_STREAM_URL)


# Compatibilidade de importação com os nomes anteriores.
SharedCamera = CameraCompartilhada

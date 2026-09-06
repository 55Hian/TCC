"""Uma conexao por processo, com ultimo frame compartilhado entre consumidores."""
import threading
import time

from core.config import settings
from services.camera_service import gerador_de_frames


class SharedCamera:
    def __init__(self, url, source=gerador_de_frames):
        self.url = url
        self.source = source
        self._lifecycle = threading.RLock()
        self._consumers = {}
        self._condition = threading.Condition()
        self._stop = threading.Event()
        self._thread = None
        self._frame = None
        self._sequence = 0
        self._received = None
        self._status = "parado"
        self._error = None

    def start(self):
        with self._condition:
            if self._thread and self._thread.is_alive():
                return
            self._stop.clear()
            self._frame = None
            self._received = None
            self._status = "conectando"
            self._thread = threading.Thread(target=self._run, name="camera-reader", daemon=True)
            self._thread.start()

    def acquire(self, name):
        with self._lifecycle:
            token = object()
            self.start()
            self._consumers[token] = name
            return token

    def release(self, token):
        with self._lifecycle:
            self._consumers.pop(token, None)
            if not self._consumers:
                self.close()

    def _report(self, status, error=None):
        with self._condition:
            self._status, self._error = status, error
            self._frame = None
            self._condition.notify_all()

    def _run(self):
        try:
            for frame in self.source(self.url, self._stop, self._report):
                if self._stop.is_set():
                    break
                with self._condition:
                    self._frame = frame.copy()
                    self._sequence += 1
                    self._received = time.monotonic()
                    self._status, self._error = "recebendo", None
                    self._condition.notify_all()
        except Exception as exc:
            self._report("erro", str(exc))
        finally:
            if self._stop.is_set():
                self._report("parado")

    def wait_frame(self, sequence=0, timeout=0.5):
        """Retorna copia independente; nunca entrega frame com mais de 3 segundos."""
        with self._condition:
            self._condition.wait_for(
                lambda: self._stop.is_set() or (self._frame is not None and self._sequence > sequence
                    and time.monotonic() - self._received <= 3),
                timeout=timeout,
            )
            if (self._stop.is_set() or self._frame is None or self._sequence <= sequence
                    or time.monotonic() - self._received > 3):
                return None
            return self._sequence, self._frame.copy()

    def frames(self, stop_event=None, timeout=15):
        token = self.acquire("captura")
        try:
            sequence = 0
            last = time.monotonic()
            while not self._stop.is_set() and not (stop_event and stop_event.is_set()):
                item = self.wait_frame(sequence)
                if item is None:
                    if time.monotonic() - last >= timeout:
                        raise TimeoutError("Camera sem novos frames")
                    continue
                sequence, frame = item
                last = time.monotonic()
                yield frame
        finally:
            self.release(token)

    def status(self):
        with self._lifecycle, self._condition:
            age = None if self._received is None else time.monotonic() - self._received
            status = self._status
            if status == "recebendo" and age is not None and age > 3:
                status = "sem_frames"
            return {"status": status, "erro": self._error,
                    "consumidores": list(self._consumers.values()),
                    "idade_frame_segundos": age, "frames_recebidos": self._sequence}

    def close(self):
        with self._lifecycle:
            self._stop.set()
            with self._condition:
                self._condition.notify_all()
            if self._thread:
                self._thread.join(timeout=5)
            if self._thread and self._thread.is_alive():
                raise RuntimeError("Leitor da camera nao encerrou no prazo")
            self._consumers.clear()
            self._report("parado")



camera = SharedCamera(settings.ESP32_STREAM_URL)

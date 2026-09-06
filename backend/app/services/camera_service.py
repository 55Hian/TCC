import threading
import urllib.request

import cv2
import numpy as np


def gerador_de_frames(url_stream, stop_event=None, on_status=None):
    """Leitor exclusivo de rede; fecha a resposta em falha ou cancelamento."""
    stop = stop_event if stop_event is not None else threading.Event()
    report = on_status or (lambda status, erro=None: None)
    while not stop.is_set():
        try:
            report("conectando")
            print(f"[CAMERA] Conectando em {url_stream}...")
            with urllib.request.urlopen(url_stream, timeout=3) as stream:
                buffer = b""
                while not stop.is_set():
                    bloco = stream.read1(4096)
                    if not bloco:
                        raise ConnectionError("stream encerrado")
                    buffer += bloco
                    if len(buffer) > 4 * 1024 * 1024:
                        raise ValueError("JPEG excedeu limite de buffer")
                    while True:
                        inicio = buffer.find(b"\xff\xd8")
                        if inicio < 0:
                            buffer = buffer[-1:]
                            break
                        buffer = buffer[inicio:]
                        fim = buffer.find(b"\xff\xd9", 2)
                        if fim < 0:
                            break
                        jpg, buffer = buffer[:fim + 2], buffer[fim + 2:]
                        frame = cv2.imdecode(np.frombuffer(jpg, dtype=np.uint8), cv2.IMREAD_COLOR)
                        if frame is not None:
                            yield frame
        except Exception as exc:
            report("reconectando", str(exc))
            print(f"[CAMERA] Falha: {exc}. Reconectando em 2 segundos...")
            stop.wait(2)

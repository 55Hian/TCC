import time
import urllib.request

import cv2
import numpy as np


def gerador_de_frames(url_stream):
    """Conecta ao ESP32-CAM e entrega frames continuamente como generator."""
    while True:
        try:
            print(f"[CAMERA] Conectando em {url_stream}...")
            stream = urllib.request.urlopen(url_stream, timeout=10)
            bytes_stream = b""
            print("[CAMERA] Conectado! Enviando frames...")

            while True:
                bloco = stream.read(4096)
                if not bloco:
                    raise ConnectionError("stream encerrado")
                bytes_stream += bloco
                inicio = bytes_stream.find(b"\xff\xd8")
                fim = bytes_stream.find(b"\xff\xd9")

                if inicio != -1 and fim != -1:
                    if inicio < fim:
                        jpg = bytes_stream[inicio:fim + 2]
                        bytes_stream = bytes_stream[fim + 2:]
                        frame = cv2.imdecode(
                            np.frombuffer(jpg, dtype=np.uint8), cv2.IMREAD_COLOR
                        )
                        if frame is not None:
                            yield frame
                    else:
                        bytes_stream = bytes_stream[inicio:]
        except Exception as exc:
            print(f"[CAMERA] Falha de rede: {exc}. Reconectando em 2 segundos...")
            time.sleep(2)

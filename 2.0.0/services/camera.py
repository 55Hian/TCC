"""Leitura e reconexao do stream MJPEG da camera."""
import threading
import time
import urllib.request

import cv2
import numpy as np


def frames(url, stop=None):
    stop = stop or threading.Event()
    while not stop.is_set():
        try:
            with urllib.request.urlopen(url, timeout=4) as response:
                yield from _decode(response, stop)
        except Exception as error:
            print(f"[camera] {error}; tentando novamente")
            stop.wait(2)


def _decode(response, stop):
    buffer = b""
    while not stop.is_set():
        chunk = response.read1(4096)
        if not chunk:
            raise ConnectionError("Stream da camera encerrou")
        buffer += chunk
        start = buffer.find(b"\xff\xd8")
        end = buffer.find(b"\xff\xd9", start + 2) if start >= 0 else -1
        if start < 0:
            buffer = buffer[-1:]
        elif end >= 0:
            image = cv2.imdecode(np.frombuffer(buffer[start:end + 2], np.uint8), cv2.IMREAD_COLOR)
            buffer = buffer[end + 2:]
            if image is not None:
                yield image
        elif len(buffer) > 4 * 1024 * 1024:
            raise ValueError("Quadro JPEG maior que 4 MB")


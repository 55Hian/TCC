"""Captura imagens unicas para anotacao manual."""
import time
import uuid
from pathlib import Path

import cv2

from config import CAMERA_URL, RAW_FRAMES
from services.camera import frames


def capturar(intervalo=2.0, quantidade=20):
    RAW_FRAMES.mkdir(parents=True, exist_ok=True)
    total = 0
    proximo = 0.0
    for image in frames(CAMERA_URL):
        agora = time.monotonic()
        if agora < proximo:
            continue
        nome = f"frame_{int(time.time())}_{uuid.uuid4().hex[:8]}.jpg"
        if not cv2.imwrite(str(RAW_FRAMES / nome), image):
            raise OSError(f"Nao foi possivel salvar {nome}")
        total += 1
        proximo = agora + intervalo
        if quantidade and total >= quantidade:
            break
    return total

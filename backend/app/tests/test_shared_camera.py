import asyncio
import sys
import threading
import time
from pathlib import Path
from unittest.mock import Mock

import cv2
import numpy as np
import pandas as pd
from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from services.shared_camera import SharedCamera
from services import camera_service
from routers import stream, dataset
from main import app
import worker
from core.state import state


def test_broadcast_uma_conexao_copias_e_consumidor_lento():
    calls = []
    def source(url, stop, report):
        calls.append(url)
        while not stop.wait(0.01):
            yield np.zeros((8, 8, 3), dtype=np.uint8)
    camera = SharedCamera("fake", source)
    try:
        threads = [threading.Thread(target=camera.start) for _ in range(10)]
        for thread in threads: thread.start()
        for thread in threads: thread.join()
        a = camera.wait_frame(timeout=1)
        b = camera.wait_frame(timeout=1)
        assert a is not None and b is not None
        a[1][:] = 255
        assert not b[1].any()
        time.sleep(0.06)
        assert camera.wait_frame(a[0])[0] > a[0]
        assert calls == ["fake"]
    finally:
        camera.close()
    assert camera.status()["status"] == "parado"


def test_reconecta_fecha_respostas_e_decodifica_varios_jpegs(monkeypatch):
    stop = threading.Event()
    jpg = cv2.imencode(".jpg", np.zeros((8, 8, 3), dtype=np.uint8))[1].tobytes()
    responses = []
    class Response:
        closed = False
        def __enter__(self): return self
        def __exit__(self, *args): self.closed = True
        def read1(self, size):
            if len(responses) == 1: raise TimeoutError("queda simulada")
            return b"cabecalho" + jpg + jpg
    def open_stream(*args, **kwargs):
        response = Response()
        responses.append(response)
        return response
    monkeypatch.setattr(camera_service.urllib.request, "urlopen", open_stream)
    frames = camera_service.gerador_de_frames("fake", stop)
    try:
        assert next(frames).shape == (8, 8, 3)
        assert next(frames).shape == (8, 8, 3)
    finally:
        frames.close()
    assert len(responses) == 2
    assert all(response.closed for response in responses)


def test_stream_worker_captura_e_evento_ws_mesma_fonte(monkeypatch, tmp_path):
    calls = []
    def source(url, stop, report):
        calls.append(url)
        while not stop.wait(0.02):
            yield np.zeros((8, 8, 3), dtype=np.uint8)
    camera = SharedCamera("fake", source)
    for module in [worker, stream, dataset]: monkeypatch.setattr(module, "camera", camera)
    monkeypatch.setattr(dataset.settings, "RAW_FRAMES_DIR", str(tmp_path))
    vision = Mock()
    vision.processar_frame.return_value = pd.DataFrame([
        dict(classe="mao", x_min=0, y_min=0, x_max=10, y_max=10),
        dict(classe="cha", x_min=0, y_min=0, x_max=10, y_max=10)])
    monkeypatch.setattr(worker, "VisionService", lambda: vision)
    async def browsers():
        request = Mock()
        async def connected(): return False
        request.is_disconnected = connected
        streams = [stream._frames_mjpeg(request), stream._frames_mjpeg(request)]
        try:
            parts = await asyncio.wait_for(asyncio.gather(*(anext(s) for s in streams)), 3)
            assert all(b"Content-Type: image/jpeg" in part for part in parts)
        finally:
            for s in streams: await s.aclose()
    try:
        with TestClient(app) as client:
            with client.websocket_connect("/ws/eventos") as ws:
                assert worker.iniciar()
                asyncio.run(browsers())
                dataset._executar_captura(0, 5)
                assert len(list(tmp_path.glob("*.jpg"))) == 5
                assert dataset.state.captura_status == "concluido"
                assert ws.receive_json()["tipo"] == "interacao_mao"
                assert vision.processar_frame.called
                assert calls == ["fake"]
    finally:
        worker.encerrar()
        camera.close()
        state.monitor_status = "parado"
        state.captura_status = "ocioso"


def test_parar_worker_sem_frames(monkeypatch):
    def source(url, stop, report):
        stop.wait()
        yield np.zeros((1, 1, 3), dtype=np.uint8)
    camera = SharedCamera("fake", source)
    monkeypatch.setattr(worker, "camera", camera)
    monkeypatch.setattr(worker, "VisionService", Mock())
    try:
        worker.iniciar()
        time.sleep(0.1)
        started = time.monotonic()
        worker.encerrar()
        assert time.monotonic() - started < 1.5
        assert not worker.esta_rodando()
    finally:
        camera.close()


def test_ultimo_consumidor_fecha_e_permite_reiniciar():
    starts, closed = [], []
    def source(url, stop, report):
        starts.append(1)
        try:
            while not stop.wait(0.01):
                yield np.zeros((8, 8, 3), dtype=np.uint8)
        finally:
            closed.append(1)
    camera = SharedCamera("fake", source)
    for _ in range(3):
        monitor = camera.acquire("monitoramento")
        capture = camera.acquire("captura")
        assert camera.wait_frame(timeout=1)
        camera.release(monitor)
        assert camera.status()["consumidores"] == ["captura"]
        assert camera._thread.is_alive()
        camera.release(capture)
        assert camera.status()["consumidores"] == []
        assert camera.status()["status"] == "parado"
        assert not camera._thread.is_alive()
    assert len(starts) == len(closed) == 3


def test_captura_libera_camera_ao_atingir_limite(tmp_path):
    from capturar_frames import capturar_frames
    def source(url, stop, report):
        while not stop.wait(0.01):
            yield np.zeros((8, 8, 3), dtype=np.uint8)
    camera = SharedCamera("fake", source)
    assert capturar_frames(str(tmp_path), intervalo=0, max_frames=5,
        mostrar_janela=False, fonte_frames=camera.frames()) == 5
    assert camera.status()["status"] == "parado"
    assert not camera._thread.is_alive()


def test_galeria_unicode_e_jpeg_completo(monkeypatch, tmp_path):
    from urllib.parse import quote
    from capturar_frames import capturar_frames
    monkeypatch.setattr(dataset.settings, "RAW_FRAMES_DIR", str(tmp_path))
    frame = np.zeros((8, 8, 3), dtype=np.uint8)
    capturar_frames(str(tmp_path), intervalo=0, max_frames=1,
        mostrar_janela=False, fonte_frames=iter([frame]))
    saved = next(tmp_path.glob("*.jpg"))
    special = tmp_path / "captura a\u00e7\u00e3o #1 & teste.jpg"
    saved.rename(special)
    (tmp_path / "incompleta.jpg.part").write_bytes(b"incompleta")
    with TestClient(app) as client:
        images = client.get("/api/dataset/imagens").json()["imagens"]
        assert len(images) == 1 and images[0]["versao"]
        response = client.get("/api/dataset/imagens/" + quote(special.name, safe=""))
        assert response.status_code == 200
        assert response.headers["content-type"].startswith("image/jpeg")
        assert cv2.imdecode(np.frombuffer(response.content, np.uint8), cv2.IMREAD_COLOR) is not None


def test_stream_desconectado_libera_consumidor(monkeypatch):
    def source(url, stop, report):
        while not stop.wait(0.01):
            yield np.zeros((8, 8, 3), dtype=np.uint8)
    camera = SharedCamera("fake", source)
    monkeypatch.setattr(stream, "camera", camera)
    class Request:
        async def is_disconnected(self): return False
    async def check():
        generator = stream._frames_mjpeg(Request())
        await anext(generator)
        assert camera.status()["consumidores"] == ["mjpeg"]
        await generator.aclose()
    asyncio.run(check())
    assert camera.status()["status"] == "parado"
    assert not camera._thread.is_alive()

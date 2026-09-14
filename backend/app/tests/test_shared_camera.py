import pytest
import asyncio
import threading
import time
from unittest.mock import Mock

import cv2
import numpy as np
import pandas as pd
from fastapi.testclient import TestClient

from services.shared_camera import CameraCompartilhada
from services import camera_service
from routers import stream, dataset
from main import app
import worker
from core.state import state


def test_broadcast_uma_conexao_copias_e_consumidor_lento():
    chamadas = []
    def fonte_simulada(url, sinal_parada, report):
        chamadas.append(url)
        while not sinal_parada.wait(0.01):
            yield np.zeros((8, 8, 3), dtype=np.uint8)
    camera = CameraCompartilhada("fake", fonte_simulada)
    try:
        tarefas = [threading.Thread(target=camera.iniciar) for _ in range(10)]
        for tarefa in tarefas: tarefa.start()
        for tarefa in tarefas: tarefa.join()
        a = camera.aguardar_frame(timeout=1)
        b = camera.aguardar_frame(timeout=1)
        assert a is not None and b is not None
        a[1][:] = 255
        assert not b[1].any()
        time.sleep(0.06)
        assert camera.aguardar_frame(a[0])[0] > a[0]
        assert chamadas == ["fake"]
    finally:
        camera.fechar()
    assert camera.status()["status"] == "parado"


def test_reconecta_fecha_respostas_e_decodifica_varios_jpegs(monkeypatch):
    sinal_parada = threading.Event()
    jpg = cv2.imencode(".jpg", np.zeros((8, 8, 3), dtype=np.uint8))[1].tobytes()
    respostas = []
    class RespostaSimulada:
        closed = False
        def __enter__(self): return self
        def __exit__(self, *args): self.closed = True
        def read1(self, size):
            if len(respostas) == 1: raise TimeoutError("queda simulada")
            return b"cabecalho" + jpg + jpg
    def abrir_fluxo(*args, **kwargs):
        resposta = RespostaSimulada()
        respostas.append(resposta)
        return resposta
    monkeypatch.setattr(camera_service.urllib.request, "urlopen", abrir_fluxo)
    quadros = camera_service.gerador_de_frames("fake", sinal_parada)
    try:
        assert next(quadros).shape == (8, 8, 3)
        assert next(quadros).shape == (8, 8, 3)
    finally:
        quadros.close()
    assert len(respostas) == 2
    assert all(resposta.closed for resposta in respostas)


def test_stream_worker_captura_e_evento_ws_mesma_fonte(monkeypatch, tmp_path):
    chamadas = []
    def fonte_simulada(url, sinal_parada, report):
        chamadas.append(url)
        while not sinal_parada.wait(0.02):
            yield np.zeros((8, 8, 3), dtype=np.uint8)
    camera = CameraCompartilhada("fake", fonte_simulada)
    for module in [worker, stream, dataset]: monkeypatch.setattr(module, "camera", camera)
    monkeypatch.setattr(dataset.settings, "RAW_FRAMES_DIR", str(tmp_path))
    visao = Mock()
    visao.processar_frame.return_value = pd.DataFrame([
        dict(classe="mao", x_min=0, y_min=0, x_max=10, y_max=10),
        dict(classe="cha", x_min=0, y_min=0, x_max=10, y_max=10)])
    monkeypatch.setattr(worker, 'ServicoVisao', lambda: visao)
    async def simular_navegadores():
        request = Mock()
        async def conectado(): return False
        request.is_disconnected = conectado
        streams = [stream._frames_mjpeg(request), stream._frames_mjpeg(request)]
        try:
            parts = await asyncio.wait_for(asyncio.gather(*(anext(s) for s in streams)), 3)
            assert all(b"Content-Type: image/jpeg" in part for part in parts)
        finally:
            for s in streams: await s.aclose()
    try:
        with TestClient(app) as cliente:
            with cliente.websocket_connect("/ws/eventos") as ws:
                assert worker.iniciar()
                asyncio.run(simular_navegadores())
                dataset._executar_captura(0, 5)
                assert len(list(tmp_path.glob("*.jpg"))) == 5
                assert dataset.state.captura_status == "concluido"
                assert ws.receive_json()["tipo"] == "interacao_mao"
                assert visao.processar_frame.called
                assert chamadas == ["fake"]
    finally:
        worker.encerrar()
        camera.fechar()
        state.monitor_status = "parado"
        state.captura_status = "ocioso"


def test_parar_worker_sem_frames(monkeypatch):
    def fonte_simulada(url, sinal_parada, report):
        sinal_parada.wait()
        yield np.zeros((1, 1, 3), dtype=np.uint8)
    camera = CameraCompartilhada("fake", fonte_simulada)
    monkeypatch.setattr(worker, "camera", camera)
    monkeypatch.setattr(worker, 'ServicoVisao', Mock())
    try:
        worker.iniciar()
        time.sleep(0.1)
        inicio = time.monotonic()
        worker.encerrar()
        assert time.monotonic() - inicio < 1.5
        assert not worker.esta_rodando()
    finally:
        camera.fechar()


def test_ultimo_consumidor_fecha_e_permite_reiniciar():
    starts, closed = [], []
    def fonte_simulada(url, sinal_parada, report):
        starts.append(1)
        try:
            while not sinal_parada.wait(0.01):
                yield np.zeros((8, 8, 3), dtype=np.uint8)
        finally:
            closed.append(1)
    camera = CameraCompartilhada("fake", fonte_simulada)
    for _ in range(3):
        monitor = camera.adquirir("monitoramento")
        captura = camera.adquirir("captura")
        assert camera.aguardar_frame(timeout=1)
        camera.liberar(monitor)
        assert camera.status()["consumidores"] == ["captura"]
        assert camera._tarefa.is_alive()
        camera.liberar(captura)
        assert camera.status()["consumidores"] == []
        assert camera.status()["status"] == "parado"
        assert not camera._tarefa.is_alive()
    assert len(starts) == len(closed) == 3


def test_captura_libera_camera_ao_atingir_limite(tmp_path):
    from capturar_frames import capturar_frames
    def fonte_simulada(url, sinal_parada, report):
        while not sinal_parada.wait(0.01):
            yield np.zeros((8, 8, 3), dtype=np.uint8)
    camera = CameraCompartilhada("fake", fonte_simulada)
    assert capturar_frames(str(tmp_path), intervalo=0, max_frames=5,
        mostrar_janela=False, fonte_frames=camera.gerar_frames()) == 5
    assert camera.status()["status"] == "parado"
    assert not camera._tarefa.is_alive()


def test_galeria_unicode_e_jpeg_completo(monkeypatch, tmp_path):
    from urllib.parse import quote
    from capturar_frames import capturar_frames
    monkeypatch.setattr(dataset.settings, "RAW_FRAMES_DIR", str(tmp_path))
    imagem = np.zeros((8, 8, 3), dtype=np.uint8)
    capturar_frames(str(tmp_path), intervalo=0, max_frames=1,
        mostrar_janela=False, fonte_frames=iter([imagem]))
    salvo = next(tmp_path.glob("*.jpg"))
    especial = tmp_path / "captura a\u00e7\u00e3o #1 & teste.jpg"
    salvo.rename(especial)
    (tmp_path / "incompleta.jpg.part").write_bytes(b"incompleta")
    with TestClient(app) as cliente:
        images = cliente.get("/api/dataset/imagens").json()["imagens"]
        assert len(images) == 1 and images[0]["versao"]
        resposta = cliente.get("/api/dataset/imagens/" + quote(especial.name, safe=""))
        assert resposta.status_code == 200
        assert resposta.headers["content-type"].startswith("image/jpeg")
        assert cv2.imdecode(np.frombuffer(resposta.content, np.uint8), cv2.IMREAD_COLOR) is not None


def test_stream_desconectado_libera_consumidor(monkeypatch):
    def fonte_simulada(url, sinal_parada, report):
        while not sinal_parada.wait(0.01):
            yield np.zeros((8, 8, 3), dtype=np.uint8)
    camera = CameraCompartilhada("fake", fonte_simulada)
    monkeypatch.setattr(stream, "camera", camera)
    class RequisicaoSimulada:
        async def is_disconnected(self): return False
    async def verificar():
        gerador = stream._frames_mjpeg(RequisicaoSimulada())
        await anext(gerador)
        assert camera.status()["consumidores"] == ["mjpeg"]
        await gerador.aclose()
    asyncio.run(verificar())
    assert camera.status()["status"] == "parado"
    assert not camera._tarefa.is_alive()


pytestmark = pytest.mark.integracao

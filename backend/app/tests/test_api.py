import os
import sys

import pytest
from fastapi.testclient import TestClient

PROJ_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJ_DIR not in sys.path:
    sys.path.insert(0, PROJ_DIR)

from main import app


@pytest.fixture(scope="module")
def client():
    # "with" garante que o lifespan (startup) rode e registre o event loop em
    # core.state, necessario para o broadcast do WebSocket funcionar nos testes.
    with TestClient(app) as c:
        yield c


def test_health(client):
    resposta = client.get("/api/health")
    assert resposta.status_code == 200
    assert resposta.json() == {"status": "ok"}


def test_listar_eventos_vazio_ou_com_itens(client):
    resposta = client.get("/api/eventos")
    assert resposta.status_code == 200
    assert "eventos" in resposta.json()


def test_criar_evento_aparece_na_listagem(client):
    resposta = client.post(
        "/api/eventos", json={"tipo": "interacao_mao", "produto": "gelatina", "quantidade": 1}
    )
    assert resposta.status_code == 201
    corpo = resposta.json()
    assert corpo["tipo"] == "interacao_mao"
    assert "timestamp" in corpo

    eventos = client.get("/api/eventos").json()["eventos"]
    assert any(e["produto"] == "gelatina" for e in eventos)


def test_websocket_eventos_recebe_broadcast(client):
    with client.websocket_connect("/ws/eventos") as ws:
        resposta = client.post(
            "/api/eventos", json={"tipo": "inserido", "produto": "cha", "quantidade": 2}
        )
        assert resposta.status_code == 201
        mensagem = ws.receive_json()
        assert mensagem["produto"] == "cha"


def test_listar_modelos_inclui_os_4_pretreinados(client):
    resposta = client.get("/api/modelos")
    assert resposta.status_code == 200
    nomes = {m["nome"] for m in resposta.json()["pretreinados"]}
    assert nomes == {"yolov8n.pt", "yolo12n.pt", "yolo26s.pt", "yolo26m.pt"}


def test_status_treino_inicial_ocioso(client):
    resposta = client.get("/api/treino/status")
    assert resposta.status_code == 200
    assert resposta.json()["status"] == "ocioso"


def test_listar_experimentos_retorna_lista(client):
    resposta = client.get("/api/treino/experimentos")
    assert resposta.status_code == 200
    assert isinstance(resposta.json()["experimentos"], list)
    assert len(resposta.json()["experimentos"]) > 0


def test_treino_start_com_modelo_inexistente_retorna_400(client):
    resposta = client.post("/api/treino/start", json={"base_model": "nao_existe.pt"})
    assert resposta.status_code == 400


def test_listar_imagens_dataset(client):
    resposta = client.get("/api/dataset/imagens")
    assert resposta.status_code == 200
    imagens = resposta.json()["imagens"]
    assert len(imagens) > 0
    assert {"nome", "anotado"} <= imagens[0].keys()


def test_obter_imagem_inexistente_404(client):
    resposta = client.get("/api/dataset/imagens/nao_existe.jpg")
    assert resposta.status_code == 404


def test_status_monitoramento_inicial(client):
    resposta = client.get("/api/monitoramento/status")
    assert resposta.status_code == 200
    assert resposta.json()["status"] == "parado"

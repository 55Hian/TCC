
import pytest
from fastapi.testclient import TestClient


from main import app


@pytest.fixture(scope="module")
def cliente():
    # "with" garante que o lifespan (startup) rode e registre o event loop em
    # core.state, necessario para o broadcast do WebSocket funcionar nos testes.
    with TestClient(app) as c:
        yield c


def test_saude(cliente):
    resposta = cliente.get("/api/health")
    assert resposta.status_code == 200
    assert resposta.json() == {"status": "ok"}


def test_listar_eventos_vazio_ou_com_itens(cliente):
    resposta = cliente.get("/api/eventos")
    assert resposta.status_code == 200
    assert "eventos" in resposta.json()


def test_criar_evento_aparece_na_listagem(cliente):
    resposta = cliente.post(
        "/api/eventos", json={"tipo": "interacao_mao", "produto": "gelatina", "quantidade": 1}
    )
    assert resposta.status_code == 201
    corpo = resposta.json()
    assert corpo["tipo"] == "interacao_mao"
    assert "timestamp" in corpo

    eventos = cliente.get("/api/eventos").json()["eventos"]
    assert any(e["produto"] == "gelatina" for e in eventos)


def test_websocket_eventos_recebe_broadcast(cliente):
    with cliente.websocket_connect("/ws/eventos") as ws:
        resposta = cliente.post(
            "/api/eventos", json={"tipo": "inserido", "produto": "cha", "quantidade": 2}
        )
        assert resposta.status_code == 201
        mensagem = ws.receive_json()
        assert mensagem["produto"] == "cha"


def test_listar_modelos_inclui_os_4_pretreinados(cliente):
    resposta = cliente.get("/api/modelos")
    assert resposta.status_code == 200
    nomes = {m["nome"] for m in resposta.json()["pretreinados"]}
    assert nomes == {"yolov8n.pt", "yolo12n.pt", "yolo26s.pt", "yolo26m.pt"}


def test_status_treino_inicial_ocioso(cliente):
    resposta = cliente.get("/api/treino/status")
    assert resposta.status_code == 200
    assert resposta.json()["status"] == "ocioso"


def test_listar_experimentos_retorna_lista(cliente):
    resposta = cliente.get("/api/treino/experimentos")
    assert resposta.status_code == 200
    assert isinstance(resposta.json()["experimentos"], list)
    assert len(resposta.json()["experimentos"]) > 0


def test_treino_start_com_modelo_inexistente_retorna_400(cliente):
    resposta = cliente.post("/api/treino/start", json={"base_model": "nao_existe.pt"})
    assert resposta.status_code == 400


def test_listar_imagens_dataset(cliente):
    resposta = cliente.get("/api/dataset/imagens")
    assert resposta.status_code == 200
    imagens = resposta.json()["imagens"]
    assert len(imagens) > 0
    assert {"nome", "anotado"} <= imagens[0].keys()


def test_obter_imagem_inexistente_404(cliente):
    resposta = cliente.get("/api/dataset/imagens/nao_existe.jpg")
    assert resposta.status_code == 404


def test_status_monitoramento_inicial(cliente):
    resposta = cliente.get("/api/monitoramento/status")
    assert resposta.status_code == 200
    assert resposta.json()["status"] == "parado"


pytestmark = pytest.mark.integracao

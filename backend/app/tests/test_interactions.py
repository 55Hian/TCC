
import pandas as pd
import pytest

from core.config import settings
from services.event_service import ServicoEventos, contact, gerar_eventos
from services.tracking_service import RastreadorObjetos


def caixa_teste(classe, x=0, y=0, tamanho=20, **extra):
    return dict(classe=classe, x_min=x, y_min=y, x_max=x+tamanho, y_max=y+tamanho, **extra)


def quadro_teste(*produtos, maos=1):
    return pd.DataFrame([caixa_teste("mao") for _ in range(maos)] + list(produtos))


@pytest.fixture(autouse=True)
def limiares(monkeypatch):
    for nome, valor in dict(
        INTERACTION_CONFIRM_SECONDS=0.3, INTERACTION_MIN_SAMPLES=3,
        INTERACTION_MAX_GAP_SECONDS=0.5, INTERACTION_RELEASE_SECONDS=0.6,
        INTERACTION_RESET_SECONDS=2.0, IOU_THRESHOLD=0.1, HAND_CONTACT_MARGIN=0.08,
    ).items():
        monkeypatch.setattr(settings, nome, valor)


def confirmar(servico, deteccoes, inicio=0):
    assert servico.processar(deteccoes, inicio) == []
    assert servico.processar(deteccoes, inicio + 0.15) == []
    return servico.processar(deteccoes, inicio + 0.3)


def test_tres_produtos_sem_eventos_repetidos():
    servico = ServicoEventos()
    deteccoes = quadro_teste(caixa_teste("cha"), caixa_teste("gelatina"), caixa_teste("creme_leite"))
    eventos = confirmar(servico, deteccoes)
    assert {e["produto"] for e in eventos} == {"cha", "gelatina", "creme_leite"}
    assert len({e["produto_id"] for e in eventos}) == 3
    assert servico.processar(deteccoes, 0.45) == []
    assert servico.processar(deteccoes, 0.6) == []
    assert len(gerar_eventos(deteccoes)) == 3


def test_passagem_por_um_produto_e_contato_com_outro():
    servico = ServicoEventos()
    assert servico.processar(quadro_teste(caixa_teste("cha")), 0) == []
    assert servico.processar(quadro_teste(caixa_teste("cha")), 0.1) == []
    deteccoes = quadro_teste(caixa_teste("cha", x=100), caixa_teste("gelatina"))
    eventos = confirmar(servico, deteccoes, inicio=0.2)
    assert [e["produto"] for e in eventos] == ["gelatina"]


def test_liberacao_permite_nova_interacao():
    servico = ServicoEventos()
    deteccoes = quadro_teste(caixa_teste("cha"))
    assert len(confirmar(servico, deteccoes)) == 1
    assert servico.processar(pd.DataFrame(), 0.5) == []
    assert servico.processar(deteccoes, 0.65) == []  # breve oclusao
    assert servico.processar(pd.DataFrame(), 1.3) == []
    assert len(confirmar(servico, deteccoes, 1.4)) == 1


def test_observacoes_ausentes_nao_contam_como_contato():
    servico = ServicoEventos()
    deteccoes = quadro_teste(caixa_teste("cha"))
    assert servico.processar(deteccoes, 0) == []
    assert servico.processar(pd.DataFrame(), 0.1) == []
    assert servico.processar(deteccoes, 0.3) == []
    assert servico.processar(deteccoes, 0.45) == []
    assert len(servico.processar(deteccoes, 0.6)) == 1


def test_imagens_lentas_e_lacuna_nao_confirmam():
    servico = ServicoEventos()
    deteccoes = quadro_teste(caixa_teste("cha"))
    for timestamp in (0, 0.55, 1.1, 1.65):
        assert servico.processar(deteccoes, timestamp) == []
    assert servico.processar(deteccoes, 5) == []
    assert servico.processar(deteccoes, 5.1) == []
    assert len(servico.processar(deteccoes, 5.3)) == 1
    servico.reset()
    assert servico.processar(deteccoes, 6) == []


def test_objetos_reordenados_mantem_ids_distintos():
    tracker = RastreadorObjetos()
    primeiro = tracker.update([caixa_teste("cha", x=0), caixa_teste("cha", x=100)], 0)
    segundo = tracker.update([caixa_teste("cha", x=101), caixa_teste("cha", x=1)], 0.1)
    assert primeiro[0]["track_id"] == segundo[1]["track_id"]
    assert primeiro[1]["track_id"] == segundo[0]["track_id"]


def test_duas_maos_formam_pares_independentes():
    servico = ServicoEventos()
    eventos = confirmar(servico, quadro_teste(caixa_teste("cha"), maos=2))
    assert len(eventos) == 2
    assert len({e["mao_id"] for e in eventos}) == 2
    assert len({e["produto_id"] for e in eventos}) == 1


def test_pontos_rejeitam_regiao_vazia_da_caixa_da_mao():
    # A caixa cruza o produto, mas os pontos/segmentos ficam acima e a esquerda.
    pontos = [(0, 0)] * 21
    pontos[9] = (0, 10)
    pontos[8] = (100, 0)
    mao = caixa_teste("mao", tamanho=100, landmarks=pontos)
    produto = caixa_teste("cha", x=70, y=70)
    assert contact(mao, produto) == (False, [], "landmarks")
    assert contact(caixa_teste("mao", tamanho=100), produto)[2] == "iou"


def test_contato_da_ponta_do_dedo_e_segmento():
    pontos = [(0, 0)] * 21
    pontos[9] = (0, 10)
    pontos[8] = (50, 0)
    mao = caixa_teste("mao", landmarks=pontos)
    em_contato, indices_pontos, metodo = contact(mao, caixa_teste("cha", x=45, y=-5, tamanho=10))
    assert em_contato and 8 in indices_pontos and metodo == "landmarks"
    em_contato, indices_pontos, _ = contact(mao, caixa_teste("cha", x=20, y=-2, tamanho=4))
    assert em_contato and indices_pontos == []  # segmento cruza sem nenhum no dentro


def test_area_zero_e_ausencia_de_sobreposicao():
    assert not contact(caixa_teste("mao", tamanho=0), caixa_teste("cha", tamanho=0))[0]
    assert not contact(caixa_teste("mao"), caixa_teste("cha", x=100))[0]


def test_relogio_regressivo_inicia_novo_candidato():
    servico = ServicoEventos()
    deteccoes = quadro_teste(caixa_teste("cha"))
    assert len(confirmar(servico, deteccoes, 10)) == 1
    assert servico.processar(deteccoes, 1) == []


def test_api_preserva_metadados_da_mao():
    from fastapi.testclient import TestClient
    from main import app
    dados_evento = dict(tipo="interacao_mao", produto="cha", quantidade=1,
                   mao_id=1, produto_id=2, pontos_mao=[8], metodo="landmarks",
                   interpretacao="contato_provavel")
    with TestClient(app) as cliente:
        resultado = cliente.post("/api/eventos", json=dados_evento)
        assert resultado.status_code == 201
        assert all(resultado.json()[chave] == valor for chave, valor in dados_evento.items())

def test_movimento_conjunto_indica_manipulacao_sem_duplicar_evento():
    servico = ServicoEventos()
    eventos = []
    for indice in range(3):
        deteccoes = pd.DataFrame([caixa_teste("mao", x=indice*3), caixa_teste("cha", x=indice*3)])
        eventos.extend(servico.processar(deteccoes, indice*0.15))
    assert len(eventos) == 1
    assert eventos[0]["interpretacao"] == "manipulacao_provavel"
    assert servico.processar(pd.DataFrame([caixa_teste("mao", x=9), caixa_teste("cha", x=9)]), 0.45) == []


def test_movimento_isolado_da_mao_nao_indica_manipulacao():
    servico = ServicoEventos()
    for indice in range(3):
        eventos = servico.processar(pd.DataFrame([caixa_teste("mao", x=indice*3), caixa_teste("cha")]), indice*0.15)
    assert eventos[0]["interpretacao"] == "contato_provavel"


def test_visao_usa_mesmo_instante_e_substitui_mao_yolo(monkeypatch):
    import numpy as np
    from services import vision_service as module

    class CaixaSimulada:
        xyxy = np.array([[0, 0, 20, 20]])
        conf = np.array([0.9])
        def __init__(self, cls):
            self.cls = np.array([cls])

    class ModeloSimulado:
        names = dict(enumerate(settings.CLASSES))

        def __call__(self, *args, **kwargs):
            return [type("Result", (), {"boxes": [CaixaSimulada(2), CaixaSimulada(3)]})()]

    chamadas = []
    class MaosSimuladas:
        def processar_frame(self, quadro_teste, timestamp):
            chamadas.append(timestamp)
            return [caixa_teste("mao", landmarks=[(0, 0)]*21)]
        def close(self):
            chamadas.append("closed")

    monkeypatch.setattr(settings, "HAND_LANDMARKS_ENABLED", True)
    monkeypatch.setattr(settings, "USE_EXTERNAL_VALIDATION_DATASET", False)
    monkeypatch.setattr(module, "YOLO", lambda *args: ModeloSimulado())
    monkeypatch.setattr(module, 'ServicoMaos', MaosSimuladas)
    visao = module.ServicoVisao()
    resultado = visao.processar_frame(np.zeros((20,20,3), dtype=np.uint8), timestamp=1.25)
    assert resultado["classe"].tolist() == ["cha", "mao"]
    assert resultado.attrs["timestamp"] == 1.25
    assert chamadas == [1.25]
    visao.fechar()
    assert chamadas[-1] == "closed"

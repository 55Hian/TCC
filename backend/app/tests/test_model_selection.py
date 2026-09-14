from pathlib import Path
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from core.config import Configuracoes, settings, MODELOS
from services import model_service, training_service
from main import app


@pytest.mark.parametrize("name", MODELOS)
def test_selecao_resolve_ambos_os_caminhos(name):
    config = Configuracoes(_env_file=None, MODELO_ATIVO=name)
    assert Path(config.BASE_MODEL).name == name + ".pt"
    assert Path(config.MODEL_PATH).parts[-2:] == (name, "best.pt")
    assert config.TRAINING_NAME == name


def test_modelo_desconhecido_rejeitado():
    with pytest.raises(ValidationError):
        Configuracoes(_env_file=None, MODELO_ATIVO="../outro")


def test_ambiente_antigo_nao_sobrescreve_caminhos(monkeypatch):
    monkeypatch.setenv("TCC_BASE_MODEL", "wrong.pt")
    monkeypatch.setenv("TCC_MODEL_PATH", "wrong.pt")
    config = Configuracoes(_env_file=None, MODELO_ATIVO="yolo26m")
    assert Path(config.BASE_MODEL).name == "yolo26m.pt"
    assert Path(config.MODEL_PATH).parent.name == "yolo26m"


def test_catalogo_e_graficos_benchmark():
    with TestClient(app) as cliente:
        dados = cliente.get("/api/modelos").json()
        assert dados["modelo_ativo"] == settings.MODELO_ATIVO
        assert len(dados["treinados"]) == 4
        assert all(m["disponivel"] for m in dados["modelos"])
        assert [m["nome"] for m in dados["modelos"] if m["em_uso"]] == [settings.MODELO_ATIVO]
        experimentos = cliente.get("/api/treino/experimentos").json()["experimentos"]
        graphs = [e["grafico_url"] for e in experimentos if e["grafico_url"]]
        assert len(graphs) >= 4
        for graph in graphs:
            assert cliente.get(graph).status_code == 200


def test_treino_nao_pode_escolher_outro_modelo():
    different = next(nome for nome in MODELOS if nome != settings.MODELO_ATIVO)
    with TestClient(app) as cliente:
        resposta = cliente.post("/api/treino/start", json={"base_model": different + ".pt"})
        assert resposta.status_code == 400


def test_pesos_invalidos_preservam_arquivo_ativo(monkeypatch, tmp_path):
    monkeypatch.setattr(settings, "TRAINED_MODELS_DIR", str(tmp_path))
    _, destino = model_service.caminhos_modelo()
    destino.parent.mkdir()
    destino.write_bytes(b"previous")
    origem = tmp_path / "invalid.pt"
    origem.write_bytes(b"invalid")
    def reject(*args, **kwargs):
        raise ValueError("incompatible")
    monkeypatch.setattr(model_service, 'validar_pesos', reject)
    with pytest.raises(ValueError):
        model_service.publicar_pesos(origem, settings.MODELO_ATIVO)
    assert destino.read_bytes() == b"previous"


def test_publicacao_e_falha_na_copia(monkeypatch, tmp_path):
    monkeypatch.setattr(settings, "TRAINED_MODELS_DIR", str(tmp_path / "trained"))
    monkeypatch.setattr(model_service, 'validar_pesos', lambda *args: None)
    origem = tmp_path / "new.pt"
    origem.write_bytes(b"valid new weights")
    destino = Path(model_service.publicar_pesos(origem, settings.MODELO_ATIVO))
    assert destino.read_bytes() == origem.read_bytes()
    def fail(*args):
        raise OSError("copy failed")
    monkeypatch.setattr(model_service.shutil, "copyfile", fail)
    with pytest.raises(OSError):
        model_service.publicar_pesos(origem, settings.MODELO_ATIVO)
    assert destino.read_bytes() == b"valid new weights"
    assert list(destino.parent.iterdir()) == [destino]


def test_treino_publica_saida_real_apenas_apos_sucesso(monkeypatch, tmp_path):
    salvo = tmp_path / "actual_run"
    chamadas = []
    class Model:
        trainer = SimpleNamespace(save_dir=salvo)
        def train(self, **kwargs):
            chamadas.append(kwargs)
    monkeypatch.setattr(training_service, "YOLO", lambda path: Model())
    monkeypatch.setattr(training_service, '_resolver_dispositivo', lambda: ("cpu", "CPU"))
    monkeypatch.setattr(training_service, 'publicar_pesos',
                        lambda caminho, nome: chamadas.append((caminho, nome)) or "published.pt")
    resultado = training_service._treinar_dataset("data.yaml", settings.BASE_MODEL, 1, 640, 0.5)
    assert chamadas[0]["fraction"] == 0.5
    assert chamadas[0]["name"].startswith(settings.MODELO_ATIVO + "_")
    assert chamadas[-1] == (salvo / "weights" / "best.pt", settings.MODELO_ATIVO)
    assert resultado["pesos"] == "published.pt"

    def fail(**kwargs):
        raise RuntimeError("interrupted")
    monkeypatch.setattr(Model, "train", lambda self, **kwargs: fail(**kwargs))
    chamadas.clear()
    with pytest.raises(RuntimeError):
        training_service._treinar_dataset("data.yaml", settings.BASE_MODEL, 1, 640, 1)
    assert not chamadas

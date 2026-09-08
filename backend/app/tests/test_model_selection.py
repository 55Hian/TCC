import sys
from pathlib import Path
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from core.config import Settings, settings, MODELOS
from services import model_service, training_service
from main import app


@pytest.mark.parametrize("name", MODELOS)
def test_selection_resolves_both_paths(name):
    config = Settings(_env_file=None, MODELO_ATIVO=name)
    assert Path(config.BASE_MODEL).name == name + ".pt"
    assert Path(config.MODEL_PATH).parts[-2:] == (name, "best.pt")
    assert config.TRAINING_NAME == name


def test_unknown_model_rejected():
    with pytest.raises(ValidationError):
        Settings(_env_file=None, MODELO_ATIVO="../outro")


def test_legacy_environment_cannot_override_paths(monkeypatch):
    monkeypatch.setenv("TCC_BASE_MODEL", "wrong.pt")
    monkeypatch.setenv("TCC_MODEL_PATH", "wrong.pt")
    config = Settings(_env_file=None, MODELO_ATIVO="yolo26m")
    assert Path(config.BASE_MODEL).name == "yolo26m.pt"
    assert Path(config.MODEL_PATH).parent.name == "yolo26m"


def test_catalog_and_benchmark_graphs():
    with TestClient(app) as client:
        data = client.get("/api/modelos").json()
        assert data["modelo_ativo"] == settings.MODELO_ATIVO
        assert len(data["treinados"]) == 4
        assert all(m["disponivel"] for m in data["modelos"])
        assert [m["nome"] for m in data["modelos"] if m["em_uso"]] == [settings.MODELO_ATIVO]
        experiments = client.get("/api/treino/experimentos").json()["experimentos"]
        graphs = [e["grafico_url"] for e in experiments if e["grafico_url"]]
        assert len(graphs) >= 4
        for graph in graphs:
            assert client.get(graph).status_code == 200


def test_training_cannot_choose_another_model():
    different = next(name for name in MODELOS if name != settings.MODELO_ATIVO)
    with TestClient(app) as client:
        response = client.post("/api/treino/start", json={"base_model": different + ".pt"})
        assert response.status_code == 400


def test_bad_weights_do_not_replace_active_file(monkeypatch, tmp_path):
    monkeypatch.setattr(settings, "TRAINED_MODELS_DIR", str(tmp_path))
    _, target = model_service.model_paths()
    target.parent.mkdir()
    target.write_bytes(b"previous")
    source = tmp_path / "invalid.pt"
    source.write_bytes(b"invalid")
    def reject(*args, **kwargs):
        raise ValueError("incompatible")
    monkeypatch.setattr(model_service, "validate_weights", reject)
    with pytest.raises(ValueError):
        model_service.publish_weights(source, settings.MODELO_ATIVO)
    assert target.read_bytes() == b"previous"


def test_successful_publication_and_copy_failure(monkeypatch, tmp_path):
    monkeypatch.setattr(settings, "TRAINED_MODELS_DIR", str(tmp_path / "trained"))
    monkeypatch.setattr(model_service, "validate_weights", lambda *args: None)
    source = tmp_path / "new.pt"
    source.write_bytes(b"valid new weights")
    target = Path(model_service.publish_weights(source, settings.MODELO_ATIVO))
    assert target.read_bytes() == source.read_bytes()
    def fail(*args):
        raise OSError("copy failed")
    monkeypatch.setattr(model_service.shutil, "copyfile", fail)
    with pytest.raises(OSError):
        model_service.publish_weights(source, settings.MODELO_ATIVO)
    assert target.read_bytes() == b"valid new weights"
    assert list(target.parent.iterdir()) == [target]


def test_training_uses_actual_output_and_publishes_only_after_success(monkeypatch, tmp_path):
    saved = tmp_path / "actual_run"
    calls = []
    class Model:
        trainer = SimpleNamespace(save_dir=saved)
        def train(self, **kwargs):
            calls.append(kwargs)
    monkeypatch.setattr(training_service, "YOLO", lambda path: Model())
    monkeypatch.setattr(training_service, "_resolve_device", lambda: ("cpu", "CPU"))
    monkeypatch.setattr(training_service, "publish_weights",
                        lambda path, name: calls.append((path, name)) or "published.pt")
    result = training_service._train_dataset("data.yaml", settings.BASE_MODEL, 1, 640, 0.5)
    assert calls[0]["fraction"] == 0.5
    assert calls[0]["name"].startswith(settings.MODELO_ATIVO + "_")
    assert calls[-1] == (saved / "weights" / "best.pt", settings.MODELO_ATIVO)
    assert result["pesos"] == "published.pt"

    def fail(**kwargs):
        raise RuntimeError("interrupted")
    monkeypatch.setattr(Model, "train", lambda self, **kwargs: fail(**kwargs))
    calls.clear()
    with pytest.raises(RuntimeError):
        training_service._train_dataset("data.yaml", settings.BASE_MODEL, 1, 640, 1)
    assert not calls

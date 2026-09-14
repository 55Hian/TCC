"""Dados mínimos temporários: a suíte comum não depende dos artefatos do TCC."""
from pathlib import Path

import cv2
import numpy as np
import pytest

from core.config import MODELOS, settings


@pytest.fixture(autouse=True)
def ambiente_temporario(monkeypatch, tmp_path):
    pastas = {
        "RAW_FRAMES_DIR": "imagens", "LABELME_ANNOTATIONS_DIR": "anotacoes",
        "YOLO_LABELS_DIR": "rotulos", "DATASET_DIR": "dataset",
        "PRETRAINED_MODELS_DIR": "pretreinados", "TRAINED_MODELS_DIR": "treinados",
        "TRAINING_PROJECT": "experimentos", "BENCHMARKS_DIR": "benchmarks",
    }
    for atributo, nome in pastas.items():
        pasta = tmp_path / "ambiente" / nome
        pasta.mkdir(parents=True)
        monkeypatch.setattr(settings, atributo, str(pasta))
    # Os pesos são apenas arquivos de catálogo. Testes de inferência substituem o YOLO.
    for nome in MODELOS:
        (Path(settings.PRETRAINED_MODELS_DIR) / f"{nome}.pt").write_bytes(b"peso simulado")
        pasta = Path(settings.TRAINED_MODELS_DIR) / nome
        pasta.mkdir()
        (pasta / "best.pt").write_bytes(b"peso simulado")
        experimento = Path(settings.TRAINING_PROJECT) / nome
        experimento.mkdir()
        (experimento / "results.csv").write_text("epoch\n1\n", encoding="utf-8")
        (experimento / "results.png").write_bytes(b"grafico simulado")
    imagem = np.zeros((8, 8, 3), dtype=np.uint8)
    (Path(settings.RAW_FRAMES_DIR) / "captura.jpg").write_bytes(cv2.imencode(".jpg", imagem)[1].tobytes())
    from main import app
    for rota in app.routes:
        if getattr(rota, "path", None) == "/static/experiments":
            monkeypatch.setattr(rota.app, "all_directories", [settings.TRAINING_PROJECT])
        elif getattr(rota, "path", None) == "/static/benchmarks":
            monkeypatch.setattr(rota.app, "all_directories", [settings.BENCHMARKS_DIR])

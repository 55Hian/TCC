import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from main import app
from core.config import settings
from routers import stream
from services.event_service import gerar_eventos, calcular_area_intersecao
from services.annotation_converter import labelme_json_to_yolo, converter_labelme_para_yolo


def test_eventos_mao_sobre_produto_e_frame_vazio():
    assert gerar_eventos(pd.DataFrame()) == []
    boxes = pd.DataFrame([
        dict(classe="mao", x_min=0, y_min=0, x_max=10, y_max=10),
        dict(classe="cha", x_min=0, y_min=0, x_max=10, y_max=10),
    ])
    assert gerar_eventos(boxes) == [dict(tipo="interacao_mao", produto="cha", quantidade=1)]
    boxes.loc[1, ["x_min", "x_max"]] = [20, 30]
    assert gerar_eventos(boxes) == []


def test_iou_area_nula():
    box = dict(x_min=0, y_min=0, x_max=0, y_max=0)
    assert calcular_area_intersecao(box, box) == 0


def test_conversao_retangulo_invertido_e_classe_desconhecida(tmp_path):
    entrada = tmp_path / "frame.json"
    entrada.write_text(json.dumps(dict(imageWidth=100, imageHeight=200, shapes=[
        dict(label="cha", points=[[80, 160], [20, 40]]),
        dict(label="desconhecido", points=[[0, 0], [10, 10]]),
    ])))
    saida = labelme_json_to_yolo(str(entrada), str(tmp_path / "labels"), ["cha"])
    assert Path(saida).read_text() == "0 0.500000 0.500000 0.600000 0.600000"


def test_conversao_dimensao_invalida_e_pasta_vazia(tmp_path):
    with pytest.raises(FileNotFoundError):
        converter_labelme_para_yolo(str(tmp_path), str(tmp_path / "labels"))
    entrada = tmp_path / "frame.json"
    entrada.write_text(json.dumps(dict(imageWidth=0, imageHeight=100)))
    with pytest.raises(ValueError):
        labelme_json_to_yolo(str(entrada), str(tmp_path / "labels"))


def test_stream_mjpeg_com_frame_simulado(monkeypatch):
    monkeypatch.setattr(stream, "gerador_de_frames", lambda url: iter([np.zeros((8, 8, 3), dtype=np.uint8)]))
    with TestClient(app) as client:
        response = client.get("/api/stream")
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("multipart/x-mixed-replace")
    assert b"Content-Type: image/jpeg" in response.content
    assert b"\xff\xd8" in response.content


def test_frontend_e_galeria_coerentes_com_arquivos():
    with TestClient(app) as client:
        for path in ["/", "/css/style.css"] + [f"/js/{name}.js" for name in
                ["api", "tabs", "dashboard", "treino", "dataset", "experimentos"]]:
            assert client.get(path).status_code == 200, path
        imagens = client.get("/api/dataset/imagens").json()["imagens"]
        for img in imagens:
            anotacao = Path(settings.LABELME_ANNOTATIONS_DIR) / (Path(img["nome"]).stem + ".json")
            assert img["anotado"] == anotacao.is_file()
            assert client.get("/api/dataset/imagens/" + img["nome"]).status_code == 200

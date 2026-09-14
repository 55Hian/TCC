"""Protege cálculos e arquivos dos scripts sem executar treinamento ou usar GPU."""
import json
import sys

import pandas as pd
import pytest

import benchmark_tcc
import relatorio_benchmark_tcc
import replay_interactions


def criar_anotacao(caminho, pontos=None, tipo="polygon", classe="cha"):
    caminho.parent.mkdir(parents=True, exist_ok=True)
    caminho.write_text(json.dumps({
        "imageWidth": 100, "imageHeight": 100,
        "shapes": [{"label": classe, "shape_type": tipo,
                    "points": pontos or [[10, 20], [30, 40], [90, 90]]}],
    }), encoding="utf-8")


def test_benchmark_usa_todos_os_pontos_e_recorta_limites(tmp_path):
    anotacao = tmp_path / "anotacao.json"
    criar_anotacao(anotacao, [[-10, 20], [30, 40], [110, 90]])
    assert benchmark_tcc.converter_anotacao_benchmark(anotacao) == "2 0.500000 0.550000 1.000000 0.700000"


@pytest.mark.parametrize("alteracao", [
    {"tipo": "circle"}, {"classe": "desconhecida"}, {"pontos": [[10, 20], [10, 30]]},
])
def test_benchmark_rejeita_anotacao_incompativel(tmp_path, alteracao):
    anotacao = tmp_path / "anotacao.json"
    criar_anotacao(anotacao, **alteracao)
    with pytest.raises(ValueError):
        benchmark_tcc.converter_anotacao_benchmark(anotacao)


def preparar_origem_benchmark(raiz, duplicar=False):
    for indice, particao in enumerate(("train", "val")):
        nome = f"imagem_{indice}"
        imagem = raiz / "data/dataset/images" / particao / f"{nome}.jpg"
        rotulo = raiz / "data/dataset/labels" / particao / f"{nome}.txt"
        imagem.parent.mkdir(parents=True)
        rotulo.parent.mkdir(parents=True)
        imagem.write_bytes(b"imagem" if duplicar else f"imagem {indice}".encode())
        rotulo.write_text("anotacao anterior", encoding="utf-8")
        criar_anotacao(raiz / "data/labelme_annotations" / f"{nome}.json")
    (raiz / "data/dataset/data.yaml").write_text("path: anterior\nnames: [cha]\n", encoding="utf-8")


def test_congelamento_preserva_origem_e_registra_hashes(monkeypatch, tmp_path):
    origem, saida = tmp_path / "origem", tmp_path / "copia"
    preparar_origem_benchmark(origem)
    saida.mkdir()
    monkeypatch.setattr(benchmark_tcc, "ROOT", origem)
    resumos, manifesto = benchmark_tcc.congelar_dataset(saida)
    assert len(resumos["train"]) == len(resumos["val"]) == 1
    assert len(manifesto) == 6
    assert all(len(item["sha256"]) == 64 for item in manifesto)
    assert (origem / "data/dataset/labels/train/imagem_0.txt").read_text() == "anotacao anterior"
    assert (saida / "dataset/labels/train/imagem_0.txt").read_text().startswith("2 ")
    assert (saida / "annotations/imagem_0.json").is_file()


def test_congelamento_rejeita_imagem_repetida(monkeypatch, tmp_path):
    origem, saida = tmp_path / "origem", tmp_path / "copia"
    preparar_origem_benchmark(origem, duplicar=True)
    saida.mkdir()
    monkeypatch.setattr(benchmark_tcc, "ROOT", origem)
    with pytest.raises(RuntimeError, match="identicas"):
        benchmark_tcc.congelar_dataset(saida)


def test_avaliacao_replay_conta_duplicatas_e_perdas():
    eventos = [{"produto": "cha", "segundo": 1.1}, {"produto": "cha", "segundo": 1.2}]
    esperados = [{"produto": "cha", "inicio": 1, "fim": 1.3}, {"produto": "gelatina", "inicio": 2, "fim": 3}]
    assert replay_interactions.avaliar_eventos(eventos, esperados) == {
        "corretos": 1, "falsos_ou_duplicados": 1, "perdidos": 1,
    }


def test_baseline_mantem_primeiro_produto_por_mao():
    deteccoes = pd.DataFrame([
        dict(classe=classe, x_min=0, y_min=0, x_max=10, y_max=10)
        for classe in ("mao", "cha", "gelatina")
    ])
    assert replay_interactions.gerar_eventos_baseline(deteccoes) == [
        {"tipo": "interacao_mao", "produto": "cha", "quantidade": 1},
    ]


def preparar_resultados(pasta, epocas=50):
    for nome in ("yolov8n", "yolo12n", "yolo26s", "yolo26m"):
        experimento = pasta / nome
        experimento.mkdir()
        (experimento / "results.csv").write_text(
            "epoch,metrics/mAP50-95(B)\n" + "".join(f"{epoca},{epoca / 100}\n" for epoca in range(1, epocas + 1)),
            encoding="utf-8",
        )
        (pasta / f"{nome}_summary.json").write_text(json.dumps({
            "model": nome, "epochs": epocas, "best_csv_epoch": epocas,
            "precision": 0.8, "recall": 0.7, "map50": 0.6, "map50_95": 0.5,
            "training_seconds": 120, "classes": {"cha": [0.8, 0.7, 0.6, 0.5]},
        }), encoding="utf-8")


def test_relatorio_gera_markdown_csv_e_figura(monkeypatch, tmp_path):
    preparar_resultados(tmp_path)
    monkeypatch.setattr(sys, "argv", ["relatorio_benchmark_tcc.py", str(tmp_path)])
    relatorio_benchmark_tcc.main()
    texto = (tmp_path / "RELATORIO_TCC.md").read_text(encoding="utf-8")
    assert "| yolov8n | 50 | 50 | 80,00 | 70,00 | 60,00 | 50,00 | 2,00 |" in texto
    assert "| yolov8n | 20,00 | 50,00 | 30,00 |" in texto
    assert (tmp_path / "comparativo_por_classe.csv").read_text(encoding="utf-8-sig").count("cha") == 4
    assert (tmp_path / "curvas_map.png").read_bytes().startswith(b"\x89PNG")


def test_relatorio_rejeita_treino_incompleto(monkeypatch, tmp_path):
    preparar_resultados(tmp_path, epocas=49)
    monkeypatch.setattr(sys, "argv", ["relatorio_benchmark_tcc.py", str(tmp_path)])
    with pytest.raises(RuntimeError, match="50 epocas"):
        relatorio_benchmark_tcc.main()
    assert not (tmp_path / "RELATORIO_TCC.md").exists()



@pytest.mark.parametrize("modo", ["--baseline", "--iou-only", None])
def test_replay_processa_video_e_fecha_recursos(monkeypatch, tmp_path, modo):
    from unittest.mock import Mock
    import numpy as np
    from core.config import settings
    monkeypatch.setattr(settings, "HAND_LANDMARKS_ENABLED", settings.HAND_LANDMARKS_ENABLED)
    captura = Mock()
    captura.isOpened.return_value = True
    captura.get.return_value = 10
    imagem = np.zeros((2, 2, 3), dtype=np.uint8)
    captura.read.side_effect = [(True, imagem), (True, imagem), (False, None)]
    visao = Mock()
    visao.processar_frame.return_value = pd.DataFrame()
    monkeypatch.setattr(replay_interactions.cv2, "VideoCapture", lambda caminho: captura)
    monkeypatch.setattr(replay_interactions, "ServicoVisao", lambda *dados, **opcoes: visao)
    saida = tmp_path / "eventos.json"
    argumentos = ["replay_interactions.py", "simulado.mp4", "--output", str(saida)]
    if modo:
        argumentos.append(modo)
    monkeypatch.setattr(sys, "argv", argumentos)
    replay_interactions.main()
    relatorio = json.loads(saida.read_text(encoding="utf-8"))
    assert relatorio["frames"] == 2
    assert relatorio["eventos"] == []
    assert relatorio["modo"] == {None: "landmarks_temporal", "--baseline": "baseline", "--iou-only": "iou_temporal"}[modo]
    captura.release.assert_called_once()
    visao.fechar.assert_called_once()

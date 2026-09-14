"""Casos de falha e interfaces preservadas na separação dos serviços."""
import json
import random
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest

from core.config import settings
from services import annotation_converter, hand_service, model_service, training_service


def test_interfaces_anteriores_aceitam_argumentos_nomeados(tmp_path):
    from services.event_service import EventService, ServicoEventos
    from services.shared_camera import SharedCamera, CameraCompartilhada
    assert EventService is ServicoEventos
    assert SharedCamera is CameraCompartilhada
    assert model_service.model_paths(name=settings.MODELO_ATIVO) == model_service.caminhos_modelo(settings.MODELO_ATIVO)
    entrada = tmp_path / "entrada.json"
    entrada.write_text('{"imageWidth": 100, "imageHeight": 100, "shapes": []}', encoding="utf-8")
    saida = annotation_converter.labelme_json_to_yolo(json_path=entrada, output_dir=tmp_path / "saida", classes=["cha"])
    assert Path(saida).read_text() == ""


def test_pontos_da_mao_convertidos_para_pixels():
    pontos = [SimpleNamespace(x=0.25, y=0.75), SimpleNamespace(x=0.75, y=0.25)]
    deteccao = hand_service._converter_pontos(pontos, 200, 100)
    assert deteccao["landmarks"] == [(50, 75), (150, 25)]
    assert (deteccao["x_min"], deteccao["y_min"], deteccao["x_max"], deteccao["y_max"]) == (50, 25, 150, 75)


def test_maos_exigem_instantes_crescentes(monkeypatch):
    instantes = []
    servico = hand_service.ServicoMaos.__new__(hand_service.ServicoMaos)
    servico.last_timestamp = -1
    servico.mp = SimpleNamespace(Image=lambda **dados: dados, ImageFormat=SimpleNamespace(SRGB="rgb"))
    def detectar(imagem, instante):
        instantes.append(instante)
        return SimpleNamespace(hand_landmarks=[])
    servico.detector = SimpleNamespace(detect_for_video=detectar)
    for instante in (1, 1, 0.5):
        assert servico.processar_frame(np.zeros((2, 2, 3), dtype=np.uint8), instante) == []
    assert instantes == [1000, 1001, 1002]


def test_validacao_de_pesos_confere_classes_e_arquitetura(monkeypatch, tmp_path):
    pesos = tmp_path / "pesos.pt"
    pesos.write_bytes(b"simulado")
    modelo = SimpleNamespace(names=dict(enumerate(settings.CLASSES)),
                             ckpt={"train_args": {"model": settings.MODELO_ATIVO + ".pt"}})
    monkeypatch.setattr(model_service, "YOLO", lambda caminho: modelo)
    assert model_service.validar_pesos(pesos, settings.MODELO_ATIVO) is modelo
    modelo.names = {0: "outra"}
    with pytest.raises(ValueError, match="Classes"):
        model_service.validar_pesos(pesos, settings.MODELO_ATIVO)
    modelo.names = dict(enumerate(settings.CLASSES))
    modelo.ckpt["train_args"]["model"] = "outra.pt"
    with pytest.raises(ValueError, match="Arquitetura"):
        model_service.validar_pesos(pesos, settings.MODELO_ATIVO)


def test_dataset_separa_pares_sem_alterar_aleatoriedade_global(monkeypatch):
    monkeypatch.setattr(settings, "USE_EXTERNAL_VALIDATION_DATASET", False)
    for indice in range(5):
        nome = f"produto_{indice}"
        (Path(settings.RAW_FRAMES_DIR) / f"{nome}.jpg").write_bytes(f"imagem {indice}".encode())
        (Path(settings.LABELME_ANNOTATIONS_DIR) / f"{nome}.json").write_text(json.dumps({
            "imageWidth": 100, "imageHeight": 100,
            "shapes": [{"label": "cha", "points": [[10, 10], [20, 20]]}],
        }), encoding="utf-8")
    chamadas = []
    monkeypatch.setattr(training_service, "_treinar_dataset", lambda *dados: chamadas.append(dados) or {"pesos": "simulado"})
    estado_aleatorio = random.getstate()
    assert training_service.rodar_pipeline_treinamento()["pesos"] == "simulado"
    assert random.getstate() == estado_aleatorio
    raiz = Path(settings.DATASET_DIR)
    for particao, quantidade in (("train", 4), ("val", 1)):
        imagens = {arquivo.stem for arquivo in (raiz / "images" / particao).iterdir()}
        rotulos = {arquivo.stem for arquivo in (raiz / "labels" / particao).iterdir()}
        assert imagens == rotulos
        assert len(imagens) == quantidade
    assert chamadas[0][0] == str(raiz / "data.yaml")


def test_falha_codificacao_nao_publica_jpeg(monkeypatch, tmp_path):
    import capturar_frames as captura
    monkeypatch.setattr(captura.cv2, "imencode", lambda *dados: (False, None))
    with pytest.raises(OSError, match="codificar"):
        captura.capturar_frames(pasta_saida=str(tmp_path / "saida"), intervalo=0,
                                mostrar_janela=False, fonte_frames=iter([np.zeros((2, 2, 3), dtype=np.uint8)]))
    assert list((tmp_path / "saida").iterdir()) == []


def test_falha_treino_e_captura_atualiza_estado(monkeypatch):
    from core.state import state
    from routers import dataset, treino
    for atributo in ("treino_status", "treino_erro", "captura_status", "captura_erro", "captura_total"):
        monkeypatch.setattr(state, atributo, getattr(state, atributo))
    def falhar(*dados, **opcoes):
        raise RuntimeError("falha controlada")
    monkeypatch.setattr(treino, "rodar_pipeline_treinamento", falhar)
    monkeypatch.setattr(dataset, "capturar_frames", falhar)
    treino._executar(settings.BASE_MODEL, 1, 640, 1)
    dataset._executar_captura(0, 1)
    assert state.treino_status == state.captura_status == "erro"
    assert state.treino_erro == state.captura_erro == "falha controlada"



@pytest.mark.parametrize("eventos", [None, []])
def test_controlador_ignora_ausencia_de_eventos(eventos, capsys):
    from controllers.api_controller import enviar_eventos
    enviar_eventos(eventos)
    assert capsys.readouterr().out == ""

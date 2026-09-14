"""Casos de fronteira observáveis antes e depois da refatoração."""
import asyncio
import json
from pathlib import Path
from unittest.mock import Mock

import numpy as np
import pytest

from core.state import EstadoAplicacao
from services.annotation_converter import converter_arquivo_labelme
from services.annotation_paths import preparar_anotacoes
from services.shared_camera import CameraCompartilhada


def test_json_invalido_nao_cria_rotulo(tmp_path):
    entrada = tmp_path / "entrada.json"
    entrada.write_text("{", encoding="utf-8")
    with pytest.raises(json.JSONDecodeError):
        converter_arquivo_labelme(entrada, tmp_path / "saida")
    assert not (tmp_path / "saida").exists()


def test_poligono_da_aplicacao_preserva_regra_historica(tmp_path):
    entrada = tmp_path / "poligono.json"
    entrada.write_text(json.dumps({
        "imageWidth": 100, "imageHeight": 100,
        "shapes": [{"label": "cha", "points": [[10, 20], [30, 40], [90, 90]]}],
    }), encoding="utf-8")
    saida = converter_arquivo_labelme(entrada, tmp_path / "saida", ["cha"])
    assert Path(saida).read_text() == "0 0.200000 0.300000 0.200000 0.200000"


def test_reparo_valida_todos_os_arquivos_antes_de_gravar(tmp_path):
    imagens, anotacoes = tmp_path / "imagens", tmp_path / "anotacoes"
    imagens.mkdir()
    anotacoes.mkdir()
    (imagens / "primeira.jpg").write_bytes(b"imagem")
    conteudo = '{"imagePath": "ausente.jpg", "imageData": null}'
    for nome in ("primeira", "segunda"):
        (anotacoes / f"{nome}.json").write_text(conteudo, encoding="utf-8")
    with pytest.raises(ValueError):
        preparar_anotacoes(imagens, anotacoes)
    assert all(arquivo.read_text(encoding="utf-8") == conteudo for arquivo in anotacoes.glob("*.json"))


def test_camera_descarta_imagem_antiga(monkeypatch):
    import services.shared_camera as modulo
    camera = CameraCompartilhada("simulada")
    camera._imagem = np.zeros((2, 2, 3), dtype=np.uint8)
    camera._sequencia = 1
    camera._ultimo_recebimento = 10
    monkeypatch.setattr(modulo.time, "monotonic", lambda: 14)
    assert camera.aguardar_frame(timeout=0) is None


def test_estado_limita_historico_e_remove_cliente_desconectado():
    estado = EstadoAplicacao(max_eventos=2)
    for numero in range(3):
        estado.adicionar_evento({"numero": numero})
    assert estado.listar_eventos() == [{"numero": 1}, {"numero": 2}]
    recebidos = []
    class Cliente:
        async def send_json(self, evento):
            recebidos.append(evento)
    class Desconectado:
        async def send_json(self, evento):
            raise ConnectionError("desconectado")
    cliente, desconectado = Cliente(), Desconectado()
    estado.ws_clients.update((cliente, desconectado))
    asyncio.run(estado._broadcast({"numero": 3}))
    assert recebidos == [{"numero": 3}]
    assert estado.ws_clients == {cliente}


def test_falha_da_visao_libera_consumidor(monkeypatch):
    import worker
    visao = Mock()
    visao.processar_frame.side_effect = RuntimeError("falha simulada")
    camera = Mock()
    camera.adquirir.return_value = "monitor"
    camera.aguardar_frame.return_value = (1, np.zeros((2, 2, 3), dtype=np.uint8))
    monkeypatch.setattr(worker, 'ServicoVisao', lambda: visao)
    monkeypatch.setattr(worker, "camera", camera)
    worker._sinal_parada.clear()
    try:
        worker._loop_monitoramento()
        visao.fechar.assert_called_once()
        camera.liberar.assert_called_once_with("monitor")
    finally:
        worker.state.monitor_status = "parado"

import os
import sys

import numpy as np
import pytest

PROJ_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJ_DIR not in sys.path:
    sys.path.insert(0, PROJ_DIR)

from capturar_frames import capturar_frames, deve_capturar, gerar_nome_arquivo


def test_deve_capturar_intervalo_nao_decorrido():
    assert deve_capturar(ultimo_salvamento=10.0, agora=10.5, intervalo=2.0) is False


def test_deve_capturar_intervalo_decorrido_exato():
    assert deve_capturar(ultimo_salvamento=10.0, agora=12.0, intervalo=2.0) is True


def test_deve_capturar_intervalo_excedido():
    assert deve_capturar(ultimo_salvamento=10.0, agora=15.0, intervalo=2.0) is True


def test_gerar_nome_arquivo_eh_unico_por_contador():
    nome_0 = gerar_nome_arquivo(0)
    nome_1 = gerar_nome_arquivo(1)
    assert nome_0 != nome_1
    assert nome_0.endswith("_0000.jpg")
    assert nome_1.endswith("_0001.jpg")


def _frame_falso():
    return np.zeros((10, 10, 3), dtype=np.uint8)


def test_capturar_frames_respeita_max_frames_com_fonte_falsa(tmp_path):
    frames_falsos = [_frame_falso() for _ in range(50)]

    total_salvo = capturar_frames(
        pasta_saida=str(tmp_path),
        intervalo=0.0,
        max_frames=5,
        mostrar_janela=False,
        fonte_frames=iter(frames_falsos),
    )

    arquivos = sorted(p for p in os.listdir(tmp_path) if p.endswith(".jpg"))
    assert total_salvo == 5
    assert len(arquivos) == 5


def test_capturar_frames_cria_pasta_saida_se_nao_existir(tmp_path):
    pasta_saida = tmp_path / "nao_existe_ainda"
    capturar_frames(
        pasta_saida=str(pasta_saida),
        intervalo=0.0,
        max_frames=1,
        mostrar_janela=False,
        fonte_frames=iter([_frame_falso()]),
    )
    assert pasta_saida.is_dir()


def test_capturar_frames_sem_max_frames_para_com_fonte_finita(tmp_path):
    frames_falsos = [_frame_falso() for _ in range(3)]
    total_salvo = capturar_frames(
        pasta_saida=str(tmp_path),
        intervalo=0.0,
        max_frames=0,
        mostrar_janela=False,
        fonte_frames=iter(frames_falsos),
    )
    assert total_salvo == 3

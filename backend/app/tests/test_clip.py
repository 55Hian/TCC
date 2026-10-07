"""
Testes do gravador de retirada. Usam uma câmera simulada, então não exigem
hardware. Executar com:  python -m unittest test_gravador_retirada -v

Limitação: validam a lógica (janela, FPS, arquivo, falhas), não o
comportamento de uma câmera real nem a reprodução em navegador.
"""

import os
import tempfile
import threading
import time
import unittest
from pathlib import Path
from unittest.mock import patch

import cv2
import numpy as np

from app.services import clip_service
from app.services.clip_service import GravadorRetirada



CAPTURA_REAL = cv2.VideoCapture  # guardada antes de qualquer patch


class CameraFalsa:
    """Entrega frames 160x120 a ~20 fps, como uma webcam."""

    def __init__(self, fonte, *args):
        self.n = 0

    def isOpened(self):
        return True

    def read(self):
        time.sleep(0.05)
        self.n += 1
        return True, np.full((120, 160, 3), self.n % 255, dtype=np.uint8)

    def release(self):
        pass


class CameraQueNaoAbre:
    def __init__(self, fonte, *args):
        pass

    def isOpened(self):
        return False

    def release(self):
        pass


def criar_gravador(pasta, **kwargs):
    return GravadorRetirada(
        pasta_saida=pasta, segundos_antes=2, segundos_depois=1, fps_buffer=10, **kwargs
    )


class TestGravadorRetirada(unittest.TestCase):

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.pasta = Path(self._tmp.name)

    def tearDown(self):
        self._tmp.cleanup()

    def test_grava_janela_antes_e_depois_do_evento(self):
        resultado = {}
        pronto = threading.Event()

        def ao_concluir(id_evento, caminho):
            resultado["id"], resultado["caminho"] = id_evento, caminho
            pronto.set()

        with patch.object(clip_service.cv2, "VideoCapture", CameraFalsa):
            gravador = criar_gravador(self.pasta)
            gravador.iniciar()
            time.sleep(3)  # enche o buffer com mais que a janela anterior
            gravador.gravar_retirada(152, ao_concluir=ao_concluir)
            self.assertTrue(pronto.wait(timeout=10), "gravação não terminou")
            gravador.parar()

        self.assertEqual(resultado["id"], 152)
        self.assertIsNotNone(resultado["caminho"])
        self.assertTrue(Path(resultado["caminho"]).exists())
        self.assertEqual(Path(resultado["caminho"]).name, "evento_152.mp4")

        video = CAPTURA_REAL(resultado["caminho"])
        self.assertTrue(video.isOpened())
        frames = int(video.get(cv2.CAP_PROP_FRAME_COUNT))
        fps = video.get(cv2.CAP_PROP_FPS)
        video.release()

        # Janela pedida: 2 s antes + 1 s depois = 3 s. FPS vem dos timestamps (~10).
        duracao = frames / fps
        self.assertAlmostEqual(duracao, 3.0, delta=0.8)
        self.assertAlmostEqual(fps, 10, delta=2)

    def test_sem_frames_retorna_none_e_nao_cria_arquivo(self):
        resultado = {}
        pronto = threading.Event()

        def ao_concluir(id_evento, caminho):
            resultado["caminho"] = caminho
            pronto.set()

        gravador = GravadorRetirada(
            pasta_saida=self.pasta, segundos_antes=2, segundos_depois=0
        )  # captura nunca iniciada: buffer vazio
        gravador.gravar_retirada(7, ao_concluir=ao_concluir)

        self.assertTrue(pronto.wait(timeout=5))
        self.assertIsNone(resultado["caminho"])
        self.assertEqual(list(self.pasta.glob("*.mp4")), [])

    def test_id_malicioso_nao_escapa_da_pasta(self):
        gravador = GravadorRetirada(pasta_saida=self.pasta)
        frame = np.zeros((120, 160, 3), dtype=np.uint8)
        _, jpg = cv2.imencode(".jpg", frame)
        agora = time.time()
        janela = [(agora + i * 0.1, jpg.tobytes()) for i in range(5)]

        caminho = gravador._escrever_video("../../fora", janela)

        self.assertIsNotNone(caminho)
        self.assertEqual(Path(caminho).resolve().parent, self.pasta.resolve())

    def test_camera_que_nao_abre_nao_derruba_e_para_rapido(self):
        with patch.object(clip_service.cv2, "VideoCapture", CameraQueNaoAbre):
            gravador = criar_gravador(self.pasta)
            gravador.iniciar()
            time.sleep(0.3)
            self.assertTrue(gravador._thread.is_alive())
            inicio = time.time()
            gravador.parar()
            self.assertLess(time.time() - inicio, 2)  # não espera os 5 s de retry

    def test_repassa_backend_para_o_opencv_somente_quando_informado(self):
        chamadas = []

        class CameraEspia(CameraQueNaoAbre):
            def __init__(self, *args):
                chamadas.append(args)

        with patch.object(clip_service.cv2, "VideoCapture", CameraEspia):
            for kwargs in ({}, {"backend": cv2.CAP_DSHOW}):
                gravador = criar_gravador(self.pasta, **kwargs)
                gravador.iniciar()
                time.sleep(0.3)
                gravador.parar()

        self.assertEqual(chamadas[0], (0,))
        self.assertEqual(chamadas[1], (0, cv2.CAP_DSHOW))

    def test_erro_no_callback_nao_propaga(self):
        terminou = threading.Event()

        def callback_quebrado(id_evento, caminho):
            terminou.set()
            raise ValueError("falha proposital")

        gravador = GravadorRetirada(pasta_saida=self.pasta, segundos_depois=0)
        gravador.gravar_retirada(1, ao_concluir=callback_quebrado)
        self.assertTrue(terminou.wait(timeout=5))  # chegou ao callback sem derrubar nada

    def test_apagar_antigos_remove_so_os_vencidos(self):
        velho = self.pasta / "evento_1.mp4"
        novo = self.pasta / "evento_2.mp4"
        velho.write_bytes(b"x")
        novo.write_bytes(b"x")
        dez_dias = time.time() - 10 * 86400
        os.utime(velho, (dez_dias, dez_dias))

        GravadorRetirada(pasta_saida=self.pasta).apagar_antigos(dias=7)

        self.assertFalse(velho.exists())
        self.assertTrue(novo.exists())


if __name__ == "__main__":
    unittest.main()

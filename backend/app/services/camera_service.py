import threading
import urllib.request

import cv2
import numpy as np


LIMITE_BUFFER_BYTES = 4 * 1024 * 1024


def gerador_de_frames(url_stream, stop_event=None, on_status=None):
    """Leitor exclusivo de rede; fecha a resposta em falha ou cancelamento."""
    sinal_parada = stop_event if stop_event is not None else threading.Event()
    informar_status = on_status or (lambda status, erro=None: None)
    while not sinal_parada.is_set():
        try:
            informar_status("conectando")
            print(f"[CAMERA] Conectando em {url_stream}...")
            with urllib.request.urlopen(url_stream, timeout=3) as fluxo:
                yield from _decodificar_resposta(fluxo, sinal_parada)
        except Exception as erro:
            informar_status("reconectando", str(erro))
            print(f"[CAMERA] Falha: {erro}. Reconectando em 2 segundos...")
            sinal_parada.wait(2)


def _decodificar_resposta(fluxo, sinal_parada):
    """Remonta JPEGs entre blocos de rede e descarta bytes antes do marcador inicial."""
    dados_pendentes = b""
    while not sinal_parada.is_set():
        bloco = fluxo.read1(4096)
        if not bloco:
            raise ConnectionError("stream encerrado")
        dados_pendentes += bloco
        if len(dados_pendentes) > LIMITE_BUFFER_BYTES:
            raise ValueError("JPEG excedeu limite de buffer")
        while True:
            inicio = dados_pendentes.find(b"\xff\xd8")
            if inicio < 0:
                dados_pendentes = dados_pendentes[-1:]
                break
            dados_pendentes = dados_pendentes[inicio:]
            fim = dados_pendentes.find(b"\xff\xd9", 2)
            if fim < 0:
                break
            jpg, dados_pendentes = dados_pendentes[:fim + 2], dados_pendentes[fim + 2:]
            imagem = cv2.imdecode(np.frombuffer(jpg, dtype=np.uint8), cv2.IMREAD_COLOR)
            if imagem is not None:
                yield imagem

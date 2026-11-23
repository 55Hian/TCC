"""Controle do monitoramento de camera."""
import time

from fastapi import APIRouter, HTTPException
from fastapi.responses import Response, StreamingResponse

from config import STREAM_MAX_FPS
from services.monitoramento import monitor

FRONTEIRA = "quadro"

router = APIRouter(prefix="/api/monitoramento", tags=["monitoramento"])


@router.post("/iniciar")
def iniciar():
    return {"iniciado": monitor.iniciar(), "status": monitor.status}


@router.post("/parar")
def parar():
    return {"status": monitor.parar()}


@router.get("/status")
def status():
    return {"status": monitor.status, "erro": monitor.erro, "metricas": monitor.metricas}


@router.get("/frame")
def frame_atual():
    if monitor.ultimo_jpeg is None:
        raise HTTPException(status_code=404, detail="Ainda nao ha imagem processada")
    return Response(monitor.ultimo_jpeg, media_type="image/jpeg")


def _quadros_mjpeg():
    """Envia cada quadro processado assim que fica pronto, limitado a TCC_STREAM_FPS."""
    intervalo = 1 / STREAM_MAX_FPS if STREAM_MAX_FPS > 0 else 0
    seq, ultimo_envio = 0, 0.0
    while True:
        novo_seq, dados = monitor.aguardar_quadro(seq)
        if novo_seq == seq or dados is None:
            if not monitor.ativo():
                return
            continue
        espera = ultimo_envio + intervalo - time.monotonic()
        if espera > 0:
            time.sleep(espera)
            novo_seq, dados = monitor.aguardar_quadro(novo_seq, timeout=0)
        seq, ultimo_envio = novo_seq, time.monotonic()
        yield (b"--" + FRONTEIRA.encode() + b"\r\nContent-Type: image/jpeg\r\nContent-Length: "
               + str(len(dados)).encode() + b"\r\n\r\n" + dados + b"\r\n")


@router.get("/stream")
def stream():
    if not monitor.ativo():
        raise HTTPException(status_code=409, detail="O monitoramento nao esta em execucao")
    return StreamingResponse(
        _quadros_mjpeg(),
        media_type=f"multipart/x-mixed-replace; boundary={FRONTEIRA}",
        headers={"Cache-Control": "no-store"},
    )

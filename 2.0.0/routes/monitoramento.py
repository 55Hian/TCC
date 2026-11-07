"""Controle do monitoramento de camera."""
from fastapi import APIRouter, HTTPException
from fastapi.responses import Response

from services.monitoramento import monitor

router = APIRouter(prefix="/api/monitoramento", tags=["monitoramento"])


@router.post("/iniciar")
def iniciar():
    return {"iniciado": monitor.iniciar(), "status": monitor.status}


@router.post("/parar")
def parar():
    return {"status": monitor.parar()}


@router.get("/status")
def status():
    return {"status": monitor.status, "erro": monitor.erro}


@router.get("/frame")
def frame_atual():
    if monitor.ultimo_jpeg is None:
        raise HTTPException(status_code=404, detail="Ainda nao ha imagem processada")
    return Response(monitor.ultimo_jpeg, media_type="image/jpeg")

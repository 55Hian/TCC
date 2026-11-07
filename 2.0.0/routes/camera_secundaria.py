"""Agenda clipes da camera USB para um timestamp de retirada."""
from datetime import datetime
from pathlib import Path

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field, field_validator

from config import VIDEO_DIR
from services.camera_secundaria import camera_secundaria
from services.database import caminho_video_evento, status_video_evento

router = APIRouter(prefix="/api/camera-secundaria", tags=["camera-secundaria"])


class GravacaoEntrada(BaseModel):
    id_evento: int = Field(gt=0)
    timestamp: datetime

    @field_validator("timestamp")
    @classmethod
    def timestamp_com_fuso(cls, valor):
        if valor.tzinfo is None or valor.utcoffset() is None:
            raise ValueError("O timestamp precisa incluir fuso horario")
        return valor


@router.get("/status")
def status_camera():
    return camera_secundaria.status()


@router.post("/gravar", status_code=202)
def gravar_evento(entrada: GravacaoEntrada):
    try:
        job = camera_secundaria.agendar_gravacao(entrada.id_evento, entrada.timestamp)
    except ValueError as erro:
        raise HTTPException(status_code=409, detail=str(erro)) from erro
    except RuntimeError as erro:
        raise HTTPException(status_code=503, detail=str(erro)) from erro
    return {"agendado": True, **job}


@router.get("/gravacoes/{id_evento}")
def status_gravacao(id_evento: int):
    gravacao = camera_secundaria.status_gravacao(id_evento)
    if gravacao is not None:
        return gravacao
    registro = status_video_evento(id_evento)
    if registro is None:
        raise HTTPException(status_code=404, detail="Gravacao nao encontrada")
    return {
        "id_evento": id_evento,
        "status": registro["video_status"],
        "caminho": registro["video_path"],
        "erro": None,
    }


@router.get("/gravacoes/{id_evento}/arquivo")
def arquivo_gravacao(id_evento: int):
    caminho = caminho_video_evento(id_evento)
    if not caminho:
        raise HTTPException(status_code=404, detail="Video ainda nao foi salvo")
    arquivo = Path(caminho).resolve()
    pasta = VIDEO_DIR.resolve()
    if not arquivo.is_relative_to(pasta) or not arquivo.is_file():
        raise HTTPException(status_code=404, detail="Arquivo de video nao encontrado")
    return FileResponse(arquivo, media_type="video/mp4")

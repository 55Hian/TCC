"""Rotas de gravacao e consulta dos eventos gerados pela camera."""
import json
from datetime import datetime, timezone

import psycopg
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from services.database import listar_interacoes, salvar_interacao

router = APIRouter(prefix="/api/eventos", tags=["eventos"])


class EventoEntrada(BaseModel):
    tipo: str
    produto: str
    quantidade: int = 1
    mao_id: int | None = None
    produto_id: int | None = None
    pontos_mao: list[int] | None = None
    metodo: str | None = None
    interpretacao: str | None = None


def _formato_evento(registro):
    pontos = registro.get("pontos_mao")
    if isinstance(pontos, str):
        try:
            pontos = json.loads(pontos)
        except json.JSONDecodeError:
            pass
    momento = registro["momento"]
    if momento.tzinfo is None:
        momento = momento.replace(tzinfo=timezone.utc)
    return {
        "id": registro["id"], "tipo": registro["tipo"], "produto": registro["produto"],
        "quantidade": registro["quantidade"], "mao_id": registro["mao_id"],
        "produto_id": registro["produto_id"], "pontos_mao": pontos,
        "metodo": registro["metodo"], "interpretacao": registro["interpretacao"],
        "video_path": registro.get("video_path"), "video_status": registro.get("video_status"),
        "timestamp": momento,
    }


@router.post("", status_code=201)
def receber_evento(evento: EventoEntrada):
    momento = datetime.now(timezone.utc)
    try:
        registro = salvar_interacao(evento.model_dump(exclude_none=True), momento)
    except psycopg.Error as erro:
        raise HTTPException(status_code=503, detail="Banco indisponivel; evento nao foi gravado") from erro
    return _formato_evento(registro)


@router.get("")
def listar_eventos():
    try:
        registros = listar_interacoes()
    except psycopg.Error as erro:
        raise HTTPException(status_code=503, detail="Banco indisponivel; eventos nao podem ser consultados") from erro
    return {"eventos": [_formato_evento(item) for item in registros]}


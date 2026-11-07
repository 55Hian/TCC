"""Recebe variacao de peso e grava com horario gerado pela API."""
from datetime import datetime, timezone

import psycopg
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from services.database import listar_variacoes, salvar_variacao

router = APIRouter(prefix="/api/balanca", tags=["balanca"])


class LeituraPeso(BaseModel):
    variacao_peso: float = Field(description="Variacao de peso recebida da balanca")


@router.post("", status_code=201)
def receber_variacao(leitura: LeituraPeso):
    momento = datetime.now(timezone.utc)
    try:
        registro = salvar_variacao(leitura.variacao_peso, momento)
    except psycopg.Error as erro:
        raise HTTPException(status_code=503, detail="Banco indisponivel; variacao nao foi gravada") from erro
    timestamp = registro["momento"]
    if timestamp.tzinfo is None:
        timestamp = timestamp.replace(tzinfo=timezone.utc)
    return {"id": registro["id"], "variacao_peso": registro["variacao_peso"], "timestamp": timestamp}


@router.get("")
def consultar_variacoes(limite: int = 100):
    if limite < 1 or limite > 500:
        raise HTTPException(status_code=422, detail="O limite deve ficar entre 1 e 500")
    try:
        registros = listar_variacoes(limite)
    except psycopg.Error as erro:
        raise HTTPException(status_code=503, detail="Banco indisponivel; variacoes nao podem ser consultadas") from erro
    return {"variacoes": [
        {"id": item["id"], "variacao_peso": item["variacao_peso"],
         "timestamp": item["momento"].replace(tzinfo=timezone.utc)
         if item["momento"].tzinfo is None else item["momento"]}
        for item in registros
    ]}

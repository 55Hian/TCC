"""Rotas para capturar frames, abrir Labelme e treinar YOLO."""
import threading

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from services.captura import capturar
from services.anotacoes import abrir_labelme
from services.treinamento import treinar

router = APIRouter(prefix="/api/treinamento", tags=["treinamento"])
_treino = {"status": "ocioso", "erro": None, "resultado": None}
_captura = {"status": "ocioso", "erro": None, "total": 0}
_thread_treino = None
_thread_captura = None


class Captura(BaseModel):
    intervalo: float = Field(default=2, gt=0)
    quantidade: int = Field(default=20, ge=1)


class Treino(BaseModel):
    epochs: int = Field(default=50, ge=1)
    imgsz: int = Field(default=640, ge=32)


def _capturar(entrada):
    _captura.update(status="rodando", erro=None, total=0)
    try:
        _captura["total"] = capturar(entrada.intervalo, entrada.quantidade)
        _captura["status"] = "concluido"
    except Exception as erro:
        _captura.update(status="erro", erro=str(erro))


def _treinar(entrada):
    _treino.update(status="rodando", erro=None, resultado=None)
    try:
        _treino["resultado"] = treinar(entrada.epochs, entrada.imgsz)
        _treino["status"] = "concluido"
    except Exception as erro:
        _treino.update(status="erro", erro=str(erro))


@router.post("/capturar")
def iniciar_captura(entrada: Captura):
    global _thread_captura
    if _thread_captura and _thread_captura.is_alive():
        raise HTTPException(status_code=409, detail="Ja existe uma captura em andamento")
    _thread_captura = threading.Thread(target=_capturar, args=(entrada,), daemon=True)
    _thread_captura.start()
    return {"iniciado": True}


@router.get("/captura/status")
def status_captura():
    return dict(_captura)


@router.post("/labelme")
def iniciar_labelme():
    try:
        processo = abrir_labelme()
        return {"iniciado": True, "pid": processo.pid}
    except Exception as erro:
        raise HTTPException(status_code=500, detail=str(erro))


@router.post("/treinar")
def iniciar_treino(entrada: Treino):
    global _thread_treino
    if _thread_treino and _thread_treino.is_alive():
        raise HTTPException(status_code=409, detail="Ja existe um treino em andamento")
    _thread_treino = threading.Thread(target=_treinar, args=(entrada,), daemon=True)
    _thread_treino.start()
    return {"iniciado": True}


@router.get("/status")
def status_treino():
    return dict(_treino)

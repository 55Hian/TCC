"""Valida pedidos de treino e acompanha sua execução sem bloquear a API."""
import threading

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from pathlib import Path

from core.config import settings
from core.state import state
from services.training_service import rodar_pipeline_treinamento
from services.experiment_service import listar_experimentos as consultar_experimentos

router = APIRouter(prefix="/api/treino", tags=["treino"])

_thread = None


class TreinoEntrada(BaseModel):
    base_model: str | None = None  # nome do arquivo em models/pretrained, ex: "yolo26s.pt"
    epochs: int = Field(default=50, ge=1)
    imgsz: int = Field(default=640, ge=32)
    fraction: float = Field(default=1.0, gt=0, le=1)


def _executar(base_model_path, epochs, imgsz, fraction):
    state.treino_status = "rodando"
    state.treino_erro = None
    try:
        rodar_pipeline_treinamento(base_model=base_model_path, epochs=epochs, imgsz=imgsz, fraction=fraction)
        state.treino_status = "concluido"
    except Exception as erro:
        state.treino_status = "erro"
        state.treino_erro = str(erro)


@router.post("/start")
def iniciar_treino(entrada: TreinoEntrada):
    global _thread
    if _thread is not None and _thread.is_alive():
        raise HTTPException(status_code=409, detail="Ja existe um treino em andamento.")

    base_model_path = settings.BASE_MODEL
    if entrada.base_model and entrada.base_model not in (settings.MODELO_ATIVO + ".pt", base_model_path):
        raise HTTPException(status_code=400, detail="O modelo deve corresponder a MODELO_ATIVO. Altere config.py e reinicie.")
    if not Path(base_model_path).is_file():
        raise HTTPException(status_code=400, detail=f"Modelo base ausente: {base_model_path}")

    _thread = threading.Thread(
        target=_executar,
        args=(base_model_path, entrada.epochs, entrada.imgsz, entrada.fraction),
        daemon=True,
        name="treino-worker",
    )
    _thread.start()
    return {"iniciado": True, "base_model": base_model_path}


@router.get("/status")
def status_treino():
    return {"status": state.treino_status, "erro": state.treino_erro, "modelo_ativo": settings.MODELO_ATIVO}


@router.get("/experimentos")
def listar_experimentos():
    return consultar_experimentos()

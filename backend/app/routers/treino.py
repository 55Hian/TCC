import os
import threading

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from core.config import settings
from core.state import state
from services.training_service import rodar_pipeline_treinamento

router = APIRouter(prefix="/api/treino", tags=["treino"])

_thread = None


class TreinoEntrada(BaseModel):
    base_model: str | None = None  # nome do arquivo em models/pretrained, ex: "yolo26s.pt"
    epochs: int = 50
    imgsz: int = 640
    fraction: float = 1.0


def _executar(base_model_path, epochs, imgsz, fraction):
    state.treino_status = "rodando"
    state.treino_erro = None
    try:
        rodar_pipeline_treinamento(base_model=base_model_path, epochs=epochs, imgsz=imgsz, fraction=fraction)
        state.treino_status = "concluido"
    except Exception as exc:
        state.treino_status = "erro"
        state.treino_erro = str(exc)


@router.post("/start")
def iniciar_treino(entrada: TreinoEntrada):
    global _thread
    if _thread is not None and _thread.is_alive():
        raise HTTPException(status_code=409, detail="Ja existe um treino em andamento.")

    base_model_path = settings.BASE_MODEL
    if entrada.base_model:
        candidato = os.path.join(settings.PRETRAINED_MODELS_DIR, entrada.base_model)
        if not os.path.isfile(candidato):
            raise HTTPException(status_code=400, detail=f"Modelo base nao encontrado: {entrada.base_model}")
        base_model_path = candidato

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
    return {"status": state.treino_status, "erro": state.treino_erro}


@router.get("/experimentos")
def listar_experimentos():
    base = settings.TRAINING_PROJECT
    experimentos = []
    if os.path.isdir(base):
        for nome in sorted(os.listdir(base)):
            pasta = os.path.join(base, nome)
            if not os.path.isdir(pasta):
                continue
            experimentos.append(
                {
                    "nome": nome,
                    "tem_resultados": os.path.isfile(os.path.join(pasta, "results.csv")),
                    "tem_pesos": os.path.isfile(os.path.join(pasta, "weights", "best.pt")),
                }
            )
    return {"experimentos": experimentos}

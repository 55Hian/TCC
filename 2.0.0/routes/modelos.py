"""Lista e seleciona pesos fine-tunados que pertencem a 2.0.0."""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from config import DATA, MODELOS, TRAINED_MODELS, modelo_ativo
from services.monitoramento import monitor

router = APIRouter(prefix="/api/modelos", tags=["modelos"])


class ModeloEscolhido(BaseModel):
    nome: str


@router.get("")
def listar_modelos():
    return {"modelo_ativo": modelo_ativo(), "modelos": [
        {"nome": nome, "treinado": (TRAINED_MODELS / nome / "best.pt").is_file(),
         "em_uso": nome == modelo_ativo()} for nome in MODELOS
    ]}


@router.post("/ativar")
def ativar_modelo(entrada: ModeloEscolhido):
    if entrada.nome not in MODELOS:
        raise HTTPException(status_code=400, detail="Arquitetura desconhecida")
    if monitor.thread and monitor.thread.is_alive():
        raise HTTPException(status_code=409, detail="Pare o monitoramento antes de trocar o modelo")
    pesos = TRAINED_MODELS / entrada.nome / "best.pt"
    if not pesos.is_file():
        raise HTTPException(status_code=404, detail="Esse modelo ainda nao foi treinado")
    DATA.mkdir(parents=True, exist_ok=True)
    (DATA / "modelo_ativo.txt").write_text(entrada.nome, encoding="utf-8")
    return {"modelo_ativo": entrada.nome, "pesos": str(pesos)}

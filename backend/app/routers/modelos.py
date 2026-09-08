from pathlib import Path

from fastapi import APIRouter

from core.config import settings
from services.model_service import catalog

router = APIRouter(prefix="/api", tags=["modelos"])


@router.get("/modelos")
def listar_modelos():
    models = catalog()
    size = lambda path: round(Path(path).stat().st_size / 1024**2, 2) if Path(path).is_file() else 0
    return {
        "modelo_ativo": settings.MODELO_ATIVO,
        "modelos": models,
        "pretreinados": [
            dict(nome=Path(m["base_model"]).name, caminho=m["base_model"],
                 tamanho_mb=size(m["base_model"]), em_uso=m["em_uso"]) for m in models],
        "treinados": [
            dict(experimento=m["nome"], caminho=m["model_path"],
                 tamanho_mb=size(m["model_path"]), em_uso=m["em_uso"],
                 disponivel=Path(m["model_path"]).is_file()) for m in models],
    }

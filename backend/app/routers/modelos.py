"""Expõe o catálogo de modelos e a disponibilidade dos arquivos de pesos."""
from pathlib import Path

from fastapi import APIRouter

from core.config import settings
from services.model_service import listar_catalogo

router = APIRouter(prefix="/api", tags=["modelos"])


@router.get("/modelos")
def listar_modelos():
    modelos = listar_catalogo()
    return {
        "modelo_ativo": settings.MODELO_ATIVO,
        "modelos": modelos,
        "pretreinados": [
            dict(nome=Path(m["base_model"]).name, caminho=m["base_model"],
                 tamanho_mb=_tamanho_megabytes(m["base_model"]), em_uso=m["em_uso"]) for m in modelos],
        "treinados": [
            dict(experimento=m["nome"], caminho=m["model_path"],
                 tamanho_mb=_tamanho_megabytes(m["model_path"]), em_uso=m["em_uso"],
                 disponivel=Path(m["model_path"]).is_file()) for m in modelos],
    }


def _tamanho_megabytes(caminho):
    arquivo = Path(caminho)
    return round(arquivo.stat().st_size / 1024**2, 2) if arquivo.is_file() else 0

import os

from fastapi import APIRouter

from core.config import settings

router = APIRouter(prefix="/api", tags=["modelos"])


def _listar_pretreinados():
    modelos = []
    if os.path.isdir(settings.PRETRAINED_MODELS_DIR):
        for nome in sorted(os.listdir(settings.PRETRAINED_MODELS_DIR)):
            if not nome.endswith(".pt"):
                continue
            caminho = os.path.join(settings.PRETRAINED_MODELS_DIR, nome)
            modelos.append(
                {
                    "nome": nome,
                    "caminho": caminho,
                    "tamanho_mb": round(os.path.getsize(caminho) / (1024 * 1024), 2),
                    "em_uso": os.path.abspath(caminho) == os.path.abspath(settings.BASE_MODEL),
                }
            )
    return modelos


def _listar_treinados():
    treinados = []
    base = settings.TRAINING_PROJECT
    if os.path.isdir(base):
        for nome_exp in sorted(os.listdir(base)):
            pesos = os.path.join(base, nome_exp, "weights", "best.pt")
            if os.path.isfile(pesos):
                treinados.append(
                    {
                        "experimento": nome_exp,
                        "caminho": pesos,
                        "tamanho_mb": round(os.path.getsize(pesos) / (1024 * 1024), 2),
                        "em_uso": os.path.abspath(pesos) == os.path.abspath(settings.MODEL_PATH),
                    }
                )
    return treinados


@router.get("/modelos")
def listar_modelos():
    """Lista os 4 modelos-base (models/pretrained) e os modelos ja treinados (experiments/treinamentos)."""
    return {"pretreinados": _listar_pretreinados(), "treinados": _listar_treinados()}

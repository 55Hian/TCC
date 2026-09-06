import os
import subprocess
import sys
import threading

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel

from core.config import settings
from core.state import state
from capturar_frames import capturar_frames

router = APIRouter(prefix="/api/dataset", tags=["dataset"])

_thread_captura = None


class CapturaEntrada(BaseModel):
    intervalo: float = 2.0
    max_frames: int = 20


def _extensao_valida(nome):
    return nome.lower().endswith((".jpg", ".jpeg", ".png"))


@router.get("/imagens")
def listar_imagens():
    pasta = settings.RAW_FRAMES_DIR
    if not os.path.isdir(pasta):
        return {"imagens": []}

    imagens = []
    for nome in sorted(os.listdir(pasta)):
        if not _extensao_valida(nome):
            continue
        nome_base = os.path.splitext(nome)[0]
        anotado = os.path.isfile(os.path.join(settings.LABELME_ANNOTATIONS_DIR, f"{nome_base}.json"))
        imagens.append({"nome": nome, "anotado": anotado})
    return {"imagens": imagens}


@router.get("/imagens/{nome}")
def obter_imagem(nome: str):
    caminho = os.path.join(settings.RAW_FRAMES_DIR, os.path.basename(nome))
    if not os.path.isfile(caminho):
        raise HTTPException(status_code=404, detail="Imagem nao encontrada.")
    return FileResponse(caminho)


def _executar_captura(intervalo, max_frames):
    state.captura_status = "rodando"
    state.captura_erro = None
    try:
        total = capturar_frames(
            pasta_saida=settings.RAW_FRAMES_DIR,
            intervalo=intervalo,
            max_frames=max_frames,
            mostrar_janela=False,
        )
        state.captura_total = total
        state.captura_status = "concluido"
    except Exception as exc:
        state.captura_status = "erro"
        state.captura_erro = str(exc)


@router.post("/capturar")
def iniciar_captura(entrada: CapturaEntrada):
    global _thread_captura
    if _thread_captura is not None and _thread_captura.is_alive():
        raise HTTPException(status_code=409, detail="Ja existe uma captura em andamento.")

    _thread_captura = threading.Thread(
        target=_executar_captura,
        args=(entrada.intervalo, entrada.max_frames),
        daemon=True,
        name="captura-worker",
    )
    _thread_captura.start()
    return {"iniciado": True}


@router.get("/capturar/status")
def status_captura():
    return {"status": state.captura_status, "erro": state.captura_erro, "total": state.captura_total}


@router.post("/anotar")
def abrir_labelme():
    """Abre o LabelMe (janela desktop separada) apontando para as imagens capturadas."""
    os.makedirs(settings.LABELME_ANNOTATIONS_DIR, exist_ok=True)
    try:
        processo = subprocess.Popen(
            [sys.executable, "-m", "labelme", settings.RAW_FRAMES_DIR, "--output", settings.LABELME_ANNOTATIONS_DIR]
        )
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Falha ao abrir o LabelMe: {exc}")
    return {"iniciado": True, "pid": processo.pid}

import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

from fastapi import FastAPI
from pydantic import BaseModel


app = FastAPI()
eventos = []
BASE_DIR = Path(__file__).resolve().parent
SERVICES_DIR = BASE_DIR / "services"


class EventoEntrada(BaseModel):
    tipo: str
    produto: str
    quantidade: int = 1
    mao_id: int | None = None
    produto_id: int | None = None
    pontos_mao: list[int] | None = None
    metodo: str | None = None
    interpretacao: str | None = None

@app.get("/")
def ler_raiz():
    return {"mensagem": "Olá, Mundo!"}

@app.get("/capturar_frames_treinamento")
def capturar_frames_treinamento():
    subprocess.Popen([sys.executable, str(SERVICES_DIR / "captura_frames_treinamento.py")])
    return {"response": "Foi solicitado  o inicio da captura de frames para treinamento."}

@app.get("/iniciar_monitoramento")
def iniciar_monitoramento():
    subprocess.Popen([sys.executable, str(SERVICES_DIR / "iniciar_monitoramento.py")])
    return {"response": "Foi solicitado o inicio do monitoramento."}


@app.post("/api/eventos", status_code=201)
def criar_evento(evento: EventoEntrada):
    dados_evento = evento.model_dump(exclude_none=True)
    dados_evento["timestamp"] = datetime.now(timezone.utc).isoformat()
    eventos.append(dados_evento)
    print(f"[API] Evento recebido: {dados_evento['tipo']} -> {dados_evento['produto']}")
    return dados_evento
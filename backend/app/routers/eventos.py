from datetime import datetime, timezone

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from pydantic import BaseModel

import time
import worker
from services.shared_camera import camera
from core.state import state
from core.config import settings

router = APIRouter(prefix="/api", tags=["eventos"])
ws_router = APIRouter(tags=["eventos"])


class EventoEntrada(BaseModel):
    tipo: str
    produto: str
    quantidade: int = 1
    mao_id: int | None = None
    produto_id: int | None = None
    pontos_mao: list[int] | None = None
    metodo: str | None = None
    interpretacao: str | None = None


@router.get("/eventos")
def listar_eventos():
    return {"eventos": state.listar_eventos()}


@router.post("/eventos", status_code=201)
def criar_evento(evento: EventoEntrada):
    """Recebe um evento externo (compat. com o antigo API_ENDPOINT) e distribui via WebSocket."""
    payload = evento.model_dump(exclude_none=True)
    payload["timestamp"] = datetime.now(timezone.utc).isoformat()
    state.adicionar_evento(payload)
    return payload


@router.get("/monitoramento/status")
def status_monitoramento():
    age = None if state.ultimo_processamento is None else time.monotonic() - state.ultimo_processamento
    return {"status": state.monitor_status, "erro": state.monitor_erro,
            "camera": camera.status(), "idade_processamento_segundos": age,
            "modelo_configurado": settings.MODELO_ATIVO,
            "modelo_carregado": state.monitor_modelo, "pesos_carregados": state.monitor_pesos}


@router.post("/monitoramento/iniciar")
def iniciar_monitoramento():
    iniciado = worker.iniciar()
    return {"iniciado": iniciado, "status": state.monitor_status}


@router.post("/monitoramento/parar")
def parar_monitoramento():
    parado = worker.parar()
    return {"parado": parado, "status": state.monitor_status}


@ws_router.websocket("/ws/eventos")
async def ws_eventos(websocket: WebSocket):
    await websocket.accept()
    state.ws_clients.add(websocket)
    try:
        while True:
            # mantem a conexao viva; o cliente nao precisa enviar nada
            await websocket.receive_text()
    except WebSocketDisconnect:
        pass
    finally:
        state.ws_clients.discard(websocket)

from datetime import datetime, timezone

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from pydantic import BaseModel

import worker
from core.state import state

router = APIRouter(prefix="/api", tags=["eventos"])
ws_router = APIRouter(tags=["eventos"])


class EventoEntrada(BaseModel):
    tipo: str
    produto: str
    quantidade: int = 1


@router.get("/eventos")
def listar_eventos():
    return {"eventos": state.listar_eventos()}


@router.post("/eventos", status_code=201)
def criar_evento(evento: EventoEntrada):
    """Recebe um evento externo (compat. com o antigo API_ENDPOINT) e distribui via WebSocket."""
    payload = evento.model_dump()
    payload["timestamp"] = datetime.now(timezone.utc).isoformat()
    state.adicionar_evento(payload)
    return payload


@router.get("/monitoramento/status")
def status_monitoramento():
    return {"status": state.monitor_status, "erro": state.monitor_erro}


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

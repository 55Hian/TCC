"""Entrypoint do backend FastAPI: expõe a API de monitoramento/treino/dataset.

Uso local (nao exposto publicamente - sem autenticacao):
    uvicorn main:app --reload --app-dir backend/app
"""
import asyncio
from contextlib import asynccontextmanager

from fastapi import FastAPI

from core.state import state
from routers import dataset, eventos, modelos, stream, treino


@asynccontextmanager
async def lifespan(app: FastAPI):
    state.registrar_loop(asyncio.get_running_loop())
    yield


app = FastAPI(title="Controle Autonomo de Inventario - API", lifespan=lifespan)

app.include_router(eventos.router)
app.include_router(eventos.ws_router)
app.include_router(stream.router)
app.include_router(modelos.router)
app.include_router(treino.router)
app.include_router(dataset.router)


@app.get("/api/health")
def health():
    return {"status": "ok"}

"""Entrypoint do backend FastAPI: expõe a API de monitoramento/treino/dataset.

Uso local (nao exposto publicamente - sem autenticacao):
    uvicorn main:app --reload --app-dir backend/app
"""
import asyncio
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from core.config import BASE_DIR, settings
from core.state import state
from services.shared_camera import camera
import worker
from routers import dataset, eventos, modelos, stream, treino


@asynccontextmanager
async def lifespan(app: FastAPI):
    state.registrar_loop(asyncio.get_running_loop())
    try:
        yield
    finally:
        await asyncio.to_thread(worker.encerrar)
        await asyncio.to_thread(camera.close)
        state.main_loop = None


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


# graficos/resultados de treino (read-only) e o frontend estatico.
# mount() e resolvido por ultimo na tabela de rotas, entao nao conflita com /api e /ws acima.
app.mount("/static/experiments", StaticFiles(directory=settings.TRAINING_PROJECT, check_dir=False), name="experiments")
app.mount("/static/benchmarks", StaticFiles(directory=settings.BENCHMARKS_DIR, check_dir=False), name="benchmarks")

FRONTEND_DIR = BASE_DIR / "frontend"
if FRONTEND_DIR.is_dir():
    app.mount("/", StaticFiles(directory=str(FRONTEND_DIR), html=True), name="frontend")

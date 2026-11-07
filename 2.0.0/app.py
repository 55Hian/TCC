"""API completa da versao 2.0.0."""
from contextlib import asynccontextmanager
import logging
from threading import Event, Thread

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from config import ROOT
from routes import balanca, banco, camera_secundaria, dashboard, eventos, modelos, monitoramento, produtos, treinamento
from services.camera_secundaria import camera_secundaria as gravador_usb
from services.database import inicializar
from services.correlacao import executar_correlacao_periodica
from services.monitoramento import monitor

logger = logging.getLogger(__name__)


@asynccontextmanager
async def ciclo_api(app):
    logger.info("Iniciando API e verificando esquema do banco")
    try:
        inicializar()
    except Exception:
        logger.exception("Falha ao inicializar o banco; API nao iniciada")
        raise
    parar_correlacao = Event()
    tarefa_correlacao = Thread(
        target=executar_correlacao_periodica, args=(parar_correlacao,),
        name="correlacao-retirada", daemon=True,
    )
    tarefa_correlacao.start()
    try:
        try:
            gravador_usb.iniciar()
        except Exception:
            logger.exception("Nao foi possivel iniciar a camera secundaria")
        logger.info("API iniciada; correlacao em execucao")
        yield
    finally:
        logger.info("Encerrando workers da API")
        parar_correlacao.set()
        tarefa_correlacao.join(timeout=5)
        monitor.parar()
        gravador_usb.parar()


app = FastAPI(title="Controle de Inventario 2.0.0", version="2.0.0", lifespan=ciclo_api)
app.include_router(treinamento.router)
app.include_router(monitoramento.router)
app.include_router(modelos.router)
app.include_router(eventos.router)
app.include_router(dashboard.router)
app.include_router(balanca.router)
app.include_router(produtos.router)
app.include_router(banco.router)
app.include_router(camera_secundaria.router)


@app.get("/api/health")
def health():
    return {"status": "ok", "versao": "2.0.0"}


app.mount("/", StaticFiles(directory=str(ROOT / "web"), html=True), name="web")

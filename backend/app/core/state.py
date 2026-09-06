"""Estado em memoria compartilhado entre o worker de monitoramento e a API."""
import asyncio
import threading
from collections import deque


class AppState:
    def __init__(self, max_eventos=200):
        self._lock = threading.Lock()
        self._eventos = deque(maxlen=max_eventos)
        self.monitor_status = "parado"  # parado | rodando | erro
        self.monitor_erro = None
        self.treino_status = "ocioso"  # ocioso | rodando | concluido | erro
        self.treino_erro = None
        self.captura_status = "ocioso"  # ocioso | rodando | concluido | erro
        self.captura_erro = None
        self.captura_total = 0
        self.main_loop = None  # definido no startup do FastAPI, usado p/ broadcast a partir da thread do worker
        self.ws_clients = set()

    def registrar_loop(self, loop):
        self.main_loop = loop

    def adicionar_evento(self, evento):
        with self._lock:
            self._eventos.append(evento)
        if self.main_loop is not None:
            asyncio.run_coroutine_threadsafe(self._broadcast(evento), self.main_loop)

    def listar_eventos(self):
        with self._lock:
            return list(self._eventos)

    async def _broadcast(self, evento):
        mortos = []
        for ws in list(self.ws_clients):
            try:
                await ws.send_json(evento)
            except Exception:
                mortos.append(ws)
        for ws in mortos:
            self.ws_clients.discard(ws)


state = AppState()

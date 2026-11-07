"""Comando simples para executar o monitoramento sem a API."""
import time
from services.monitoramento import monitor

if __name__ == "__main__":
    monitor.iniciar()
    try:
        while monitor.thread and monitor.thread.is_alive():
            time.sleep(0.5)
    except KeyboardInterrupt:
        monitor.parar()

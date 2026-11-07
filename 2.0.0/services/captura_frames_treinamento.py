"""Comando simples para capturar frames para anotacao."""
from services.captura import capturar

if __name__ == "__main__":
    print(f"Frames capturados: {capturar(intervalo=2, quantidade=360)}")

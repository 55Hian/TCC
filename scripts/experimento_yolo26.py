"""Entrada de treinamento que segue MODELO_ATIVO, igual ao backend."""
import argparse
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend" / "app"))
from core.config import settings
from services.model_service import caminhos_modelo
from services.training_service import rodar_pipeline_treinamento


def main():
    argumentos = argparse.ArgumentParser(description=__doc__)
    argumentos.add_argument("--epochs", type=int, default=50)
    argumentos.add_argument("--imgsz", type=int, default=640)
    argumentos.add_argument("--check", action="store_true")
    opcoes = argumentos.parse_args()
    base, treinado = caminhos_modelo()
    if not base.is_file():
        argumentos.error(f"Modelo base ausente: {base}")
    if opcoes.check:
        print(f"Modelo: {settings.MODELO_ATIVO}; base: {base}; inferencia: {treinado}")
        return
    rodar_pipeline_treinamento(epochs=opcoes.epochs, imgsz=opcoes.imgsz)


if __name__ == "__main__":
    main()

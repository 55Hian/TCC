"""Entrada de treinamento que segue MODELO_ATIVO, igual ao backend."""
import argparse
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend" / "app"))
from core.config import settings
from services.model_service import model_paths
from services.training_service import rodar_pipeline_treinamento


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--epochs", type=int, default=50)
    parser.add_argument("--imgsz", type=int, default=640)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    base, trained = model_paths()
    if not base.is_file():
        parser.error(f"Modelo base ausente: {base}")
    if args.check:
        print(f"Modelo: {settings.MODELO_ATIVO}; base: {base}; inferencia: {trained}")
        return
    rodar_pipeline_treinamento(epochs=args.epochs, imgsz=args.imgsz)


if __name__ == "__main__":
    main()

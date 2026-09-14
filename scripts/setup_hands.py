"""Baixa o modelo oficial; nao altera pesos YOLO ou configuracoes."""
from pathlib import Path
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
URL = "https://storage.googleapis.com/mediapipe-models/hand_landmarker/hand_landmarker/float16/1/hand_landmarker.task"


def main():
    destino = ROOT / "models" / "hand_landmarker.task"
    if destino.is_file():
        print(f"Modelo existente: {destino}")
        return
    destino.parent.mkdir(parents=True, exist_ok=True)
    temporario = destino.with_suffix(".task.part")
    try:
        urllib.request.urlretrieve(URL, temporario)
        temporario.replace(destino)
    finally:
        temporario.unlink(missing_ok=True)
    print(f"Modelo salvo: {destino}")


if __name__ == "__main__":
    main()

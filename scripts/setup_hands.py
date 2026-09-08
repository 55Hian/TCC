"""Baixa o modelo oficial; nao altera pesos YOLO ou configuracoes."""
from pathlib import Path
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
URL = "https://storage.googleapis.com/mediapipe-models/hand_landmarker/hand_landmarker/float16/1/hand_landmarker.task"


def main():
    target = ROOT / "models" / "hand_landmarker.task"
    if target.is_file():
        print(f"Modelo existente: {target}")
        return
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = target.with_suffix(".task.part")
    try:
        urllib.request.urlretrieve(URL, temporary)
        temporary.replace(target)
    finally:
        temporary.unlink(missing_ok=True)
    print(f"Modelo salvo: {target}")


if __name__ == "__main__":
    main()

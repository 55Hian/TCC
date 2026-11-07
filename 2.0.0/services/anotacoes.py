"""Abre Labelme e transforma caixas JSON em rotulos YOLO."""
import json
import subprocess
import sys
from pathlib import Path

from config import ANNOTATIONS, CLASSES, RAW_FRAMES, YOLO_LABELS


def abrir_labelme():
    ANNOTATIONS.mkdir(parents=True, exist_ok=True)
    return subprocess.Popen([sys.executable, "-m", "labelme", str(RAW_FRAMES), "--output", str(ANNOTATIONS)])


def converter_anotacoes():
    YOLO_LABELS.mkdir(parents=True, exist_ok=True)
    arquivos = list(ANNOTATIONS.glob("*.json"))
    if not arquivos:
        raise FileNotFoundError("Nao ha anotacoes Labelme")
    convertidos = 0
    for caminho in arquivos:
        dado = json.loads(caminho.read_text(encoding="utf-8"))
        largura, altura = dado.get("imageWidth", 0), dado.get("imageHeight", 0)
        if largura <= 0 or altura <= 0:
            raise ValueError(f"Dimensoes invalidas: {caminho.name}")
        linhas = []
        for shape in dado.get("shapes", []):
            if shape.get("label") not in CLASSES or len(shape.get("points", [])) < 2:
                continue
            (x1, y1), (x2, y2) = shape["points"][:2]
            cid = CLASSES.index(shape["label"])
            linhas.append(f"{cid} {(x1+x2)/2/largura:.6f} {(y1+y2)/2/altura:.6f} {abs(x2-x1)/largura:.6f} {abs(y2-y1)/altura:.6f}")
        (YOLO_LABELS / f"{caminho.stem}.txt").write_text("\n".join(linhas), encoding="utf-8")
        convertidos += 1
    return convertidos

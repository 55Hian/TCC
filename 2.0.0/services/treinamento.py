"""Prepara os dados e publica o melhor peso do treino concluido."""
import random
import shutil
from pathlib import Path

import yaml
from ultralytics import YOLO

from config import CLASSES, DATA, RAW_FRAMES, YOLO_LABELS, modelo_ativo
from services.anotacoes import converter_anotacoes


def preparar_dataset():
    converter_anotacoes()
    imagens = [p for p in RAW_FRAMES.iterdir() if p.suffix.lower() in (".jpg", ".jpeg", ".png")]
    pares = [p for p in imagens if (YOLO_LABELS / f"{p.stem}.txt").is_file()]
    if len(pares) < 2:
        raise ValueError("Anote pelo menos duas imagens para separar treino e validacao")
    random.Random(42).shuffle(pares)
    corte = max(1, min(len(pares) - 1, int(len(pares) * 0.8)))
    destino = DATA / "dataset"
    for parte, grupo in (("train", pares[:corte]), ("val", pares[corte:])):
        for tipo in ("images", "labels"):
            pasta = destino / tipo / parte
            pasta.mkdir(parents=True, exist_ok=True)
            for antigo in pasta.iterdir():
                antigo.unlink()
        for imagem in grupo:
            shutil.copy2(imagem, destino / "images" / parte / imagem.name)
            rotulo = YOLO_LABELS / f"{imagem.stem}.txt"
            shutil.copy2(rotulo, destino / "labels" / parte / rotulo.name)
    caminho_yaml = destino / "data.yaml"
    conteudo = {"path": str(destino), "train": "images/train", "val": "images/val", "names": CLASSES}
    caminho_yaml.write_text(yaml.safe_dump(conteudo, sort_keys=False), encoding="utf-8")
    return caminho_yaml


def treinar(epochs=50, imgsz=640):
    nome = modelo_ativo()
    data_yaml = preparar_dataset()
    base = Path(__file__).resolve().parents[1] / "models" / "pretrained" / f"{nome}.pt"
    if not base.is_file():
        raise FileNotFoundError(f"Peso base ausente: {base}")
    modelo = YOLO(str(base))
    modelo.train(data=str(data_yaml), epochs=epochs, imgsz=imgsz,
                 project=str(DATA / "treinos"), name=nome)
    experimento = Path(modelo.trainer.save_dir)
    melhor = experimento / "weights" / "best.pt"
    if not melhor.is_file() or melhor.stat().st_size == 0:
        raise RuntimeError("O treino terminou sem gerar best.pt")
    destino = Path(__file__).resolve().parents[1] / "models" / "trained" / nome / "best.pt"
    destino.parent.mkdir(parents=True, exist_ok=True)
    temporario = destino.with_suffix(".pt.tmp")
    shutil.copy2(melhor, temporario)
    temporario.replace(destino)
    return {"modelo": nome, "pesos": str(destino), "experimento": str(experimento)}


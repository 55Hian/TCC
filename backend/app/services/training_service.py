import os
import random
import shutil
from pathlib import Path
from uuid import uuid4

import torch
from ultralytics import YOLO

from services.annotation_converter import converter_labelme_para_yolo
from core.config import settings
from services.model_service import publish_weights


def _resolve_device():
    if torch.cuda.is_available():
        return 0, torch.cuda.get_device_name(0)
    return "cpu", "CPU"


def _train_dataset(data, base_model, epochs, imgsz, fraction):
    name = settings.MODELO_ATIVO
    device, device_name = _resolve_device()
    print(f"[TREINO] Modelo: {name}; dispositivo: {device_name}")
    model = YOLO(base_model)
    model.train(data=data, epochs=epochs, imgsz=imgsz, fraction=fraction,
                project=str(Path(settings.TRAINING_PROJECT).resolve()),
                name=f"{name}_{uuid4().hex[:12]}", device=device)
    best = Path(model.trainer.save_dir) / "weights" / "best.pt"
    # Apenas um treino concluido com pesos validos substitui a copia de inferencia.
    published = publish_weights(best, name)
    return dict(modelo=name, experimento=str(model.trainer.save_dir), pesos=published)


def rodar_pipeline_treinamento(
    pasta_fotos=None,
    pasta_json=None,
    pasta_yolo=None,
    pasta_dataset=None,
    base_model=None,
    epochs=50,
    imgsz=640,
    fraction=1.0,
):
    pasta_fotos = pasta_fotos or settings.RAW_FRAMES_DIR
    pasta_json = pasta_json or settings.LABELME_ANNOTATIONS_DIR
    pasta_yolo = pasta_yolo or settings.YOLO_LABELS_DIR
    pasta_dataset = pasta_dataset or settings.DATASET_DIR
    base_model = base_model or settings.BASE_MODEL
    if Path(base_model).resolve() != Path(settings.BASE_MODEL).resolve():
        raise ValueError("O treino deve usar MODELO_ATIVO; altere config.py e reinicie.")
    if not Path(base_model).is_file():
        raise FileNotFoundError(f"Modelo base ausente: {base_model}")

    if settings.USE_EXTERNAL_VALIDATION_DATASET:
        return _train_dataset(settings.EXTERNAL_VALIDATION_DATASET_YAML, base_model, epochs, imgsz, fraction)

    os.makedirs(pasta_json, exist_ok=True)
    os.makedirs(pasta_yolo, exist_ok=True)
    if not os.listdir(pasta_json):
        raise FileNotFoundError(
            f"Nenhum JSON do LabelMe foi encontrado em '{pasta_json}'."
        )

    converter_labelme_para_yolo(pasta_json, pasta_yolo, settings.CLASSES)
    for split in ("train", "val"):
        os.makedirs(os.path.join(pasta_dataset, "images", split), exist_ok=True)
        os.makedirs(os.path.join(pasta_dataset, "labels", split), exist_ok=True)

    imagens = [
        nome for nome in os.listdir(pasta_fotos)
        if nome.lower().endswith((".jpg", ".jpeg", ".png"))
    ]
    validos = [
        img for img in imagens
        if os.path.exists(
            os.path.join(pasta_yolo, f"{os.path.splitext(img)[0]}.txt")
        )
    ]
    if not validos:
        raise FileNotFoundError(
            f"Nenhuma imagem convertida foi encontrada em '{pasta_yolo}'."
        )

    random.seed(42)
    random.shuffle(validos)
    corte = int(len(validos) * 0.8)
    conjuntos = {"train": validos[:corte], "val": validos[corte:]}
    for split, arquivos in conjuntos.items():
        for imagem in arquivos:
            nome_base = os.path.splitext(imagem)[0]
            shutil.copy(
                os.path.join(pasta_fotos, imagem),
                os.path.join(pasta_dataset, "images", split, imagem),
            )
            shutil.copy(
                os.path.join(pasta_yolo, f"{nome_base}.txt"),
                os.path.join(pasta_dataset, "labels", split, f"{nome_base}.txt"),
            )

    caminho_yaml = os.path.join(pasta_dataset, "data.yaml")
    with open(caminho_yaml, "w", encoding="utf-8") as arquivo:
        arquivo.write(f"path: {os.path.abspath(pasta_dataset).replace(chr(92), '/') }\n")
        arquivo.write("train: images/train\n")
        arquivo.write("val: images/val\n")
        arquivo.write(f"names: {settings.CLASSES}\n")

    return _train_dataset(caminho_yaml, base_model, epochs, imgsz, fraction)

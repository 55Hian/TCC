import os
import random
import shutil

import torch
from ultralytics import YOLO

from services.annotation_converter import converter_labelme_para_yolo
from core.config import settings


def _resolve_device():
    if torch.cuda.is_available():
        return 0, torch.cuda.get_device_name(0)
    return "cpu", "CPU"


def _treinar_com_dataset_externo(epochs=50, imgsz=640, fraction=1.0):
    print(f"[TREINO] Dataset externo: {settings.EXTERNAL_VALIDATION_DATASET_YAML}")
    dispositivo, nome_dispositivo = _resolve_device()
    print(f"[TREINO] Iniciando {settings.BASE_MODEL} em: {nome_dispositivo}")
    modelo = YOLO(settings.BASE_MODEL)
    modelo.train(
        data=settings.EXTERNAL_VALIDATION_DATASET_YAML,
        epochs=epochs,
        imgsz=imgsz,
        fraction=fraction,
        project=os.path.abspath(settings.TRAINING_PROJECT),
        name=settings.TRAINING_NAME,
        device=dispositivo,
    )


def rodar_pipeline_treinamento(
    pasta_fotos=None,
    pasta_json=None,
    pasta_yolo=None,
    pasta_dataset=None,
    epochs=50,
    imgsz=640,
    fraction=1.0,
):
    pasta_fotos = pasta_fotos or settings.RAW_FRAMES_DIR
    pasta_json = pasta_json or settings.LABELME_ANNOTATIONS_DIR
    pasta_yolo = pasta_yolo or settings.YOLO_LABELS_DIR
    pasta_dataset = pasta_dataset or settings.DATASET_DIR

    if settings.USE_EXTERNAL_VALIDATION_DATASET:
        _treinar_com_dataset_externo(epochs=epochs, imgsz=imgsz, fraction=fraction)
        return

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

    dispositivo, nome_dispositivo = _resolve_device()
    print(f"[TREINO] Iniciando {settings.BASE_MODEL} em: {nome_dispositivo}")
    modelo = YOLO(settings.BASE_MODEL)
    modelo.train(
        data=caminho_yaml,
        epochs=epochs,
        imgsz=imgsz,
        project=os.path.abspath(settings.TRAINING_PROJECT),
        name=settings.TRAINING_NAME,
        device=dispositivo,
    )

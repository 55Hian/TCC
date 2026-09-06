import os
import random
import shutil

import torch
from ultralytics import YOLO

from services.annotation_converter import converter_labelme_para_yolo
from utils.config import (
    BASE_MODEL,
    CLASSES,
    DATASET_DIR,
    EXTERNAL_VALIDATION_DATASET_YAML,
    TRAINING_NAME,
    TRAINING_PROJECT,
    USE_EXTERNAL_VALIDATION_DATASET,
)


def _resolve_device():
    if torch.cuda.is_available():
        return 0, torch.cuda.get_device_name(0)
    return "cpu", "CPU"


def _treinar_com_dataset_externo(epochs=50, imgsz=640, fraction=1.0):
    print(f"[TREINO] Dataset externo: {EXTERNAL_VALIDATION_DATASET_YAML}")
    dispositivo, nome_dispositivo = _resolve_device()
    print(f"[TREINO] Iniciando {BASE_MODEL} em: {nome_dispositivo}")
    modelo = YOLO(BASE_MODEL)
    modelo.train(
        data=EXTERNAL_VALIDATION_DATASET_YAML,
        epochs=epochs,
        imgsz=imgsz,
        fraction=fraction,
        project=os.path.abspath(TRAINING_PROJECT),
        name=TRAINING_NAME,
        device=dispositivo,
    )


def rodar_pipeline_treinamento(
    pasta_fotos="dataset_fotos",
    pasta_json="dataset_labels",
    pasta_yolo="labels_yolo",
    pasta_dataset=DATASET_DIR,
    epochs=50,
    imgsz=640,
    fraction=1.0,
):
    if USE_EXTERNAL_VALIDATION_DATASET:
        _treinar_com_dataset_externo(epochs=epochs, imgsz=imgsz, fraction=fraction)
        return

    os.makedirs(pasta_json, exist_ok=True)
    os.makedirs(pasta_yolo, exist_ok=True)
    if not os.listdir(pasta_json):
        raise FileNotFoundError(
            "Nenhum JSON do LabelMe foi encontrado em 'dataset_labels'."
        )

    converter_labelme_para_yolo(pasta_json, pasta_yolo, CLASSES)
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
            "Nenhuma imagem convertida foi encontrada em 'labels_yolo'."
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
        arquivo.write(f"names: {CLASSES}\n")

    dispositivo, nome_dispositivo = _resolve_device()
    print(f"[TREINO] Iniciando {BASE_MODEL} em: {nome_dispositivo}")
    modelo = YOLO(BASE_MODEL)
    modelo.train(
        data=caminho_yaml,
        epochs=epochs,
        imgsz=imgsz,
        project=os.path.abspath(TRAINING_PROJECT),
        name=TRAINING_NAME,
        device=dispositivo,
    )

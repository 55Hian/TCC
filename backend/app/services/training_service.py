"""Prepara o dataset, executa o treino e publica apenas pesos concluídos e válidos."""
import os
import random
import shutil
from pathlib import Path
from uuid import uuid4

import torch
from ultralytics import YOLO

from services.annotation_converter import converter_labelme_para_yolo
from core.config import settings
from services.model_service import publicar_pesos


def _resolver_dispositivo():
    if torch.cuda.is_available():
        return 0, torch.cuda.get_device_name(0)
    return "cpu", "CPU"


def _treinar_dataset(dados, base_model, epochs, imgsz, fraction):
    nome = settings.MODELO_ATIVO
    dispositivo, nome_dispositivo = _resolver_dispositivo()
    print(f"[TREINO] Modelo: {nome}; dispositivo: {nome_dispositivo}")
    modelo = YOLO(base_model)
    modelo.train(data=dados, epochs=epochs, imgsz=imgsz, fraction=fraction,
                project=str(Path(settings.TRAINING_PROJECT).resolve()),
                name=f"{nome}_{uuid4().hex[:12]}", device=dispositivo)
    melhores_pesos = Path(modelo.trainer.save_dir) / "weights" / "best.pt"
    # Apenas um treino concluido com pesos validos substitui a copia de inferencia.
    publicado = publicar_pesos(melhores_pesos, nome)
    return dict(modelo=nome, experimento=str(modelo.trainer.save_dir), pesos=publicado)


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
        return _treinar_dataset(settings.EXTERNAL_VALIDATION_DATASET_YAML, base_model, epochs, imgsz, fraction)

    caminho_yaml = _preparar_dataset(pasta_fotos, pasta_json, pasta_yolo, pasta_dataset)
    return _treinar_dataset(caminho_yaml, base_model, epochs, imgsz, fraction)


def _preparar_dataset(pasta_fotos, pasta_json, pasta_yolo, pasta_dataset):
    """Converte, separa os pares imagem/rótulo e grava o YAML para o treino."""
    os.makedirs(pasta_json, exist_ok=True)
    os.makedirs(pasta_yolo, exist_ok=True)
    if not os.listdir(pasta_json):
        raise FileNotFoundError(
            f"Nenhum JSON do LabelMe foi encontrado em '{pasta_json}'."
        )

    converter_labelme_para_yolo(pasta_json, pasta_yolo, settings.CLASSES)
    for particao in ("train", "val"):
        os.makedirs(os.path.join(pasta_dataset, "images", particao), exist_ok=True)
        os.makedirs(os.path.join(pasta_dataset, "labels", particao), exist_ok=True)

    imagens = [
        nome for nome in os.listdir(pasta_fotos)
        if nome.lower().endswith((".jpg", ".jpeg", ".png"))
    ]
    validos = [
        imagem for imagem in imagens
        if os.path.exists(
            os.path.join(pasta_yolo, f"{os.path.splitext(imagem)[0]}.txt")
        )
    ]
    if not validos:
        raise FileNotFoundError(
            f"Nenhuma imagem convertida foi encontrada em '{pasta_yolo}'."
        )

    # A semente local mantém a divisão sem afetar o gerador aleatório do processo.
    random.Random(42).shuffle(validos)
    corte = int(len(validos) * 0.8)
    conjuntos = {"train": validos[:corte], "val": validos[corte:]}
    _copiar_conjuntos(conjuntos, pasta_fotos, pasta_yolo, pasta_dataset)

    caminho_yaml = os.path.join(pasta_dataset, "data.yaml")
    with open(caminho_yaml, "w", encoding="utf-8") as arquivo:
        arquivo.write(f"path: {os.path.abspath(pasta_dataset).replace(chr(92), '/') }\n")
        arquivo.write("train: images/train\n")
        arquivo.write("val: images/val\n")
        arquivo.write(f"names: {settings.CLASSES}\n")

    return caminho_yaml


def _copiar_conjuntos(conjuntos, pasta_fotos, pasta_yolo, pasta_dataset):
    """Copia cada imagem junto com seu rótulo para a mesma partição."""
    for particao, arquivos in conjuntos.items():
        for imagem in arquivos:
            nome_base = os.path.splitext(imagem)[0]
            shutil.copy(
                os.path.join(pasta_fotos, imagem),
                os.path.join(pasta_dataset, "images", particao, imagem),
            )
            shutil.copy(
                os.path.join(pasta_yolo, f"{nome_base}.txt"),
                os.path.join(pasta_dataset, "labels", particao, f"{nome_base}.txt"),
            )



# Compatibilidade de importação com os nomes anteriores.
_resolve_device = _resolver_dispositivo
def _train_dataset(data, base_model, epochs, imgsz, fraction):
    """Aceita os parâmetros nomeados da interface anterior."""
    return _treinar_dataset(data, base_model, epochs, imgsz, fraction)

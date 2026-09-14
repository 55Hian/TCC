"""Catalogo unico e publicacao atomica dos pesos de cada arquitetura."""
import hashlib
import os
from pathlib import Path
import shutil
import tempfile

from ultralytics import YOLO

from core.config import settings, MODELOS


def caminhos_modelo(nome=None):
    nome = nome or settings.MODELO_ATIVO
    if nome not in MODELOS:
        raise ValueError(f"Modelo desconhecido: {nome}")
    return (Path(settings.PRETRAINED_MODELS_DIR) / f"{nome}.pt",
            Path(settings.TRAINED_MODELS_DIR) / nome / "best.pt")


def validar_pesos(caminho, nome, classes_esperadas=None):
    caminho = Path(caminho)
    if not caminho.is_file():
        raise FileNotFoundError(f"Pesos ausentes: {caminho}")
    modelo = YOLO(str(caminho))
    nomes = dict(modelo.names)
    esperados = (settings.EXTERNAL_CLASSES if settings.USE_EXTERNAL_VALIDATION_DATASET else settings.CLASSES) if classes_esperadas is None else classes_esperadas
    if nomes != dict(enumerate(esperados)):
        raise ValueError(f"Classes incompativeis em {caminho}: {nomes}; esperado {esperados}")
    origem_modelo = Path(str(modelo.ckpt.get("train_args", {}).get("model", "")).replace("\\", "/")).stem
    if origem_modelo != nome:
        raise ValueError(f"Arquitetura de origem {origem_modelo!r} diferente de {nome!r}: {caminho}")
    return modelo


def publicar_pesos(origem, nome):
    """Valida antes de substituir; treino interrompido nunca substitui o modelo ativo."""
    origem = Path(origem)
    validar_pesos(origem, nome)
    _, destino = caminhos_modelo(nome)
    destino.parent.mkdir(parents=True, exist_ok=True)
    descritor, temporario = tempfile.mkstemp(prefix="best_", suffix=".pt", dir=destino.parent)
    os.close(descritor)
    temporario = Path(temporario)
    try:
        shutil.copyfile(origem, temporario)
        if _resumo_arquivo(origem) != _resumo_arquivo(temporario):
            raise RuntimeError("Falha na verificacao da copia dos pesos.")
        temporario.replace(destino)
    finally:
        temporario.unlink(missing_ok=True)
    return str(destino)


def listar_catalogo():
    resultado = []
    for nome in MODELOS:
        base, treinado = caminhos_modelo(nome)
        resultado.append(dict(nome=nome, base_model=str(base), model_path=str(treinado),
                           disponivel=base.is_file() and treinado.is_file(),
                           em_uso=nome == settings.MODELO_ATIVO))
    return resultado


def _resumo_arquivo(caminho):
    """Compara o conteúdo integral antes da substituição dos pesos publicados."""
    return hashlib.sha256(caminho.read_bytes()).hexdigest()


# Compatibilidade de importação com os nomes anteriores.
catalog = listar_catalogo
def model_paths(name=None):
    """Aceita os parâmetros nomeados da interface anterior."""
    return caminhos_modelo(name)
def publish_weights(source, name):
    """Aceita os parâmetros nomeados da interface anterior."""
    return publicar_pesos(source, name)
def validate_weights(path, name, expected_classes=None):
    """Aceita os parâmetros nomeados da interface anterior."""
    return validar_pesos(path, name, expected_classes)

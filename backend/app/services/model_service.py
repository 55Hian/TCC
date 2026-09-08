"""Catalogo unico e publicacao atomica dos pesos de cada arquitetura."""
import hashlib
import os
from pathlib import Path
import shutil
import tempfile

from ultralytics import YOLO

from core.config import settings, MODELOS


def model_paths(name=None):
    name = name or settings.MODELO_ATIVO
    if name not in MODELOS:
        raise ValueError(f"Modelo desconhecido: {name}")
    return (Path(settings.PRETRAINED_MODELS_DIR) / f"{name}.pt",
            Path(settings.TRAINED_MODELS_DIR) / name / "best.pt")


def validate_weights(path, name, expected_classes=None):
    path = Path(path)
    if not path.is_file():
        raise FileNotFoundError(f"Pesos ausentes: {path}")
    model = YOLO(str(path))
    names = dict(model.names)
    expected = (settings.EXTERNAL_CLASSES if settings.USE_EXTERNAL_VALIDATION_DATASET else settings.CLASSES) if expected_classes is None else expected_classes
    if names != dict(enumerate(expected)):
        raise ValueError(f"Classes incompativeis em {path}: {names}; esperado {expected}")
    origin = Path(str(model.ckpt.get("train_args", {}).get("model", "")).replace("\\", "/")).stem
    if origin != name:
        raise ValueError(f"Arquitetura de origem {origin!r} diferente de {name!r}: {path}")
    return model


def publish_weights(source, name):
    """Valida antes de substituir; treino interrompido nunca substitui o modelo ativo."""
    source = Path(source)
    validate_weights(source, name)
    _, target = model_paths(name)
    target.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary = tempfile.mkstemp(prefix="best_", suffix=".pt", dir=target.parent)
    os.close(descriptor)
    temporary = Path(temporary)
    try:
        shutil.copyfile(source, temporary)
        digest = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()
        if digest(source) != digest(temporary):
            raise RuntimeError("Falha na verificacao da copia dos pesos.")
        temporary.replace(target)
    finally:
        temporary.unlink(missing_ok=True)
    return str(target)


def catalog():
    result = []
    for name in MODELOS:
        base, trained = model_paths(name)
        result.append(dict(nome=name, base_model=str(base), model_path=str(trained),
                           disponivel=base.is_file() and trained.is_file(),
                           em_uso=name == settings.MODELO_ATIVO))
    return result

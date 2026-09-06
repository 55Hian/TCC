"""Repara referencias quebradas apos separar imagens e anotacoes."""
import json
import os
import re
from pathlib import Path


def preparar_anotacoes(raw_dir, annotation_dir):
    raw = Path(raw_dir).resolve()
    annotations = Path(annotation_dir)
    changes = []
    for path in annotations.glob("*.json"):
        original = path.read_text(encoding="utf-8")
        data = json.loads(original)
        if data.get("imageData"):
            continue
        image_path = data.get("imagePath", "")
        if image_path and (path.parent / image_path).is_file():
            continue
        candidates = [p for p in raw.iterdir() if p.stem == path.stem
                      and p.suffix.lower() in (".jpg", ".jpeg", ".png") and p.is_file()]
        if len(candidates) != 1:
            raise ValueError(f"Imagem ausente ou ambigua para {path.name}")
        relative = Path(os.path.relpath(candidates[0], path.parent)).as_posix()
        replacement = json.dumps(relative, ensure_ascii=False)
        updated, count = re.subn(r'("imagePath"\s*:\s*)"(?:\\.|[^"\\])*"',
            lambda match: match[1] + replacement, original, count=1)
        if count != 1:
            raise ValueError(f"imagePath ausente em {path.name}")
        changes.append((path, updated))
    for path, updated in changes:
        temporary = path.with_suffix(".json.tmp")
        temporary.write_text(updated, encoding="utf-8")
        temporary.replace(path)
    return len(changes)

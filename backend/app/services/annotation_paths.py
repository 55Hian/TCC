"""Repara referencias quebradas apos separar imagens e anotacoes."""
import json
import os
import re
from pathlib import Path


def preparar_anotacoes(raw_dir, annotation_dir):
    imagens_originais = Path(raw_dir).resolve()
    anotacoes = Path(annotation_dir)
    alteracoes = []
    for caminho in anotacoes.glob("*.json"):
        original = caminho.read_text(encoding="utf-8")
        dados = json.loads(original)
        if dados.get("imageData"):
            continue
        caminho_imagem = dados.get("imagePath", "")
        if caminho_imagem and (caminho.parent / caminho_imagem).is_file():
            continue
        imagem = _encontrar_imagem(imagens_originais, caminho)
        relativo = Path(os.path.relpath(imagem, caminho.parent)).as_posix()
        substituicao = json.dumps(relativo, ensure_ascii=False)
        atualizado, quantidade = re.subn(r'("imagePath"\s*:\s*)"(?:\\.|[^"\\])*"',
            lambda match: match[1] + substituicao, original, count=1)
        if quantidade != 1:
            raise ValueError(f"imagePath ausente em {caminho.name}")
        alteracoes.append((caminho, atualizado))
    for caminho, atualizado in alteracoes:
        temporario = caminho.with_suffix(".json.tmp")
        temporario.write_text(atualizado, encoding="utf-8")
        temporario.replace(caminho)
    return len(alteracoes)


def _encontrar_imagem(imagens_originais, caminho):
    """Exige uma única imagem correspondente antes de permitir qualquer escrita."""
    candidatos = [p for p in imagens_originais.iterdir() if p.stem == caminho.stem
                  and p.suffix.lower() in (".jpg", ".jpeg", ".png") and p.is_file()]
    if len(candidatos) != 1:
        raise ValueError(f"Imagem ausente ou ambigua para {caminho.name}")
    return candidatos[0]

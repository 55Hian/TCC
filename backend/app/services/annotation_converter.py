"""Conversão histórica LabelMe para YOLO, com saída normalizada por imagem."""
import json
import os

from core.config import settings


def converter_arquivo_labelme(caminho_json, pasta_saida, classes=None):
    classes = classes or settings.CLASSES
    with open(caminho_json, "r", encoding="utf-8") as arquivo:
        dados = json.load(arquivo)

    largura_imagem = dados.get("imageWidth", 1)
    altura_imagem = dados.get("imageHeight", 1)
    if largura_imagem <= 0 or altura_imagem <= 0:
        raise ValueError(f"Dimensoes invalidas no arquivo LabelMe: {caminho_json}")

    linhas_yolo = _normalizar_formas(dados.get("shapes", []), largura_imagem, altura_imagem, classes)

    os.makedirs(pasta_saida, exist_ok=True)
    nome_base = os.path.splitext(os.path.basename(caminho_json))[0]
    caminho_saida = os.path.join(pasta_saida, f"{nome_base}.txt")
    with open(caminho_saida, "w", encoding="utf-8") as arquivo:
        arquivo.write("\n".join(linhas_yolo))
    return caminho_saida


def converter_labelme_para_yolo(json_dir, output_dir, classes=None):
    classes = classes or settings.CLASSES
    os.makedirs(output_dir, exist_ok=True)
    arquivos = [nome for nome in os.listdir(json_dir) if nome.lower().endswith(".json")]
    if not arquivos:
        raise FileNotFoundError("Nenhum arquivo JSON do LabelMe foi encontrado.")

    return [
        converter_arquivo_labelme(os.path.join(json_dir, nome), output_dir, classes)
        for nome in arquivos
    ]


def _normalizar_formas(formas, largura_imagem, altura_imagem, classes):
    """Mantém a regra histórica: os dois primeiros pontos definem a caixa."""
    linhas_yolo = []
    for forma in formas:
        rotulo = forma.get("label")
        if rotulo not in classes:
            continue
        pontos = forma.get("points", [])
        if len(pontos) < 2:
            continue

        x1, y1 = pontos[0]
        x2, y2 = pontos[1]
        id_classe = classes.index(rotulo)
        centro_x = ((x1 + x2) / 2) / largura_imagem
        centro_y = ((y1 + y2) / 2) / altura_imagem
        largura = abs(x2 - x1) / largura_imagem
        altura = abs(y2 - y1) / altura_imagem
        linhas_yolo.append(f"{id_classe} {centro_x:.6f} {centro_y:.6f} {largura:.6f} {altura:.6f}")
    return linhas_yolo


# Compatibilidade de importação com os nomes anteriores.
def labelme_json_to_yolo(json_path, output_dir, classes=None):
    """Aceita os parâmetros nomeados da interface anterior."""
    return converter_arquivo_labelme(json_path, output_dir, classes)

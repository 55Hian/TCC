import json
import os

from utils.config import CLASSES


def labelme_json_to_yolo(json_path, output_dir, classes=None):
    classes = classes or CLASSES
    with open(json_path, "r", encoding="utf-8") as handle:
        data = json.load(handle)

    image_width = data.get("imageWidth", 1)
    image_height = data.get("imageHeight", 1)
    if image_width <= 0 or image_height <= 0:
        raise ValueError(f"Dimensoes invalidas no arquivo LabelMe: {json_path}")

    txt_lines = []
    for shape in data.get("shapes", []):
        label = shape.get("label")
        if label not in classes:
            continue
        points = shape.get("points", [])
        if len(points) < 2:
            continue

        x1, y1 = points[0]
        x2, y2 = points[1]
        cls_id = classes.index(label)
        x_center = ((x1 + x2) / 2) / image_width
        y_center = ((y1 + y2) / 2) / image_height
        width = abs(x2 - x1) / image_width
        height = abs(y2 - y1) / image_height
        txt_lines.append(f"{cls_id} {x_center:.6f} {y_center:.6f} {width:.6f} {height:.6f}")

    os.makedirs(output_dir, exist_ok=True)
    nome_base = os.path.splitext(os.path.basename(json_path))[0]
    output_path = os.path.join(output_dir, f"{nome_base}.txt")
    with open(output_path, "w", encoding="utf-8") as handle:
        handle.write("\n".join(txt_lines))
    return output_path


def converter_labelme_para_yolo(json_dir, output_dir, classes=None):
    classes = classes or CLASSES
    os.makedirs(output_dir, exist_ok=True)
    arquivos = [nome for nome in os.listdir(json_dir) if nome.lower().endswith(".json")]
    if not arquivos:
        raise FileNotFoundError("Nenhum arquivo JSON do LabelMe foi encontrado.")

    return [
        labelme_json_to_yolo(os.path.join(json_dir, nome), output_dir, classes)
        for nome in arquivos
    ]

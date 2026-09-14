import json

import pytest
from services.annotation_paths import preparar_anotacoes


def test_repara_apenas_caminho_e_preserva_anotacoes(tmp_path):
    imagens_originais, labels = tmp_path / "raw", tmp_path / "labels"
    imagens_originais.mkdir(); labels.mkdir()
    (imagens_originais / "frame.jpg").write_bytes(b"jpeg")
    caminho = labels / "frame.json"
    original = {"imagePath": "frame.jpg", "imageData": None, "shapes": [{"label": "cha", "points": [[1, 2], [3, 4]]}]}
    caminho.write_text(json.dumps(original))
    assert preparar_anotacoes(imagens_originais, labels) == 1
    changed = json.loads(caminho.read_text())
    assert changed.pop("imagePath") == "../raw/frame.jpg"
    original.pop("imagePath")
    assert changed == original
    assert preparar_anotacoes(imagens_originais, labels) == 0


def test_imagem_ausente_nao_altera_json(tmp_path):
    imagens_originais, labels = tmp_path / "raw", tmp_path / "labels"
    imagens_originais.mkdir(); labels.mkdir()
    caminho = labels / "missing.json"
    original = '{"imagePath": "missing.jpg", "imageData": null}'
    caminho.write_text(original)
    with pytest.raises(ValueError, match="Imagem ausente"):
        preparar_anotacoes(imagens_originais, labels)
    assert caminho.read_text() == original

import json
import sys
from pathlib import Path

import pytest
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from services.annotation_paths import preparar_anotacoes


def test_repara_apenas_caminho_e_preserva_anotacoes(tmp_path):
    raw, labels = tmp_path / "raw", tmp_path / "labels"
    raw.mkdir(); labels.mkdir()
    (raw / "frame.jpg").write_bytes(b"jpeg")
    path = labels / "frame.json"
    original = {"imagePath": "frame.jpg", "imageData": None, "shapes": [{"label": "cha", "points": [[1, 2], [3, 4]]}]}
    path.write_text(json.dumps(original))
    assert preparar_anotacoes(raw, labels) == 1
    changed = json.loads(path.read_text())
    assert changed.pop("imagePath") == "../raw/frame.jpg"
    original.pop("imagePath")
    assert changed == original
    assert preparar_anotacoes(raw, labels) == 0


def test_imagem_ausente_nao_altera_json(tmp_path):
    raw, labels = tmp_path / "raw", tmp_path / "labels"
    raw.mkdir(); labels.mkdir()
    path = labels / "missing.json"
    original = '{"imagePath": "missing.jpg", "imageData": null}'
    path.write_text(original)
    with pytest.raises(ValueError, match="Imagem ausente"):
        preparar_anotacoes(raw, labels)
    assert path.read_text() == original

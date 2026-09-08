import sys
from pathlib import Path

import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from core.config import settings
from services.event_service import EventService, contact, gerar_eventos
from services.tracking_service import ObjectTracker


def box(classe, x=0, y=0, size=20, **extra):
    return dict(classe=classe, x_min=x, y_min=y, x_max=x+size, y_max=y+size, **extra)


def frame(*products, hands=1):
    return pd.DataFrame([box("mao") for _ in range(hands)] + list(products))


@pytest.fixture(autouse=True)
def thresholds(monkeypatch):
    for name, value in dict(
        INTERACTION_CONFIRM_SECONDS=0.3, INTERACTION_MIN_SAMPLES=3,
        INTERACTION_MAX_GAP_SECONDS=0.5, INTERACTION_RELEASE_SECONDS=0.6,
        INTERACTION_RESET_SECONDS=2.0, IOU_THRESHOLD=0.1, HAND_CONTACT_MARGIN=0.08,
    ).items():
        monkeypatch.setattr(settings, name, value)


def confirm(service, df, start=0):
    assert service.processar(df, start) == []
    assert service.processar(df, start + 0.15) == []
    return service.processar(df, start + 0.3)


def test_three_products_and_no_repeated_events():
    service = EventService()
    df = frame(box("cha"), box("gelatina"), box("creme_leite"))
    events = confirm(service, df)
    assert {e["produto"] for e in events} == {"cha", "gelatina", "creme_leite"}
    assert len({e["produto_id"] for e in events}) == 3
    assert service.processar(df, 0.45) == []
    assert service.processar(df, 0.6) == []
    assert len(gerar_eventos(df)) == 3


def test_passing_a_then_touching_b():
    service = EventService()
    assert service.processar(frame(box("cha")), 0) == []
    assert service.processar(frame(box("cha")), 0.1) == []
    df = frame(box("cha", x=100), box("gelatina"))
    events = confirm(service, df, start=0.2)
    assert [e["produto"] for e in events] == ["gelatina"]


def test_release_allows_new_interaction():
    service = EventService()
    df = frame(box("cha"))
    assert len(confirm(service, df)) == 1
    assert service.processar(pd.DataFrame(), 0.5) == []
    assert service.processar(df, 0.65) == []  # breve oclusao
    assert service.processar(pd.DataFrame(), 1.3) == []
    assert len(confirm(service, df, 1.4)) == 1


def test_missing_observations_do_not_count_as_contact():
    service = EventService()
    df = frame(box("cha"))
    assert service.processar(df, 0) == []
    assert service.processar(pd.DataFrame(), 0.1) == []
    assert service.processar(df, 0.3) == []
    assert service.processar(df, 0.45) == []
    assert len(service.processar(df, 0.6)) == 1


def test_slow_frames_and_camera_gap_do_not_confirm():
    service = EventService()
    df = frame(box("cha"))
    for timestamp in (0, 0.55, 1.1, 1.65):
        assert service.processar(df, timestamp) == []
    assert service.processar(df, 5) == []
    assert service.processar(df, 5.1) == []
    assert len(service.processar(df, 5.3)) == 1
    service.reset()
    assert service.processar(df, 6) == []


def test_reordered_same_class_objects_keep_separate_ids():
    tracker = ObjectTracker()
    first = tracker.update([box("cha", x=0), box("cha", x=100)], 0)
    second = tracker.update([box("cha", x=101), box("cha", x=1)], 0.1)
    assert first[0]["track_id"] == second[1]["track_id"]
    assert first[1]["track_id"] == second[0]["track_id"]


def test_two_hands_independent_pairs():
    service = EventService()
    events = confirm(service, frame(box("cha"), hands=2))
    assert len(events) == 2
    assert len({e["mao_id"] for e in events}) == 2
    assert len({e["produto_id"] for e in events}) == 1


def test_landmarks_reject_empty_part_of_hand_box():
    # A caixa cruza o produto, mas os pontos/segmentos ficam acima e a esquerda.
    points = [(0, 0)] * 21
    points[9] = (0, 10)
    points[8] = (100, 0)
    hand = box("mao", size=100, landmarks=points)
    product = box("cha", x=70, y=70)
    assert contact(hand, product) == (False, [], "landmarks")
    assert contact(box("mao", size=100), product)[2] == "iou"


def test_finger_tip_and_segment_contact():
    points = [(0, 0)] * 21
    points[9] = (0, 10)
    points[8] = (50, 0)
    hand = box("mao", landmarks=points)
    hit, nodes, method = contact(hand, box("cha", x=45, y=-5, size=10))
    assert hit and 8 in nodes and method == "landmarks"
    hit, nodes, _ = contact(hand, box("cha", x=20, y=-2, size=4))
    assert hit and nodes == []  # segmento cruza sem nenhum no dentro


def test_zero_area_and_no_overlap():
    assert not contact(box("mao", size=0), box("cha", size=0))[0]
    assert not contact(box("mao"), box("cha", x=100))[0]


def test_timestamp_rewind_starts_new_candidate():
    service = EventService()
    df = frame(box("cha"))
    assert len(confirm(service, df, 10)) == 1
    assert service.processar(df, 1) == []


def test_api_preserves_hand_metadata():
    from fastapi.testclient import TestClient
    from main import app
    payload = dict(tipo="interacao_mao", produto="cha", quantidade=1,
                   mao_id=1, produto_id=2, pontos_mao=[8], metodo="landmarks",
                   interpretacao="contato_provavel")
    with TestClient(app) as client:
        result = client.post("/api/eventos", json=payload)
        assert result.status_code == 201
        assert all(result.json()[key] == value for key, value in payload.items())

def test_joint_motion_is_manipulation_without_duplicate_event():
    service = EventService()
    events = []
    for index in range(3):
        df = pd.DataFrame([box("mao", x=index*3), box("cha", x=index*3)])
        events.extend(service.processar(df, index*0.15))
    assert len(events) == 1
    assert events[0]["interpretacao"] == "manipulacao_provavel"
    assert service.processar(pd.DataFrame([box("mao", x=9), box("cha", x=9)]), 0.45) == []


def test_hand_motion_alone_is_not_manipulation():
    service = EventService()
    for index in range(3):
        events = service.processar(pd.DataFrame([box("mao", x=index*3), box("cha")]), index*0.15)
    assert events[0]["interpretacao"] == "contato_provavel"


def test_vision_uses_same_timestamp_and_replaces_yolo_hand(monkeypatch):
    import numpy as np
    from services import vision_service as module

    class Box:
        xyxy = np.array([[0, 0, 20, 20]])
        conf = np.array([0.9])
        def __init__(self, cls):
            self.cls = np.array([cls])

    class Model:
        names = dict(enumerate(settings.CLASSES))

        def __call__(self, *args, **kwargs):
            return [type("Result", (), {"boxes": [Box(2), Box(3)]})()]

    calls = []
    class Hands:
        def processar_frame(self, frame, timestamp):
            calls.append(timestamp)
            return [box("mao", landmarks=[(0, 0)]*21)]
        def close(self):
            calls.append("closed")

    monkeypatch.setattr(settings, "HAND_LANDMARKS_ENABLED", True)
    monkeypatch.setattr(settings, "USE_EXTERNAL_VALIDATION_DATASET", False)
    monkeypatch.setattr(module, "YOLO", lambda *args: Model())
    monkeypatch.setattr(module, "HandService", Hands)
    vision = module.VisionService()
    result = vision.processar_frame(np.zeros((20,20,3), dtype=np.uint8), timestamp=1.25)
    assert result["classe"].tolist() == ["cha", "mao"]
    assert result.attrs["timestamp"] == 1.25
    assert calls == [1.25]
    vision.close()
    assert calls[-1] == "closed"

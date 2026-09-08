"""Interacoes provaveis por par mao-produto, com confirmacao temporal."""
from collections import deque
from math import hypot
import time

from core.config import settings
from services.hand_service import HAND_CONNECTIONS
from services.tracking_service import ObjectTracker, center, iou

calcular_area_intersecao = iou


def _segment_hits(a, b, box, margin):
    # Liang-Barsky: intersecao do segmento com o retangulo expandido.
    low, high = 0.0, 1.0
    dx, dy = b[0] - a[0], b[1] - a[1]
    for p, q in ((-dx, a[0] - box["x_min"] + margin),
                 (dx, box["x_max"] + margin - a[0]),
                 (-dy, a[1] - box["y_min"] + margin),
                 (dy, box["y_max"] + margin - a[1])):
        if p == 0:
            if q < 0:
                return False
        elif p < 0:
            low = max(low, q / p)
        else:
            high = min(high, q / p)
        if low > high:
            return False
    return True


def contact(hand, product, active=False):
    points = hand.get("landmarks")
    if isinstance(points, (list, tuple)) and len(points) == 21:
        scale = max(1.0, hypot(points[0][0] - points[9][0], points[0][1] - points[9][1]))
        margin = settings.HAND_CONTACT_MARGIN * scale * (1.5 if active else 1)
        nodes = [index for index, point in enumerate(points)
                 if _segment_hits(point, point, product, margin)]
        segments = [(a, b) for a, b in HAND_CONNECTIONS
                    if _segment_hits(points[a], points[b], product, margin)]
        palm = tuple(sum(points[i][axis] for i in (0, 5, 9, 13, 17)) / 5 for axis in (0, 1))
        palm_hit = _segment_hits(palm, palm, product, margin)
        return bool(nodes or segments or palm_hit), nodes, "landmarks"
    threshold = settings.IOU_THRESHOLD * (0.7 if active else 1)
    return iou(hand, product) >= threshold and iou(hand, product) > 0, [], "iou"


def gerar_eventos(df_atual):
    """Compatibilidade: candidatos de um frame, sem confirmacao temporal.

    Monitoramento e CLI usam EventService. Esta funcao nao deve publicar eventos.
    """
    records = df_atual.to_dict("records")
    return [dict(tipo="interacao_mao", produto=product["classe"], quantidade=1)
            for product in records if product["classe"] != "mao"
            if any(contact(hand, product)[0] for hand in records if hand["classe"] == "mao")]


def _interpretation(history, hand):
    if len(history) < 3:
        return "contato_provavel"
    _, first_hand, first_product = history[0]
    _, last_hand, last_product = history[-1]
    hand_vector = tuple(b - a for a, b in zip(first_hand, last_hand))
    product_vector = tuple(b - a for a, b in zip(first_product, last_product))
    hand_distance, product_distance = hypot(*hand_vector), hypot(*product_vector)
    scale = max(1.0, hypot(hand["x_max"] - hand["x_min"], hand["y_max"] - hand["y_min"]))
    minimum = max(3.0, settings.INTERACTION_MOTION_MIN_RATIO * scale)
    if min(hand_distance, product_distance) < minimum:
        return "contato_provavel"
    cosine = sum(a * b for a, b in zip(hand_vector, product_vector)) / (hand_distance * product_distance)
    ratio = min(hand_distance, product_distance) / max(hand_distance, product_distance)
    return "manipulacao_provavel" if cosine >= 0.8 and ratio >= 0.5 else "contato_provavel"


class EventService:
    def __init__(self):
        self.reset()

    def reset(self):
        self.tracker = ObjectTracker(settings.INTERACTION_RELEASE_SECONDS)
        self.pairs = {}
        self.last_timestamp = None
        self.detections = []
        self.diagnostics = []

    def processar(self, df_atual, timestamp=None):
        timestamp = time.monotonic() if timestamp is None else timestamp
        if self.last_timestamp is not None and (
                timestamp <= self.last_timestamp or
                timestamp - self.last_timestamp > settings.INTERACTION_RESET_SECONDS):
            self.reset()
        self.last_timestamp = timestamp
        self.detections = self.tracker.update(df_atual.to_dict("records"), timestamp)
        self.pairs = {key: value for key, value in self.pairs.items()
                      if timestamp - value["last_seen"] <= settings.INTERACTION_RELEASE_SECONDS}
        hands = [item for item in self.detections if item["classe"] == "mao"]
        products = [item for item in self.detections if item["classe"] != "mao"]
        events, seen = [], set()
        self.diagnostics = []
        for hand in hands:
            for product in products:
                key = (hand["track_id"], product["track_id"])
                previous = self.pairs.get(key)
                active = previous is not None and previous["confirmed"]
                hit, nodes, method = contact(hand, product, active)
                if not hit:
                    continue
                seen.add(key)
                if previous is None:
                    previous = dict(last_seen=timestamp, duration=0.0, samples=0, confirmed=False,
                                    consecutive=False, motion=deque(maxlen=120))
                    self.pairs[key] = previous
                delta = timestamp - previous["last_seen"]
                if not previous["confirmed"]:
                    if previous["consecutive"] and delta <= settings.INTERACTION_MAX_GAP_SECONDS:
                        previous["duration"] += delta
                    else:
                        previous["duration"] = 0.0
                        previous["samples"] = 0
                    previous["samples"] += 1
                if not previous["consecutive"] or delta > settings.INTERACTION_MAX_GAP_SECONDS:
                    previous["motion"].clear()
                previous["motion"].append((timestamp, center(hand), center(product)))
                while previous["motion"] and timestamp - previous["motion"][0][0] > 0.6:
                    previous["motion"].popleft()
                interpretation = _interpretation(previous["motion"], hand)
                previous["last_seen"] = timestamp
                previous["consecutive"] = True
                if (not previous["confirmed"]
                        and previous["duration"] + 1e-9 >= settings.INTERACTION_CONFIRM_SECONDS
                        and previous["samples"] >= settings.INTERACTION_MIN_SAMPLES):
                    previous["confirmed"] = True
                    events.append(dict(
                        tipo="interacao_mao", produto=product["classe"], quantidade=1,
                        mao_id=key[0], produto_id=key[1], pontos_mao=nodes,
                        metodo=method, interpretacao=interpretation,
                    ))
                self.diagnostics.append(dict(
                    mao_id=key[0], produto_id=key[1], pontos_mao=nodes,
                    interpretacao=interpretation,
                    estado="confirmada" if previous["confirmed"] else "candidata",
                ))
        for key, previous in self.pairs.items():
            if key not in seen:
                previous["consecutive"] = False
        return events

"""Associacao espacial de curto prazo, por classe, sem alterar o modelo YOLO."""
from math import hypot


def iou(a, b):
    intersection = max(0, min(a["x_max"], b["x_max"]) - max(a["x_min"], b["x_min"])) * max(
        0, min(a["y_max"], b["y_max"]) - max(a["y_min"], b["y_min"]))
    area = lambda box: max(0, box["x_max"] - box["x_min"]) * max(0, box["y_max"] - box["y_min"])
    union = area(a) + area(b) - intersection
    return intersection / union if union > 0 else 0.0


def center(box):
    return ((box["x_min"] + box["x_max"]) / 2, (box["y_min"] + box["y_max"]) / 2)


class ObjectTracker:
    """IDs locais a uma sessao; nao garante identidade apos oclusoes/cruzamentos."""
    def __init__(self, ttl=0.6):
        self.ttl = ttl
        self.tracks = {}
        self.next_id = 1

    def update(self, detections, timestamp):
        self.tracks = {key: value for key, value in self.tracks.items()
                       if timestamp - value[1] <= self.ttl}
        candidates = []
        for index, detection in enumerate(detections):
            for key, (old, _) in self.tracks.items():
                if old["classe"] != detection["classe"]:
                    continue
                overlap = iou(old, detection)
                scale = max(1, hypot(old["x_max"] - old["x_min"], old["y_max"] - old["y_min"]))
                distance = hypot(*(a - b for a, b in zip(center(old), center(detection)))) / scale
                if overlap >= 0.1 or distance <= 0.5:
                    candidates.append((overlap - distance, key, index))
        assigned, used = {}, set()
        for _, key, index in sorted(candidates, reverse=True):
            if index not in assigned and key not in used:
                assigned[index] = key
                used.add(key)
        result = []
        for index, detection in enumerate(detections):
            key = assigned.get(index)
            if key is None:
                key = self.next_id
                self.next_id += 1
            item = dict(detection, track_id=key)
            self.tracks[key] = (item, timestamp)
            result.append(item)
        return result

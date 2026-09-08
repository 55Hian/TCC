"""Visualizacao local das deteccoes e associacoes usadas na decisao."""
import cv2

from services.hand_service import HAND_CONNECTIONS


def draw_interactions(frame, events):
    output = frame.copy()
    confirmed = {item["produto_id"] for item in events.diagnostics if item["estado"] == "confirmada"}
    for item in events.detections:
        color = (0, 200, 0) if item["track_id"] in confirmed else (0, 200, 255)
        a = (int(item["x_min"]), int(item["y_min"]))
        b = (int(item["x_max"]), int(item["y_max"]))
        cv2.rectangle(output, a, b, color, 2)
        cv2.putText(output, f'{item["classe"]} #{item["track_id"]}', a,
                    cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 1)
        points = item.get("landmarks")
        if isinstance(points, (list, tuple)) and len(points) == 21:
            for start, end in HAND_CONNECTIONS:
                cv2.line(output, tuple(map(int, points[start])), tuple(map(int, points[end])), color, 1)
            for index, point in enumerate(points):
                position = tuple(map(int, point))
                cv2.circle(output, position, 3, (255, 0, 255), -1)
                cv2.putText(output, str(index), position, cv2.FONT_HERSHEY_SIMPLEX, 0.3, color, 1)
    for index, item in enumerate(events.diagnostics):
        cv2.putText(output, f'Mao {item["mao_id"]} -> produto {item["produto_id"]}: {item["estado"]} {item["interpretacao"]}',
                    (10, 20 + index * 20), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 255), 1)
    return output

"""Reproduz video local e exporta eventos para calibracao, sem publicar na API."""
import argparse
import json
import sys
import time
from pathlib import Path

import cv2

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend" / "app"))
from services.event_service import EventService
from services.interaction_overlay import draw_interactions
from services.vision_service import VisionService
from core.config import settings


def evaluate(events, expected):
    matched = set()
    true_positive = 0
    for event in events:
        for index, item in enumerate(expected):
            if (index not in matched and item["produto"] == event["produto"]
                    and item["inicio"] <= event["segundo"] <= item["fim"] + settings.INTERACTION_CONFIRM_SECONDS):
                matched.add(index)
                true_positive += 1
                break
    return dict(corretos=true_positive, falsos_ou_duplicados=len(events)-true_positive,
                perdidos=len(expected)-true_positive)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("video", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--weights")
    parser.add_argument("--device", help="cpu ou indice da GPU; padrao do YOLO quando omitido.")
    parser.add_argument("--iou-only", action="store_true", help="Desativa landmarks; mantem regra temporal.")
    parser.add_argument("--baseline", action="store_true", help="Regra original: primeiro produto por mao/frame.")
    parser.add_argument("--annotated-video", type=Path)
    parser.add_argument("--annotations", type=Path, help="JSON: lista de produto/inicio/fim em segundos.")
    args = parser.parse_args()
    # Saidas devem ser novas para evitar sobrescrever videos/anotacoes.
    for output in (args.output, args.annotated_video):
        if output is not None and output.exists():
            parser.error(f"Saida ja existe: {output}")
    settings.HAND_LANDMARKS_ENABLED = not (args.iou_only or args.baseline)
    capture = cv2.VideoCapture(str(args.video))
    vision, writer = None, None
    try:
        if not capture.isOpened():
            raise ValueError(f"Nao foi possivel abrir {args.video}")
        fps = capture.get(cv2.CAP_PROP_FPS)
        if fps <= 0:
            raise ValueError("Video sem FPS valido.")
        vision = VisionService(args.weights, device=args.device)
        service = EventService()
        events, frames = [], 0
        started = time.perf_counter()
        while True:
            ok, frame = capture.read()
            if not ok:
                break
            second = frames / fps
            detections = vision.processar_frame(frame, timestamp=second)
            if args.baseline:
                from services.event_service import calcular_area_intersecao
                records = detections.to_dict("records")
                current = []
                for hand in records:
                    if hand["classe"] != "mao":
                        continue
                    for product in records:
                        if product["classe"] != "mao" and calcular_area_intersecao(hand, product) >= settings.IOU_THRESHOLD:
                            current.append(dict(tipo="interacao_mao", produto=product["classe"], quantidade=1))
                            break
            else:
                current = service.processar(detections, second)
            events.extend(dict(event, segundo=second) for event in current)
            if args.annotated_video:
                if writer is None:
                    writer = cv2.VideoWriter(str(args.annotated_video), cv2.VideoWriter_fourcc(*"mp4v"),
                                             fps, (frame.shape[1], frame.shape[0]))
                    if not writer.isOpened():
                        raise RuntimeError("Falha ao criar video anotado.")
                writer.write(draw_interactions(frame, service))
            frames += 1
        elapsed = time.perf_counter() - started
        report = dict(video=str(args.video), frames=frames, fps_video=fps,
                      fps_processamento=frames / elapsed if elapsed else 0,
                      modo="baseline" if args.baseline else ("iou_temporal" if args.iou_only else "landmarks_temporal"),
                      parametros={key: value for key, value in settings.model_dump().items()
                                  if key.startswith(("INTERACTION_", "HAND_CONTACT_", "IOU_"))},
                      eventos=events)
        if args.annotations:
            report["avaliacao"] = evaluate(events, json.loads(args.annotations.read_text(encoding="utf-8")))
        args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"{frames} frames; {len(events)} eventos; {report['fps_processamento']:.1f} FPS. {args.output}")
    finally:
        capture.release()
        if writer is not None:
            writer.release()
        if vision is not None:
            vision.close()


if __name__ == "__main__":
    main()

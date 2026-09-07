"""Comparativo controlado: quatro modelos, dataset congelado e 50 epocas."""
import argparse
import csv
import hashlib
import json
import platform
import shutil
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MODELS = ['yolov8n', 'yolo12n', 'yolo26s', 'yolo26m']

def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def train_one(out, name):
    import torch
    from ultralytics import YOLO
    start = time.perf_counter()
    model = YOLO(str(ROOT / 'models/pretrained' / (name + '.pt')))
    model.train(data=str(out / 'dataset/data.yaml'), epochs=50, patience=0,
                imgsz=640, batch=2, workers=2, device=0, seed=0,
                deterministic=True, pretrained=True, fraction=1.0,
                optimizer='AdamW', lr0=0.00125, momentum=0.9,
                weight_decay=0.0005, nbs=64, amp=False, cache=False,
                close_mosaic=10, project=str(out), name=name, exist_ok=False)
    elapsed = time.perf_counter() - start
    del model
    torch.cuda.empty_cache()
    best = YOLO(str(out / name / 'weights/best.pt'))
    result = best.val(data=str(out / 'dataset/data.yaml'), imgsz=640,
                      batch=1, device=0, workers=2, quantize=32, rect=False,
                      conf=0.001, iou=0.7, max_det=300, augment=False,
                      project=str(out), name=name + '_validation', plots=True)
    rows = list(csv.DictReader((out / name / 'results.csv').open()))
    peak = max(rows, key=lambda r: float(r['metrics/mAP50-95(B)']))
    info = dict(model=name, epochs=len(rows), best_csv_epoch=int(peak['epoch']),
                precision=float(result.box.mp), recall=float(result.box.mr),
                map50=float(result.box.map50), map50_95=float(result.box.map),
                training_seconds=elapsed, csv_seconds=float(rows[-1]['time']),
                speed_ms=result.speed,
                classes={str(best.names[int(c)]):list(map(float,result.box.class_result(i)))
                         for i,c in enumerate(result.box.ap_class_index)},
                checkpoint_sha256=digest(out / name / 'weights/best.pt'))
    (out / (name + '_summary.json')).write_text(json.dumps(info, indent=2), encoding='utf-8')

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--out', type=Path, required=True)
    parser.add_argument('--model', choices=MODELS)
    args = parser.parse_args()
    out = args.out.resolve()
    if args.model:
        train_one(out, args.model)
        return
    import torch
    import ultralytics
    import yaml
    if not torch.cuda.is_available():
        raise RuntimeError('GPU CUDA indisponivel')
    out.mkdir(parents=True, exist_ok=False)
    source = ROOT / 'data/dataset'
    manifest = []
    hashes = {}
    for split in ['train', 'val']:
        hashes[split] = set()
        for image in sorted((source / 'images' / split).iterdir()):
            if image.suffix.lower() not in {'.jpg', '.jpeg', '.png', '.bmp', '.webp'}:
                continue
            label = source / 'labels' / split / (image.stem + '.txt')
            if not label.is_file():
                raise RuntimeError('Anotacao ausente: ' + str(label))
            hashes[split].add(digest(image))
            for file in [image, label]:
                relative = file.relative_to(source)
                dest = out / 'dataset' / relative
                dest.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(file, dest)
                if file.suffix == '.txt':
                    annotation = ROOT / 'data/labelme_annotations' / (file.stem + '.json')
                    original = json.loads(annotation.read_text(encoding='utf-8'))
                    names = ['creme_leite', 'gelatina', 'cha', 'mao']
                    w, h = original['imageWidth'], original['imageHeight']
                    lines = []
                    for shape in original['shapes']:
                        if shape['label'] not in names:
                            raise ValueError('Classe desconhecida: ' + str(annotation))
                        if shape.get('shape_type') not in {'polygon', 'rectangle', 'mask'}:
                            raise ValueError('Tipo desconhecido: ' + str(annotation))
                        xs, ys = zip(*shape['points'])
                        x1, x2 = max(0, min(xs)), min(w, max(xs))
                        y1, y2 = max(0, min(ys)), min(h, max(ys))
                        if x2 <= x1 or y2 <= y1:
                            raise ValueError('Caixa degenerada: ' + str(annotation))
                        lines.append(f'{names.index(shape["label"])} {(x1+x2)/(2*w):.6f} {(y1+y2)/(2*h):.6f} {(x2-x1)/w:.6f} {(y2-y1)/h:.6f}')
                    dest.write_text('\n'.join(lines), encoding='utf-8')
                    annotation_dest = out / 'annotations' / annotation.name
                    annotation_dest.parent.mkdir(exist_ok=True)
                    shutil.copy2(annotation, annotation_dest)
                    manifest.append(dict(path=annotation_dest.relative_to(out).as_posix(), sha256=digest(annotation_dest)))
                manifest.append(dict(path=relative.as_posix(), sha256=digest(dest)))
    if hashes['train'] & hashes['val']:
        raise RuntimeError('Imagens identicas entre treino e validacao')
    config = yaml.safe_load((source / 'data.yaml').read_text(encoding='utf-8'))
    config['path'] = (out / 'dataset').as_posix()
    (out / 'dataset/data.yaml').write_text(yaml.safe_dump(config, allow_unicode=True), encoding='utf-8')
    metadata = dict(python=platform.python_version(), torch=torch.__version__,
                    ultralytics=ultralytics.__version__, gpu=torch.cuda.get_device_name(0),
                    seed=0, epochs=50, batch=2, imgsz=640,
                    images={s:len(h) for s,h in hashes.items()}, files=manifest,
                    pretrained={m:digest(ROOT / 'models/pretrained' / (m+'.pt')) for m in MODELS})
    (out / 'protocol.json').write_text(json.dumps(metadata, indent=2), encoding='utf-8')
    for name in MODELS:
        print('START', name, flush=True)
        with (out / (name + '.log')).open('w', encoding='utf-8') as log:
            subprocess.run([sys.executable, '-u', str(Path(__file__).resolve()),
                            '--out', str(out), '--model', name], cwd=ROOT,
                           stdout=log, stderr=subprocess.STDOUT, check=True)
        print('DONE', name, flush=True)
    results = [json.loads((out / (m+'_summary.json')).read_text()) for m in MODELS]
    (out / 'summary.json').write_text(json.dumps(results, indent=2), encoding='utf-8')
    fields = ['model','epochs','best_csv_epoch','precision','recall','map50','map50_95','training_seconds','csv_seconds']
    with (out / 'comparativo.csv').open('w', newline='', encoding='utf-8-sig') as f:
        writer = csv.DictWriter(f, fieldnames=fields, extrasaction='ignore')
        writer.writeheader()
        writer.writerows(results)
    print('COMPLETE', out, flush=True)

if __name__ == '__main__':
    main()


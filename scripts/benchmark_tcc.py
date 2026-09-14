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

def calcular_hash(caminho):
    return hashlib.sha256(caminho.read_bytes()).hexdigest()

def treinar_modelo(pasta_saida, nome):
    import torch
    from ultralytics import YOLO
    inicio = time.perf_counter()
    modelo = YOLO(str(ROOT / 'models/pretrained' / (nome + '.pt')))
    modelo.train(data=str(pasta_saida / 'dataset/data.yaml'), epochs=50, patience=0,
                imgsz=640, batch=2, workers=2, device=0, seed=0,
                deterministic=True, pretrained=True, fraction=1.0,
                optimizer='AdamW', lr0=0.00125, momentum=0.9,
                weight_decay=0.0005, nbs=64, amp=False, cache=False,
                close_mosaic=10, project=str(pasta_saida), name=nome, exist_ok=False)
    tempo_decorrido = time.perf_counter() - inicio
    del modelo
    torch.cuda.empty_cache()
    melhores_pesos = YOLO(str(pasta_saida / nome / 'weights/best.pt'))
    resultado = melhores_pesos.val(data=str(pasta_saida / 'dataset/data.yaml'), imgsz=640,
                      batch=1, device=0, workers=2, quantize=32, rect=False,
                      conf=0.001, iou=0.7, max_det=300, augment=False,
                      project=str(pasta_saida), name=nome + '_validation', plots=True)
    with (pasta_saida / nome / 'results.csv').open(encoding='utf-8', newline='') as arquivo_csv:
        linhas = list(csv.DictReader(arquivo_csv))
    melhor_epoca = max(linhas, key=lambda r: float(r['metrics/mAP50-95(B)']))
    informacoes = dict(model=nome, epochs=len(linhas), best_csv_epoch=int(melhor_epoca['epoch']),
                precision=float(resultado.box.mp), recall=float(resultado.box.mr),
                map50=float(resultado.box.map50), map50_95=float(resultado.box.map),
                training_seconds=tempo_decorrido, csv_seconds=float(linhas[-1]['time']),
                speed_ms=resultado.speed,
                classes={str(melhores_pesos.names[int(c)]):list(map(float,resultado.box.class_result(i)))
                         for i,c in enumerate(resultado.box.ap_class_index)},
                checkpoint_sha256=calcular_hash(pasta_saida / nome / 'weights/best.pt'))
    (pasta_saida / (nome + '_summary.json')).write_text(json.dumps(informacoes, indent=2), encoding='utf-8')

def converter_anotacao_benchmark(annotation):
    """Usa todos os pontos e recorta à imagem, conforme o protocolo experimental."""
    original = json.loads(annotation.read_text(encoding='utf-8'))
    nomes = ['creme_leite', 'gelatina', 'cha', 'mao']
    largura, altura = original['imageWidth'], original['imageHeight']
    linhas = []
    for forma in original['shapes']:
        if forma['label'] not in nomes:
            raise ValueError('Classe desconhecida: ' + str(annotation))
        if forma.get('shape_type') not in {'polygon', 'rectangle', 'mask'}:
            raise ValueError('Tipo desconhecido: ' + str(annotation))
        xs, ys = zip(*forma['points'])
        x1, x2 = max(0, min(xs)), min(largura, max(xs))
        y1, y2 = max(0, min(ys)), min(altura, max(ys))
        if x2 <= x1 or y2 <= y1:
            raise ValueError('Caixa degenerada: ' + str(annotation))
        linhas.append(f'{nomes.index(forma["label"])} {(x1+x2)/(2*largura):.6f} {(y1+y2)/(2*altura):.6f} {(x2-x1)/largura:.6f} {(y2-y1)/altura:.6f}')
    return '\n'.join(linhas)

def congelar_dataset(out):
    """Copia dados e anotações, valida duplicatas e registra hashes sem treinar."""
    import yaml
    origem = ROOT / 'data/dataset'
    manifesto = []
    resumos = {}
    for particao in ['train', 'val']:
        resumos[particao] = set()
        for imagem in sorted((origem / 'images' / particao).iterdir()):
            if imagem.suffix.lower() not in {'.jpg', '.jpeg', '.png', '.bmp', '.webp'}:
                continue
            rotulo = origem / 'labels' / particao / (imagem.stem + '.txt')
            if not rotulo.is_file():
                raise RuntimeError('Anotacao ausente: ' + str(rotulo))
            resumos[particao].add(calcular_hash(imagem))
            for arquivo in [imagem, rotulo]:
                relativo = arquivo.relative_to(origem)
                destino = out / 'dataset' / relativo
                destino.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(arquivo, destino)
                if arquivo.suffix == '.txt':
                    anotacao = ROOT / 'data/labelme_annotations' / (arquivo.stem + '.json')
                    destino.write_text(converter_anotacao_benchmark(anotacao), encoding='utf-8')
                    destino_anotacao = out / 'annotations' / anotacao.name
                    destino_anotacao.parent.mkdir(exist_ok=True)
                    shutil.copy2(anotacao, destino_anotacao)
                    manifesto.append(dict(path=destino_anotacao.relative_to(out).as_posix(), sha256=calcular_hash(destino_anotacao)))
                manifesto.append(dict(path=relativo.as_posix(), sha256=calcular_hash(destino)))
    if resumos['train'] & resumos['val']:
        raise RuntimeError('Imagens identicas entre treino e validacao')
    config = yaml.safe_load((origem / 'data.yaml').read_text(encoding='utf-8'))
    config['path'] = (out / 'dataset').as_posix()
    (out / 'dataset/data.yaml').write_text(yaml.safe_dump(config, allow_unicode=True), encoding='utf-8')
    return resumos, manifesto

def main():
    argumentos = argparse.ArgumentParser()
    argumentos.add_argument('--out', type=Path, required=True)
    argumentos.add_argument('--model', choices=MODELS)
    opcoes = argumentos.parse_args()
    pasta_saida = opcoes.out.resolve()
    if opcoes.model:
        treinar_modelo(pasta_saida, opcoes.model)
        return
    import torch
    import ultralytics
    import yaml
    if not torch.cuda.is_available():
        raise RuntimeError('GPU CUDA indisponivel')
    pasta_saida.mkdir(parents=True, exist_ok=False)
    resumos, manifesto = congelar_dataset(pasta_saida)
    metadados = dict(python=platform.python_version(), torch=torch.__version__,
                    ultralytics=ultralytics.__version__, gpu=torch.cuda.get_device_name(0),
                    seed=0, epochs=50, batch=2, imgsz=640,
                    images={particao: len(resumo) for particao, resumo in resumos.items()}, files=manifesto,
                    pretrained={m:calcular_hash(ROOT / 'models/pretrained' / (m+'.pt')) for m in MODELS})
    (pasta_saida / 'protocol.json').write_text(json.dumps(metadados, indent=2), encoding='utf-8')
    for nome in MODELS:
        print('START', nome, flush=True)
        with (pasta_saida / (nome + '.log')).open('w', encoding='utf-8') as log:
            subprocess.run([sys.executable, '-u', str(Path(__file__).resolve()),
                            '--out', str(pasta_saida), '--model', nome], cwd=ROOT,
                           stdout=log, stderr=subprocess.STDOUT, check=True)
        print('DONE', nome, flush=True)
    resultados = [json.loads((pasta_saida / (m+'_summary.json')).read_text()) for m in MODELS]
    (pasta_saida / 'summary.json').write_text(json.dumps(resultados, indent=2), encoding='utf-8')
    campos = ['model','epochs','best_csv_epoch','precision','recall','map50','map50_95','training_seconds','csv_seconds']
    with (pasta_saida / 'comparativo.csv').open('w', newline='', encoding='utf-8-sig') as f:
        gravador = csv.DictWriter(f, fieldnames=campos, extrasaction='ignore')
        gravador.writeheader()
        gravador.writerows(resultados)
    print('COMPLETE', pasta_saida, flush=True)



# Compatibilidade de importação com os nomes anteriores.
def digest(path):
    """Aceita os parâmetros nomeados da interface anterior."""
    return calcular_hash(path)
def train_one(out, name):
    """Aceita os parâmetros nomeados da interface anterior."""
    return treinar_modelo(out, name)

if __name__ == '__main__':
    main()


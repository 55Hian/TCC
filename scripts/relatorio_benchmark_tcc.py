"""Gera tabelas e curvas somente depois dos quatro benchmarks completos."""
import argparse
import csv
import json
from pathlib import Path

def number(value, digits=2):
    return f'{value:.{digits}f}'.replace('.', ',')

def table(headers, rows):
    return '\n'.join(['| ' + ' | '.join(headers) + ' |', '| ' + ' | '.join(['---']*len(headers)) + ' |'] + ['| ' + ' | '.join(map(str,row)) + ' |' for row in rows])

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('directory', type=Path)
    args=parser.parse_args()
    out=args.directory.resolve()
    names=['yolov8n','yolo12n','yolo26s','yolo26m']
    results=[json.loads((out/(name+'_summary.json')).read_text(encoding='utf-8')) for name in names]
    histories={name:list(csv.DictReader((out/name/'results.csv').open())) for name in names}
    if any(len(rows)!=50 for rows in histories.values()):
        raise RuntimeError('Todos os treinos devem ter 50 epocas completas')
    metric='metrics/mAP50-95(B)'
    main_rows=[]
    epoch_rows=[]
    class_rows=[]
    for r in results:
        name=r['model']
        main_rows.append([name, str(r['epochs']), str(r['best_csv_epoch']), *[number(100*r[k]) for k in ['precision','recall','map50','map50_95']], number(r['training_seconds']/60)])
        h=histories[name]
        best20=max(float(row[metric]) for row in h[:20])
        best50=max(float(row[metric]) for row in h)
        epoch_rows.append([name,number(100*best20),number(100*best50),number(100*(best50-best20))])
        for label, values in r['classes'].items():
            class_rows.append([name,label,*[number(v*100) for v in values]])
    with (out/'comparativo_por_classe.csv').open('w',newline='',encoding='utf-8-sig') as f:
        w=csv.writer(f,delimiter=';')
        w.writerow(['Modelo','Classe','Precisao (%)','Recall (%)','mAP50 (%)','mAP50-95 (%)'])
        w.writerows(class_rows)
    report='''# Comparativo experimental YOLO — TCC

## Protocolo

Quatro modelos pré-treinados (YOLOv8n, YOLO12n, YOLO26s e YOLO26m), cada um treinado por 50 épocas na mesma NVIDIA GeForce GTX 1650 de 4 GB, sequencialmente. Configuração comum: imgsz=640, batch=2, workers=2, fraction=1.0, seed=0, deterministic=True, optimizer=AdamW, lr0=0.00125, momentum=0.9, weight_decay=0.0005, nbs=64, close_mosaic=10, amp=False (FP32), patience=0. Os demais parâmetros estão registrados no args.yaml de cada execução. Ambiente: Python 3.13.9, PyTorch 2.6.0+cu124 e Ultralytics 8.4.141.

O dataset foi copiado antes do treinamento, mantendo o split de 76 imagens de treino e 19 de validação. Foram preservadas as quatro classes: creme_leite, gelatina, cha e mao. Há 539 instâncias de treino e 132 de validação. Não há imagens de conteúdo binário idêntico entre os splits. O arquivo protocol.json registra hashes SHA-256 dos dados, das anotações e dos pesos pré-treinados.

As caixas foram regeneradas dos JSONs LabelMe na cópia do experimento, usando os extremos de todos os pontos dos polígonos e os limites das máscaras/retângulos, com recorte às dimensões da imagem. A conversão anterior usava apenas dois pontos dos polígonos, produzindo inclusive caixas de altura zero. Foram alterados 16 arquivos TXT; os arquivos originais do projeto foram preservados. A execução preliminar na pasta comparativo_20260907_50ep foi interrompida e não integra este comparativo.

## Resultados

As métricas abaixo são da reavaliação do best.pt de cada treino sobre a mesma validação, com imgsz=640, batch=1, FP32, rect=False, conf=0.001, iou=0.7 e max_det=300. A coluna de época identifica o maior mAP50–95 no CSV do treino. A reavaliação pode apresentar pequenas diferenças por usar um protocolo de inferência distinto daquele da validação interna durante o treino. O tempo inclui a chamada de treinamento e sua validação final, mas exclui a reavaliação separada.

'''
    report+=table(['Modelo','Épocas','Melhor época (CSV)','Precisão (%)','Recall (%)','mAP50 (%)','mAP50–95 (%)','Tempo de treino (min)'],main_rows)
    report+='\n\n## Evolução até 20 e 50 épocas\n\n'
    report+='Máximos de mAP50–95 observados nos CSVs da mesma execução. Os primeiros 20 ciclos de um treino programado para 50 épocas não equivalem a um treino independente de 20 épocas, pois o agendamento da taxa de aprendizado e o fechamento do mosaic dependem da duração total.\n\n'
    report+=table(['Modelo','Melhor até 20 (%)','Melhor até 50 (%)','Ganho (p.p.)'],epoch_rows)
    report+='\n\n## Resultados por classe\n\n'+table(['Modelo','Classe','Precisão (%)','Recall (%)','mAP50 (%)','mAP50–95 (%)'],class_rows)
    report+='''

## Limitações e interpretação

Este é um comparativo de validação com uma execução por modelo e uma única semente; não estima variabilidade entre treinos nem significância estatística. O conjunto de validação também seleciona o melhor checkpoint, portanto as métricas não representam um teste independente. As imagens incluem frames próximos de uma mesma captura, que podem ser visualmente semelhantes entre treino e validação mesmo sem duplicatas exatas. A generalização exige avaliação adicional em cenas/sessões de captura separadas, idealmente com repetições por semente.

O protocolo controla hiperparâmetros para comparação, mas não busca o melhor ajuste individual de cada arquitetura. Os modelos usam suas perdas e arquiteturas próprias. Cinquenta épocas constituem o orçamento experimental escolhido, sem garantia prévia de convergência. Os resultados antigos não devem ser combinados com estes devido à correção das anotações e às diferenças de configuração.

Os tempos de inferência disponíveis nos JSONs são diagnósticos de uma passagem de validação pequena; não constituem benchmark de FPS da aplicação nem incluem câmera, comunicação e processamento de eventos.

## Artefatos

- `comparativo.csv`: resultados numéricos globais (métricas entre 0 e 1).
- `comparativo_por_classe.csv`: tabela por classe, percentuais com vírgula decimal.
- `summary.json` e `*_summary.json`: métricas completas e hashes dos checkpoints.
- `protocol.json`, `dataset/` e `annotations/`: protocolo e cópia dos dados utilizados.
- Pastas de cada modelo: `args.yaml`, `results.csv`, curvas e `weights/best.pt`.
- `curvas_map.png`: evolução do mAP50–95 na validação interna durante o treino.

Reprodução: executar `python scripts/benchmark_tcc.py --out experiments/benchmarks/NOVA_PASTA` usando o mesmo ambiente e os mesmos dados/pesos de origem; em seguida, `python scripts/relatorio_benchmark_tcc.py experiments/benchmarks/NOVA_PASTA`. A pasta de saída deve ser inédita. Os hashes permitem conferir se as entradas continuam iguais às desta execução.
'''
    (out/'RELATORIO_TCC.md').write_text(report,encoding='utf-8')
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    fig,ax=plt.subplots(figsize=(9,5))
    for name,h in histories.items():
        ax.plot([int(r['epoch']) for r in h],[100*float(r[metric]) for r in h],label=name)
    ax.axvline(20,color='gray',linestyle='--',linewidth=1)
    ax.set(xlabel='Época',ylabel='mAP50–95 de validação (%)',title='Evolução dos quatro modelos — mesmo protocolo')
    ax.legend(); ax.grid(alpha=.25); fig.tight_layout()
    fig.savefig(out/'curvas_map.png',dpi=220)
    plt.close(fig)
    print(out/'RELATORIO_TCC.md')

if __name__=='__main__':
    main()

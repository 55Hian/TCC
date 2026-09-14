# Comparativo experimental YOLO — TCC

## Protocolo

Quatro modelos pré-treinados (YOLOv8n, YOLO12n, YOLO26s e YOLO26m), cada um treinado por 50 épocas na mesma NVIDIA GeForce GTX 1650 de 4 GB, sequencialmente. Configuração comum: imgsz=640, batch=2, workers=2, fraction=1.0, seed=0, deterministic=True, optimizer=AdamW, lr0=0.00125, momentum=0.9, weight_decay=0.0005, nbs=64, close_mosaic=10, amp=False (FP32), patience=0. Os demais parâmetros estão registrados no args.yaml de cada execução. Ambiente: Python 3.13.9, PyTorch 2.6.0+cu124 e Ultralytics 8.4.141.

O dataset foi copiado antes do treinamento, mantendo o split de 76 imagens de treino e 19 de validação. Foram preservadas as quatro classes: creme_leite, gelatina, cha e mao. Há 539 instâncias de treino e 132 de validação. Não há imagens de conteúdo binário idêntico entre os splits. O arquivo protocol.json registra hashes SHA-256 dos dados, das anotações e dos pesos pré-treinados.

As caixas foram regeneradas dos JSONs LabelMe na cópia do experimento, usando os extremos de todos os pontos dos polígonos e os limites das máscaras/retângulos, com recorte às dimensões da imagem. A conversão anterior usava apenas dois pontos dos polígonos, produzindo inclusive caixas de altura zero. Foram alterados 16 arquivos TXT; os arquivos originais do projeto foram preservados. A execução preliminar na pasta comparativo_20260907_50ep foi interrompida e não integra este comparativo.

## Resultados

As métricas abaixo são da reavaliação do best.pt de cada treino sobre a mesma validação, com imgsz=640, batch=1, FP32, rect=False, conf=0.001, iou=0.7 e max_det=300. A coluna de época identifica o maior mAP50–95 no CSV do treino. A reavaliação pode apresentar pequenas diferenças por usar um protocolo de inferência distinto daquele da validação interna durante o treino. O tempo inclui a chamada de treinamento e sua validação final, mas exclui a reavaliação separada.

{{TABELA_1}}

## Evolução até 20 e 50 épocas

Máximos de mAP50–95 observados nos CSVs da mesma execução. Os primeiros 20 ciclos de um treino programado para 50 épocas não equivalem a um treino independente de 20 épocas, pois o agendamento da taxa de aprendizado e o fechamento do mosaic dependem da duração total.

{{TABELA_2}}

## Resultados por classe

{{TABELA_3}}

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

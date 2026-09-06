---
name: execucao-inventario
description: "Reconstrua, valide e execute o sistema de controle autonomo de inventario com ESP32-CAM, YOLOv8, LabelMe, pandas e API HTTP. Use quando o usuario pedir para executar o sistema descrito no MANUAL_RECONSTRUCAO.md, reconstruir o projeto ou validar o pipeline de visao."
argument-hint: "Informe a etapa desejada: reconstruir, validar dataset, treinar ou executar inferencia"
user-invocable: true
disable-model-invocation: false
---

# Execucao do Controle Autonomo de Inventario

## Objetivo

Reconstruir e validar o projeto descrito em `MANUAL_RECONSTRUCAO.md`, mantendo a separacao entre camera, visao, eventos, API e treinamento.

## Procedimento

1. Leia `MANUAL_RECONSTRUCAO.md` e confirme a raiz do workspace.
2. Verifique se `projeto/`, `requirements.txt`, dataset, pesos YOLO e interpretador Python existem.
3. Se o codigo nao existir, crie `projeto/{controllers,services,utils}` e os modulos descritos no manual. Preserve datasets e alteracoes existentes.
4. Execute primeiro a validacao barata: compile os arquivos Python e teste as funcoes puras de conversao LabelMe e geracao de eventos com DataFrames.
5. Para treinamento proprio, confirme JSONs em `dataset_labels/` e imagens correspondentes em `dataset_fotos/`; converta JSON para YOLO, monte `dataset/` e gere `data.yaml` antes de iniciar o Ultralytics.
6. Para dataset externo, ative `USE_EXTERNAL_VALIDATION_DATASET` somente de forma temporaria e confirme que o YAML usa classes compativeis. Nunca trate um dataset externo com classes diferentes como dataset final sem revisao.
7. Para inferencia, confirme `MODEL_PATH`, `ESP32_STREAM_URL` e `API_ENDPOINT`; so entao inicie o loop camera -> YOLO -> eventos -> API.
8. Nao abra camera, janela OpenCV, API ou treinamento durante testes unitarios. Esses passos exigem hardware, pesos e dependencias instalados.

## Decisoes e bloqueios

- Se faltar `projeto/`, reconstrua-o a partir do manual.
- Se faltarem `ultralytics`, `torch` ou `opencv`, reporte o bloqueio e valide apenas sintaxe e funcoes que nao dependem dessas bibliotecas; nao declare inferencia executada.
- Se faltarem pesos `.pt`, nao tente mascarar o erro: reporte que a inferencia esta bloqueada.
- Se o stream ou backend falhar, preserve o loop e reporte a falha de infraestrutura separadamente do resultado do modelo.
- Nao use LabelImg; o fluxo oficial e LabelMe -> JSON -> YOLO.

## Criterios de conclusao

- Todos os arquivos Python compilam sem erro.
- A conversao de um JSON LabelMe produz uma linha YOLO normalizada correta.
- Um caso controlado de insercao/remocao e interacao com a mao produz os eventos esperados.
- Dependencias, pesos, camera e API sao reportados explicitamente como validados ou indisponiveis.
- O resultado final distingue reconstrução, validacao local, treinamento e inferencia real.

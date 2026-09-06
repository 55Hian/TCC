# Manual de Reconstrução do Projeto — Controle Autônomo de Inventário (TCC)

> Este documento foi gerado a partir do histórico completo da sessão de desenvolvimento (E:\TCC, disco fisicamente perdido) e do conteúdo do TCC (`Controle Autônomo de Inventário`, SENAC Santo Amaro, 2026). Ele contém tudo que é necessário para recriar o repositório do zero: estrutura de pastas, conteúdo integral dos arquivos Python, dependências, comandos de execução e o histórico de decisões técnicas que levaram ao estado atual do código.
>
> Use este arquivo como fonte única da verdade para reconstruir o projeto em `D:\TCC2026` (ou em qualquer outro caminho).

---

## 1. Visão geral da arquitetura

O sistema é um protótipo de **controle autônomo de inventário** que usa uma **ESP32-CAM** para capturar vídeo, transmite o fluxo para um notebook via Wi-Fi/HTTP, processa os frames com **YOLOv8 (Ultralytics)**, compara o estado anterior e atual da cena com **pandas** para gerar eventos de estoque (produto inserido, retirado, interação com a mão), e envia esses eventos para uma API HTTP externa via **requests**.

Fluxo cronológico (o mesmo usado no capítulo de Resultados do TCC):

1. **Transmissão de Borda** — ESP32-CAM captura e transmite vídeo bruto via HTTP (`services/camera_service.py`).
2. **Aquisição/Decodificação** — o notebook reconstrói os frames JPEG a partir do stream (mesmo arquivo).
3. **Construção do Dataset e Anotação com LabelMe** — imagens de `dataset_fotos/` são anotadas manualmente no LabelMe, gerando JSON em `dataset_labels/`.
4. **Conversão do Dataset (LabelMe → YOLO)** — `services/annotation_converter.py` converte os JSON em `.txt` no formato YOLO, salvos em `labels_yolo/`.
5. **Organização do Dataset e Treinamento do YOLOv8** — `services/training_service.py` monta `dataset/images/{train,val}` e `dataset/labels/{train,val}`, gera `data.yaml` e treina o modelo (`treinamentos/modelo_produtos/weights/best.pt`), usando GPU se disponível.
6. **Inferência em Tempo Real** — `services/vision_service.py` roda o modelo treinado sobre cada frame e devolve um `DataFrame` de detecções.
7. **Interpretação de Eventos** — `services/event_service.py` compara o frame anterior com o atual (contagem por classe + IoU mão↔produto) e gera eventos de negócio.
8. **Entrega dos Eventos** — `controllers/api_controller.py` envia os eventos via `POST` HTTP para o backend.
9. **Orquestração** — `main.py` conecta todas as peças.

Arquitetura em camadas, seguindo o padrão pedido:

```
projeto/
├── main.py
├── controllers/
│   ├── __init__.py
│   └── api_controller.py
├── services/
│   ├── __init__.py
│   ├── camera_service.py
│   ├── vision_service.py
│   ├── event_service.py
│   ├── annotation_converter.py
│   └── training_service.py
└── utils/
    ├── __init__.py
    └── config.py
```

Estrutura completa do repositório (nível raiz):

```
TCC2026/
├── instructions.md                 # notas/instruções gerais do projeto (livre, recriar conforme necessidade)
├── dataset_fotos/                  # imagens brutas capturadas do ESP32-CAM (.jpg)
├── dataset_labels/                 # JSON gerados pelo LabelMe (1 por imagem anotada)
├── labels_yolo/                    # .txt convertidos no formato YOLO (gerado automaticamente)
├── dataset/                        # dataset final estruturado para o YOLO (gerado automaticamente)
│   ├── images/{train,val}/
│   ├── labels/{train,val}/
│   └── data.yaml
├── treinamentos/                   # saída do treinamento YOLO (gerado automaticamente pelo Ultralytics)
│   └── modelo_produtos/weights/best.pt
├── .agent.md                       # persona do agente Copilot especializada neste projeto
├── projeto/                        # código-fonte da aplicação (ver acima)
└── Python_3_11/                    # distribuição embutida do Python 3.11 (interpretador do projeto)
```

---

## 2. Ambiente Python

O projeto **não usa o Python do sistema**. Ele usa uma distribuição *embeddable* do Python 3.11 dentro do próprio repositório, em `Python_3_11/`, com `pip` instalado manualmente via `get-pip.py`. Isso torna o ambiente portátil e isolado.

### 2.1. Recriar o ambiente

```powershell
# 1) Baixe o "Windows embeddable package (64-bit)" do Python 3.11.x em python.org
#    e extraia o conteúdo para D:\TCC2026\Python_3_11

# 2) Habilite o site-packages editando Python_3_11\python311._pth
#    (remova o "#" da linha "#import site")

# 3) Instale o pip
D:\TCC2026\Python_3_11\python.exe D:\TCC2026\Python_3_11\get-pip.py

# 4) Instale as dependências do projeto
D:\TCC2026\Python_3_11\python.exe -m pip install --upgrade pip
D:\TCC2026\Python_3_11\python.exe -m pip install opencv-python numpy pandas requests ultralytics labelme sympy==1.13.1 mpmath==1.3.0
```

### 2.2. Dependências usadas pelo código (`requirements.txt` sugerido)

```text
opencv-python
numpy
pandas
requests
ultralytics
torch
torchvision
sympy==1.13.1
mpmath==1.3.0
labelme
```

> **Observação crítica (lição aprendida em produção):** o `pip install ultralytics` traz `torch` em versão **CPU-only** por padrão no Windows. Se houver GPU NVIDIA dedicada disponível, reinstale explicitamente a build CUDA:
> ```powershell
> D:\TCC2026\Python_3_11\python.exe -m pip uninstall -y torch torchvision
> D:\TCC2026\Python_3_11\python.exe -m pip install torch torchvision --index-url https://download.pytorch.org/whl/cu121
> ```
> Valide com:
> ```powershell
> D:\TCC2026\Python_3_11\python.exe -c "import torch; print(torch.cuda.is_available(), torch.cuda.get_device_name(0) if torch.cuda.is_available() else 'CPU')"
> ```

> **Observação sobre o LabelImg:** a ferramenta `labelImg` (PyQt5) se mostrou **instável no Windows** deste ambiente — travava/fechava com `TypeError: drawLine(... float ...)` ao desenhar bounding boxes (bug de incompatibilidade Qt/labelImg). **A decisão tomada foi abandonar o LabelImg e migrar para o `labelme`**, que é estável e gera JSON (convertido depois para `.txt` YOLO por código próprio). Não recrie a dependência do LabelImg.

---

## 3. Conteúdo completo dos arquivos Python

### 3.1. `projeto/utils/__init__.py`, `projeto/services/__init__.py`, `projeto/controllers/__init__.py`

Arquivos vazios — necessários para que `utils`, `services` e `controllers` sejam reconhecidos como pacotes Python quando o projeto é executado a partir da raiz do repositório.

```python
# conteúdo: vazio
```

### 3.2. `projeto/utils/config.py`

Configuração central do projeto: URLs, classes do modelo, thresholds, caminhos de dataset/treino e o **switch reversível** para testes com dataset externo.

```python
ESP32_STREAM_URL = "http://192.168.15.59:81/stream"
API_ENDPOINT = "http://localhost:8000/api/eventos"

CLASSES = ["creme_leite", "gelatina", "cha", "mao"]

IOU_THRESHOLD = 0.15
INTERVALO_PROCESSAMENTO = 1.0

DATASET_DIR = "dataset"
TRAINING_PROJECT = "treinamentos"
TRAINING_NAME = "modelo_produtos"
MODEL_PATH = "treinamentos/modelo_produtos/weights/best.pt"

# MODO TEMPORARIO DE VALIDACAO
# True = usa o dataset externo em D:\yolo para validar o codigo
# False = volta para o fluxo do dataset proprio do projeto
USE_EXTERNAL_VALIDATION_DATASET = False
EXTERNAL_VALIDATION_DATASET_DIR = r"D:\yolo"
EXTERNAL_VALIDATION_DATASET_YAML = r"D:\yolo\data.yaml"
```

> Ajuste `ESP32_STREAM_URL` para o IP real do seu ESP32-CAM na rede local (aparece no Serial Monitor do Arduino IDE ao ligar o dispositivo).
> Mantenha `USE_EXTERNAL_VALIDATION_DATASET = False` por padrão; só ative como `True` temporariamente para validar o pipeline com um dataset externo (ex.: `D:\yolo`) enquanto o dataset próprio não estiver pronto. É reversível: basta voltar para `False`.

### 3.3. `projeto/services/camera_service.py`

Responsável por conectar no stream MJPEG do ESP32-CAM, reconstruir os frames JPEG a partir dos bytes recebidos e entregar cada frame como um generator, com reconexão automática em caso de queda de rede.

```python
import time
import urllib.request

import cv2
import numpy as np


def gerador_de_frames(url_stream):
    """Conecta ao ESP32-CAM e entrega frames continuamente como um generator."""
    while True:
        try:
            print(f"[CÂMERA] Conectando em {url_stream}...")
            stream = urllib.request.urlopen(url_stream, timeout=10)
            bytes_stream = b""
            print("[CÂMERA] Conectado! Enviando frames...")

            while True:
                bytes_stream += stream.read(4096)
                inicio = bytes_stream.find(b"\xff\xd8")
                fim = bytes_stream.find(b"\xff\xd9")

                if inicio != -1 and fim != -1:
                    if inicio < fim:
                        jpg = bytes_stream[inicio:fim + 2]
                        bytes_stream = bytes_stream[fim + 2:]

                        frame = cv2.imdecode(np.frombuffer(jpg, dtype=np.uint8), cv2.IMREAD_COLOR)
                        if frame is not None:
                            yield frame
                    else:
                        bytes_stream = bytes_stream[inicio:]

        except Exception as exc:
            print(f"[CÂMERA] Falha de rede: {exc}. Reconectando em 2 segundos...")
            time.sleep(2)
```

### 3.4. `projeto/services/vision_service.py`

Carrega o modelo YOLOv8 treinado e converte a saída de inferência em um `pandas.DataFrame` de detecções (classe, confiança, coordenadas da bounding box).

```python
import pandas as pd
from ultralytics import YOLO

from utils.config import CLASSES


class VisionService:
    def __init__(self, caminho_pesos="treinamentos/modelo_produtos/weights/best.pt"):
        self.modelo = YOLO(caminho_pesos)

    def processar_frame(self, frame):
        resultados = self.modelo(frame, verbose=False)[0]
        deteccoes = []

        for box in resultados.boxes:
            x_min, y_min, x_max, y_max = box.xyxy[0].tolist()
            deteccoes.append(
                {
                    "classe": CLASSES[int(box.cls[0])],
                    "confianca": float(box.conf[0]),
                    "x_min": x_min,
                    "y_min": y_min,
                    "x_max": x_max,
                    "y_max": y_max,
                }
            )

        return pd.DataFrame(deteccoes)
```

### 3.5. `projeto/services/event_service.py`

Compara a contagem de produtos por classe entre o frame anterior e o atual (para detectar inserção/retirada) e calcula IoU entre a caixa da classe `mao` e as demais classes para detectar interação física.

```python
import pandas as pd

from utils.config import IOU_THRESHOLD


def calcular_area_intersecao(box_a, box_b):
    x_a = max(box_a["x_min"], box_b["x_min"])
    y_a = max(box_a["y_min"], box_b["y_min"])
    x_b = min(box_a["x_max"], box_b["x_max"])
    y_b = min(box_a["y_max"], box_b["y_max"])

    intersecao = max(0, x_b - x_a) * max(0, y_b - y_a)
    area_a = (box_a["x_max"] - box_a["x_min"]) * (box_a["y_max"] - box_a["y_min"])
    area_b = (box_b["x_max"] - box_b["x_min"]) * (box_b["y_max"] - box_b["y_min"])

    uniao = float(area_a + area_b - intersecao)
    return (intersecao / uniao) if uniao > 0 else 0


def gerar_eventos(df_anterior, df_atual):
    eventos = []
    if df_atual.empty and df_anterior.empty:
        return eventos

    c_ant = (
        df_anterior[df_anterior["classe"] != "mao"].groupby("classe").size()
        if not df_anterior.empty
        else pd.Series(dtype=int)
    )
    c_atu = (
        df_atual[df_atual["classe"] != "mao"].groupby("classe").size()
        if not df_atual.empty
        else pd.Series(dtype=int)
    )

    diferenca = c_atu.sub(c_ant, fill_value=0)
    for classe, variacao in diferenca.items():
        if variacao > 0:
            eventos.append({"tipo": "inserido", "produto": classe, "quantidade": int(variacao)})
        elif variacao < 0:
            eventos.append({"tipo": "retirado", "produto": classe, "quantidade": int(abs(variacao))})

    if not df_atual.empty:
        for _, mao in df_atual[df_atual["classe"] == "mao"].iterrows():
            for _, prod in df_atual[df_atual["classe"] != "mao"].iterrows():
                if calcular_area_intersecao(mao.to_dict(), prod.to_dict()) >= IOU_THRESHOLD:
                    eventos.append({"tipo": "interacao_mao", "produto": prod["classe"], "quantidade": 1})
                    break

    return eventos
```

### 3.6. `projeto/services/annotation_converter.py`

Converte as anotações do LabelMe (JSON, com pontos do retângulo em coordenadas absolutas de pixel) para o formato de anotação do YOLO (`.txt`, com `classe cx cy w h` normalizados entre 0 e 1).

```python
import json
import os

from utils.config import CLASSES


def labelme_json_to_yolo(json_path, output_dir, classes=None):
    classes = classes or CLASSES
    with open(json_path, "r", encoding="utf-8") as handle:
        data = json.load(handle)

    image_width = data.get("imageWidth", 1)
    image_height = data.get("imageHeight", 1)

    txt_lines = []
    for shape in data.get("shapes", []):
        label = shape.get("label")
        if label not in classes:
            continue

        points = shape.get("points", [])
        if len(points) < 2:
            continue

        x1, y1 = points[0]
        x2, y2 = points[1]

        cls_id = classes.index(label)
        x_center = ((x1 + x2) / 2) / image_width
        y_center = ((y1 + y2) / 2) / image_height
        width = abs(x2 - x1) / image_width
        height = abs(y2 - y1) / image_height

        txt_lines.append(f"{cls_id} {x_center:.6f} {y_center:.6f} {width:.6f} {height:.6f}")

    os.makedirs(output_dir, exist_ok=True)
    nome_base = os.path.splitext(os.path.basename(json_path))[0]
    output_path = os.path.join(output_dir, f"{nome_base}.txt")

    with open(output_path, "w", encoding="utf-8") as handle:
        handle.write("\n".join(txt_lines))

    return output_path


def converter_labelme_para_yolo(json_dir, output_dir, classes=None):
    classes = classes or CLASSES
    os.makedirs(output_dir, exist_ok=True)

    arquivos = [
        nome for nome in os.listdir(json_dir)
        if nome.lower().endswith(".json")
    ]

    if not arquivos:
        raise FileNotFoundError(
            "Nenhum arquivo JSON do LabelMe foi encontrado. "
            "Anote as imagens com o LabelMe e salve os JSONs antes de converter."
        )

    convertidos = []
    for nome in arquivos:
        caminho_json = os.path.join(json_dir, nome)
        convertidos.append(labelme_json_to_yolo(caminho_json, output_dir, classes))

    return convertidos
```

> Regra de anotação usada no LabelMe (documentada no TCC, seção 4.3.2): classes `creme_leite`, `gelatina`, `cha`, `mao`. Cada imagem pode conter **múltiplas instâncias** (não precisa ser 1 produto por imagem); o importante é anotar todas as instâncias visíveis e, sempre que houver interação, também anotar a classe `mao`.

### 3.7. `projeto/services/training_service.py`

Pipeline de treinamento do YOLOv8. Espera JSON do LabelMe em `dataset_labels/`, converte para `.txt` YOLO em `labels_yolo/`, monta a estrutura `dataset/images|labels/{train,val}` com split 80/20, gera `data.yaml` e treina o modelo — usando GPU automaticamente se disponível. Também contém o modo temporário e **reversível** de validação com dataset externo (`USE_EXTERNAL_VALIDATION_DATASET`).

```python
import os
import random
import shutil

import torch
from ultralytics import YOLO

from services.annotation_converter import converter_labelme_para_yolo
from utils.config import (
    CLASSES,
    DATASET_DIR,
    TRAINING_NAME,
    TRAINING_PROJECT,
    USE_EXTERNAL_VALIDATION_DATASET,
    EXTERNAL_VALIDATION_DATASET_YAML,
)


def _resolve_device():
    """Retorna (device_para_ultralytics, nome_legivel) usando GPU quando disponível."""
    if torch.cuda.is_available():
        return 0, torch.cuda.get_device_name(0)
    return "cpu", "CPU"


def _treinar_com_dataset_externo(epochs=50, imgsz=640):
    """Caminho TEMPORARIO e REVERSIVEL: valida o pipeline com um dataset já pronto (ex.: D:\\yolo)."""
    print(f"[TREINO] MODO TEMPORARIO: usando dataset externo de validacao em {EXTERNAL_VALIDATION_DATASET_YAML}.")
    dispositivo, nome_dispositivo = _resolve_device()
    print(f"[TREINO] Iniciando YOLOv8 em: {nome_dispositivo}")

    modelo = YOLO("yolov8n.pt")
    modelo.train(
        data=EXTERNAL_VALIDATION_DATASET_YAML,
        epochs=epochs,
        imgsz=imgsz,
        project=TRAINING_PROJECT,
        name=TRAINING_NAME,
        device=dispositivo,
    )


def rodar_pipeline_treinamento(
    pasta_fotos="dataset_fotos",
    pasta_json="dataset_labels",
    pasta_yolo="labels_yolo",
    pasta_dataset=DATASET_DIR,
    epochs=50,
    imgsz=640,
):
    # Switch reversível: enquanto o dataset próprio não estiver pronto,
    # ligue USE_EXTERNAL_VALIDATION_DATASET=True em utils/config.py para validar o código.
    if USE_EXTERNAL_VALIDATION_DATASET:
        _treinar_com_dataset_externo(epochs=epochs, imgsz=imgsz)
        return

    os.makedirs(pasta_json, exist_ok=True)
    os.makedirs(pasta_yolo, exist_ok=True)

    print("[TREINO] Anote as imagens no LabelMe e salve os JSONs em dataset_labels.")
    print("[TREINO] Depois disso, o script converterá os arquivos para YOLO automaticamente.")

    if not os.listdir(pasta_json):
        raise FileNotFoundError(
            "Nenhum JSON do LabelMe foi encontrado em 'dataset_labels'. "
            "Anote as imagens no LabelMe e salve os arquivos JSON antes de iniciar o treino."
        )

    converter_labelme_para_yolo(pasta_json, pasta_yolo, CLASSES)

    for split in ["train", "val"]:
        os.makedirs(os.path.join(pasta_dataset, "images", split), exist_ok=True)
        os.makedirs(os.path.join(pasta_dataset, "labels", split), exist_ok=True)

    imagens = [f for f in os.listdir(pasta_fotos) if f.lower().endswith((".jpg", ".jpeg", ".png"))]
    validos = []
    for img in imagens:
        nome_base = os.path.splitext(img)[0]
        txt_esperado = f"{nome_base}.txt"
        if os.path.exists(os.path.join(pasta_yolo, txt_esperado)):
            validos.append(img)

    if not validos:
        raise FileNotFoundError(
            "Nenhuma imagem convertida foi encontrada em 'labels_yolo'. "
            "Verifique se os JSONs do LabelMe correspondem às imagens de 'dataset_fotos'."
        )

    random.seed(42)
    random.shuffle(validos)
    corte = int(len(validos) * 0.8)
    conjuntos = {"train": validos[:corte], "val": validos[corte:]}

    for split, arquivos in conjuntos.items():
        for img in arquivos:
            nome_base = os.path.splitext(img)[0]
            txt = f"{nome_base}.txt"
            shutil.copy(os.path.join(pasta_fotos, img), os.path.join(pasta_dataset, "images", split, img))
            shutil.copy(os.path.join(pasta_yolo, txt), os.path.join(pasta_dataset, "labels", split, txt))

    caminho_yaml = os.path.join(pasta_dataset, "data.yaml")
    with open(caminho_yaml, "w", encoding="utf-8") as f:
        f.write(f"path: {os.path.abspath(pasta_dataset).replace(chr(92), '/')}\n")
        f.write("train: images/train\n")
        f.write("val: images/val\n")
        f.write(f"names: {CLASSES}\n")

    dispositivo, nome_dispositivo = _resolve_device()
    print(f"[TREINO] Iniciando YOLOv8 em: {nome_dispositivo}")
    modelo = YOLO("yolov8n.pt")
    modelo.train(
        data=caminho_yaml,
        epochs=epochs,
        imgsz=imgsz,
        project=TRAINING_PROJECT,
        name=TRAINING_NAME,
        device=dispositivo,
    )
```

> **Histórico importante:** a primeira versão deste arquivo chamava `subprocess.run(["labelImg", ...])`. Isso foi removido por completo após o LabelImg se mostrar instável no Windows (crash ao desenhar bounding box). A versão acima (LabelMe + conversão JSON→YOLO) é a versão correta e definitiva.

### 3.8. `projeto/controllers/api_controller.py`

Envia a lista de eventos gerados por `event_service.py` para o backend via `POST` HTTP, adicionando timestamp e tolerando falhas de conexão sem derrubar o loop principal.

```python
import datetime

import requests

from utils.config import API_ENDPOINT


def enviar_eventos(lista_eventos):
    if not lista_eventos:
        return

    for evento in lista_eventos:
        evento["timestamp"] = datetime.datetime.now().isoformat()
        try:
            requests.post(API_ENDPOINT, json=evento, timeout=3)
            print(f"[API] Evento enviado: {evento['tipo']} -> {evento['produto']}")
        except Exception:
            print(f"[API_ERRO] Falha de conexão com backend para o evento {evento['tipo']}.")
```

### 3.9. `projeto/main.py`

Ponto de entrada. Insere a pasta do projeto no `sys.path` (necessário para os imports `controllers.*` / `services.*` / `utils.*` funcionarem quando o script é chamado a partir da raiz do repositório), inicializa a visão computacional e roda o loop de captura → inferência → eventos → API.

```python
import os
import sys
import time

import cv2
import pandas as pd

PROJ_DIR = os.path.dirname(os.path.abspath(__file__))
if PROJ_DIR not in sys.path:
    sys.path.insert(0, PROJ_DIR)

from controllers.api_controller import enviar_eventos
from services.camera_service import gerador_de_frames
from services.event_service import gerar_eventos
from services.training_service import rodar_pipeline_treinamento
from services.vision_service import VisionService
from utils.config import ESP32_STREAM_URL, INTERVALO_PROCESSAMENTO


def main():
    # Descomente a linha abaixo para (re)treinar o modelo antes de rodar a inferência.
    # rodar_pipeline_treinamento()
    # return

    try:
        ia_visao = VisionService()
    except Exception:
        print("[ERRO] Arquivo de pesos YOLO (.pt) não encontrado.")
        return

    df_anterior = pd.DataFrame()
    ultimo_processamento = time.time()

    for frame in gerador_de_frames(ESP32_STREAM_URL):
        cv2.imshow("Monitoramento de Estoque", frame)
        tempo_atual = time.time()

        if (tempo_atual - ultimo_processamento) >= INTERVALO_PROCESSAMENTO:
            df_atual = ia_visao.processar_frame(frame)
            eventos = gerar_eventos(df_anterior, df_atual)

            if eventos:
                enviar_eventos(eventos)

            df_anterior = df_atual.copy()
            ultimo_processamento = tempo_atual

        if cv2.waitKey(1) & 0xFF == ord("q"):
            break

    cv2.destroyAllWindows()


if __name__ == "__main__":
    main()
```

> **Nota de estado:** durante o desenvolvimento, o `main()` esteve temporariamente configurado para **chamar `rodar_pipeline_treinamento()` e retornar** (em vez de rodar a inferência), para permitir testar o treinamento isoladamente. Alterne entre os dois modos comentando/descomentando o bloco indicado. Quando o arquivo `treinamentos/modelo_produtos/weights/best.pt` já existir, use o modo de inferência (padrão acima).

---

## 4. Passo a passo operacional (T01–T04)

### T01 — Hardware e rede
1. Grave o firmware do ESP32-CAM (servidor de stream MJPEG na porta 81, endpoint `/stream`).
2. Ligue o ESP32-CAM na mesma rede Wi-Fi do notebook e anote o IP mostrado no Serial Monitor.
3. Atualize `ESP32_STREAM_URL` em `utils/config.py`.
4. Rode:
   ```powershell
   cd D:\TCC2026
   .\Python_3_11\python.exe .\projeto\main.py
   ```
   Espera-se log de conexão e frames sendo processados (ou salvos, dependendo do modo ativo).

### T02 — Construção do dataset e treinamento
1. Capture/gere imagens em `dataset_fotos/` (frames do ESP32-CAM).
2. Anote as imagens no **LabelMe** (não o LabelImg):
   ```powershell
   cd D:\TCC2026
   .\Python_3_11\python.exe -m labelme
   ```
   - "Open Dir" → selecione `dataset_fotos`.
   - Desenhe retângulos e rotule com as classes: `creme_leite`, `gelatina`, `cha`, `mao`.
   - Salve o JSON de cada imagem em `dataset_labels/`.
   - Uma imagem pode ter várias instâncias/classes ao mesmo tempo.
3. Habilite o treinamento em `main.py` (descomente `rodar_pipeline_treinamento()` e `return`) e rode:
   ```powershell
   cd D:\TCC2026
   .\Python_3_11\python.exe .\projeto\main.py
   ```
   Isso converte os JSON para `.txt` YOLO, monta `dataset/`, gera `data.yaml` e treina o `yolov8n.pt` por 50 épocas, salvando em `treinamentos/modelo_produtos/weights/best.pt`.

### T03 — Validação com dataset externo (opcional, reversível)
Se o dataset próprio ainda não estiver pronto, é possível validar todo o pipeline de código com um dataset externo já estruturado no formato YOLO (ex.: `D:\yolo\data.yaml` com `images/`, `labels/` e classes definidas):
1. Em `utils/config.py`, defina `USE_EXTERNAL_VALIDATION_DATASET = True` e aponte `EXTERNAL_VALIDATION_DATASET_YAML` para o `data.yaml` externo.
2. Rode o pipeline normalmente (`rodar_pipeline_treinamento()`), que vai automaticamente pular a etapa de LabelMe/conversão e treinar direto com o dataset externo.
3. Quando o dataset próprio estiver pronto, **reverta** para `USE_EXTERNAL_VALIDATION_DATASET = False` — nenhuma outra mudança de código é necessária.

### T04 — Inferência e eventos em produção
1. Garanta que `treinamentos/modelo_produtos/weights/best.pt` existe.
2. Comente novamente a chamada de treino em `main.py` (volte ao modo de inferência).
3. Configure `API_ENDPOINT` em `utils/config.py` para o backend real.
4. Rode `main.py`: o sistema vai capturar vídeo, detectar produtos/mão, comparar com o frame anterior, gerar eventos (`inserido`, `retirado`, `interacao_mao`) e enviá-los via `POST` para a API.

---

## 5. Problemas conhecidos e correções já validadas (não repetir os mesmos erros)

| Sintoma | Causa raiz | Correção aplicada |
|---|---|---|
| `ModuleNotFoundError: No module named 'controllers'` ao rodar `main.py` da raiz | pasta do projeto não estava no `sys.path`; faltavam `__init__.py` | adicionar `__init__.py` vazio em `controllers/`, `services/`, `utils/`; inserir `PROJ_DIR` no `sys.path` no topo de `main.py` |
| LabelImg fecha sozinho ao desenhar a bounding box (`TypeError: drawLine(... float ...)`) | incompatibilidade Qt5/labelImg 1.8.6 no Windows | abandonar o LabelImg; migrar para `labelme` (estável) + conversão própria JSON→YOLO |
| `python -m labelImg` falha com `No module named labelImg.__main__` | o pacote `labelImg` não expõe entry point `__main__` | usar `Scripts\labelImg.exe` diretamente (mas de qualquer forma, prefira `labelme`) |
| `FileNotFoundError: Nenhum JSON do LabelMe foi encontrado` | pasta `dataset_labels` vazia — usuário ainda não salvou anotações | anotar no LabelMe e salvar os `.json` em `dataset_labels` antes de rodar o treino |
| `torch.cuda.is_available()` retorna `False` mesmo com GPU NVIDIA presente (`nvidia-smi` OK) | PyTorch instalado na build CPU-only (padrão do `pip install ultralytics`) | reinstalar `torch`/`torchvision` explicitamente com `--index-url https://download.pytorch.org/whl/cu121` |
| `ModuleNotFoundError: No module named 'sympy.utilities'` ao iniciar treino do Ultralytics | instalação do `sympy` corrompida/parcial no `site-packages` (pastas residuais `~ympy`, `.deleteme` travado) | remover manualmente `site-packages/sympy`, `sympy-*.dist-info` e qualquer pasta `~*` órfã, depois reinstalar com `pip install --no-cache-dir --force-reinstall --no-deps sympy==1.13.1 mpmath==1.3.0`; se o pip falhar com `WinError 3/5` ao renomear `.exe` para `.deleteme`, feche todos os processos Python/terminal que estejam usando o ambiente antes de tentar de novo |
| Dataset externo (`D:\yolo`) treina mas emite `ignoring corrupt image/label: labels mix segment and detection rows` | dataset de terceiros mistura anotações de segmentação e detecção | aceitável apenas para teste de validação de código; não usar como dataset final do TCC sem limpeza |

---

## 6. `.agent.md` (persona do Copilot para este projeto)

Recrie em `D:\TCC2026\.agent.md` com o seguinte conteúdo (persona focada em implementação e correção de código, não em consultoria acadêmica genérica):

```markdown
---
name: tcc-vision-ai-agent
description: Agente especializado em implementar e corrigir código de um projeto de TCC de visão computacional com ESP32-CAM, YOLOv8, processamento local, eventos em pandas e integração HTTP.
model: GPT-4.1
---

# Persona
Sou um agente especializado em implementar, corrigir e evoluir o código de um sistema de visão computacional para inventário automatizado em contexto acadêmico (TCC). Minha função principal é agir como parceiro de desenvolvimento: escrevo, depuro e valido código real do projeto, priorizando execução e evidência sobre explicações teóricas.

# Escopo de trabalho
- scripts Python para captura, decodificação e processamento de vídeo
- pipeline de anotação (LabelMe) e conversão de dataset (JSON → YOLO)
- treinamento e inferência com `ultralytics` (YOLOv8) e `OpenCV`
- regras de negócio de inventário com `pandas` e IoU
- integração HTTP com `requests` (envio de eventos para API)
- depuração e validação end-to-end do fluxo local

# Preferências de execução
- Python simples, modular e imperativo, seguindo a estrutura `projeto/{controllers,services,utils}`
- manter a arquitetura em camadas: câmera → visão → eventos → API
- validar com execução real sempre que possível; não simular comportamento
- corrigir a causa raiz, com mudanças pequenas e específicas

# Regras de atuação
- reproduzir o sintoma antes de alterar código
- evitar refatorações grandes sem necessidade explícita
- não introduzir dependências novas sem justificativa clara
- manter nomes e convenções já usadas no projeto (em português, estilo do código existente)
- reportar exatamente o que foi validado por execução, nunca assumir sucesso sem evidência de terminal
```

---

## 7. Checklist de reconstrução (ordem recomendada)

1. [ ] Criar a estrutura de pastas descrita na seção 1.
2. [ ] Extrair a distribuição embeddable do Python 3.11 em `Python_3_11/` e instalar `pip`.
3. [ ] Instalar as dependências da seção 2.2 (com atenção especial a `torch` CUDA e `sympy==1.13.1`).
4. [ ] Criar os 4 arquivos `__init__.py` vazios (seção 3.1).
5. [ ] Criar `utils/config.py` (seção 3.2) e ajustar `ESP32_STREAM_URL`.
6. [ ] Criar `services/camera_service.py`, `services/vision_service.py`, `services/event_service.py` (seções 3.3–3.5).
7. [ ] Criar `services/annotation_converter.py` e `services/training_service.py` (seções 3.6–3.7).
8. [ ] Criar `controllers/api_controller.py` (seção 3.8).
9. [ ] Criar `main.py` (seção 3.9).
10. [ ] Recriar `.agent.md` (seção 6), se desejado.
11. [ ] Seguir o passo a passo T01→T04 (seção 4) para validar hardware, dataset, treino e inferência.
12. [ ] Consultar a tabela da seção 5 antes de tentar resolver qualquer erro já mapeado.

---

## 8. Referência cruzada com o TCC

Este manual é consistente com o capítulo 3 (Procedimentos Metodológicos) e capítulo 4 (Resultados) do documento `Controle Autônomo de Inventário`:
- 3.2.1 Telemetria / 3.2.2 Tratamento de Ruídos → correspondem à aquisição de imagem e peso (peso ainda pendente de implementação no código — apenas visão computacional foi implementada até o momento da perda do disco).
- 3.2.3 Transmissão de Borda → `services/camera_service.py`.
- 3.2.4/3.2.5 Visão Computacional / Processamento da rede neural → `services/vision_service.py`.
- 3.2.6 Fusão Multimodal → parcialmente coberto por `event_service.py` (fusão classe+IoU mão↔produto); a fusão com célula de carga (peso) é trabalho futuro, não implementado em código ainda.
- 3.2.7 Roteamento via API → `controllers/api_controller.py`.
- 4.3.2 Construção do Dataset e Anotação com LabelMe → seção 3.6/T02 deste manual.
- 4.3.3 Conversão do Dataset do LabelMe para Formato YOLO → `services/annotation_converter.py`.
- 4.3.4 Treinamento do Modelo YOLOv8 → `services/training_service.py`.
- 4.3.5 Inferência em Tempo Real e Interpretação dos Eventos → `vision_service.py` + `event_service.py` + `main.py`.

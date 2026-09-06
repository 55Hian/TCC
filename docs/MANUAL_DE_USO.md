# Manual de Instruções de Uso — Controle Autônomo de Inventário

Para entender módulos, dependências, fluxos e pontos de extensão, consulte o [Guia do código e da arquitetura](GUIA_DO_CODIGO.md).

Este manual descreve como usar o sistema neste workspace (`G:\000. TCC`), reorganizado em backend FastAPI + frontend web. Para o histórico de como o projeto foi originalmente reconstruído (estrutura antiga em `projeto/`), veja [MANUAL_RECONSTRUCAO.md](MANUAL_RECONSTRUCAO.md).

---

## 1. Pré-requisitos

- Ambiente virtual `.venv` já criado na raiz do projeto, com todas as dependências de [requirements.txt](../requirements.txt) instaladas.
- ESP32-CAM ligada na mesma rede, transmitindo em:
  ```text
  http://192.168.15.59:81/stream
  ```
  (configurável em `ESP32_STREAM_URL`, ver seção 2).

Sempre execute os comandos a partir da raiz do workspace:

```powershell
cd "G:\000. TCC"
```

---

## 2. Subir o sistema (backend + interface web)

```powershell
.\.venv\Scripts\python.exe -m uvicorn main:app --app-dir backend\app --port 8000
```

Depois abra **http://localhost:8000** no navegador. A interface tem 4 abas:

| Aba | Para que serve |
|---|---|
| Monitoramento | Ver o stream e os eventos em tempo real via WebSocket; o detector atual gera `interacao_mao`, e a API tamb?m aceita eventos inseridos manualmente; botões iniciar/parar |
| Treino | Escolher um dos 4 modelos-base (`models/pretrained/`), configurar épocas/imgsz/fração e disparar o treino; acompanhar status |
| Dataset | Capturar novos frames da câmera, abrir o LabelMe para anotar, ver a galeria com status anotado/pendente |
| Experimentos | Comparar resultados (`results.png`, `results.csv`) de cada treino já rodado |

> Sem autenticação — não exponha esse servidor fora da rede local.

---

## 3. Configuração central (`backend/app/core/config.py`)

| Campo | Função |
|---|---|
| `ESP32_STREAM_URL` | Endereço do stream MJPEG da câmera |
| `API_ENDPOINT` | Endpoint HTTP para eventos externos (compat.) |
| `CLASSES` | Classes do dataset próprio do TCC (`creme_leite`, `gelatina`, `cha`, `mao`) |
| `EXTERNAL_CLASSES` | Classes do dataset externo de validação (`data/external_validation/`, 10 produtos) |
| `USE_EXTERNAL_VALIDATION_DATASET` | `True` = usa o dataset externo; `False` = usa o dataset próprio |
| `BASE_MODEL` | Modelo-base usado por padrão no treino (um dos 4 em `models/pretrained/`) |
| `MODEL_PATH` | Caminho do modelo treinado usado na inferência (`experiments/treinamentos/modelo_produtos/weights/best.pt`) |
| `RAW_FRAMES_DIR`, `LABELME_ANNOTATIONS_DIR`, `YOLO_LABELS_DIR`, `DATASET_DIR` | Pastas do pipeline de dataset (`data/`) |

Todos os campos podem ser sobrescritos sem editar código, via variáveis de ambiente com prefixo `TCC_` (arquivo `.env` na raiz do repo), ex.:

```text
TCC_ESP32_STREAM_URL=http://192.168.15.60:81/stream
TCC_USE_EXTERNAL_VALIDATION_DATASET=true
```

---

## 4. Capturar frames e anotar (via interface ou manual)

**Pela interface:** aba **Dataset** → formulário "Captura de frames" (intervalo/máx. frames) → botão "Abrir LabelMe para anotar" (abre a janela do LabelMe já apontando para `data/raw_frames`, salvando os JSONs em `data/labelme_annotations`).

**Manual (linha de comando):**

```powershell
$env:PYTHONPATH = "$PWD\backend\app"
.\.venv\Scripts\python.exe .\backend\app\capturar_frames.py --intervalo 2 --max-frames 100
.\.venv\Scripts\python.exe -m labelme data\raw_frames --output data\labelme_annotations
```

Use exatamente estas classes ao anotar: `creme_leite`, `gelatina`, `cha`, `mao`. Sempre que houver uma mão interagindo com um produto, anote também a caixa `mao`.

---

## 5. Treinar o modelo

**Pela interface:** aba **Treino** → escolha o modelo-base entre os 4 disponíveis, ajuste épocas/imgsz/fração → "Iniciar treino". O status é acompanhado na própria aba (`ocioso` / `rodando` / `concluido` / `erro`).

**Manual (linha de comando):**

```powershell
$env:PYTHONPATH = "$PWD\backend\app"
.\.venv\Scripts\python.exe -c "from services.training_service import rodar_pipeline_treinamento; rodar_pipeline_treinamento(epochs=50, imgsz=640, fraction=1.0)"
```

O pipeline converte os JSONs para YOLO (`data/yolo_labels/`), monta `data/dataset/images|labels/{train,val}`, gera `data/dataset/data.yaml` e treina o modelo. O resultado é salvo em `experiments/treinamentos/modelo_produtos/weights/best.pt` — caminho lido por `MODEL_PATH` e usado na inferência.

> **Aviso:** um modelo treinado com `fraction` baixo ou poucas épocas é apenas um teste de pipeline, não um modelo confiável. Para uso real, treine com `fraction=1.0` e um número adequado de épocas.
> **GPU de 4GB (GTX 1650):** nunca rode dois treinos ao mesmo tempo; batch=4 (modelos S) / batch=2 (modelos M) cabem na VRAM.

---

## 6. Monitoramento sem interface (modo console, avançado)

```powershell
$env:PYTHONPATH = "$PWD\backend\app"
.\.venv\Scripts\python.exe .\backend\app\cli_monitor.py
```

Abre uma janela OpenCV local, roda o YOLO a cada `INTERVALO_PROCESSAMENTO` segundos e imprime os eventos no console (não passa pela API/WebSocket). Para encerrar, pressione `Q` com a janela em foco.

---

## 7. Rodar os testes automatizados

```powershell
$env:PYTHONPATH = "$PWD\backend\app"
.\.venv\Scripts\python.exe -m pytest backend\app\tests -v
```

Cobre a API FastAPI (`test_api.py`, via `TestClient`, incluindo WebSocket) e a captura de frames (`test_capturar_frames.py`), sem depender da câmera real.

---

## 8. Estrutura de pastas relevante

```text
G:\000. TCC\
├── .venv/                       # ambiente virtual com todas as dependências
├── backend/app/
│   ├── main.py                  # entrypoint FastAPI (API + serve o frontend)
│   ├── cli_monitor.py           # monitoramento via console (OpenCV), sem API
│   ├── capturar_frames.py       # captura automática de frames
│   ├── worker.py                # loop de monitoramento em background (usado pela API)
│   ├── core/{config,state}.py   # configuração central (pydantic-settings) + estado em memória
│   ├── routers/                 # eventos, stream, treino, dataset, modelos
│   ├── controllers/             # api_controller.py
│   ├── services/                # camera, vision, event, annotation_converter, training
│   └── tests/                   # testes automatizados
├── frontend/                    # HTML/CSS/JS puro, servido pelo FastAPI
├── models/pretrained/            # os 4 modelos-base (yolov8n, yolo12n, yolo26s, yolo26m)
├── experiments/treinamentos/     # pesos treinados (best.pt) e métricas de cada experimento
├── data/
│   ├── raw_frames/               # imagens capturadas da ESP32-CAM
│   ├── labelme_annotations/      # JSONs do LabelMe
│   ├── yolo_labels/              # .txt convertidos (gerado automaticamente)
│   ├── dataset/                  # dataset final YOLO (gerado automaticamente)
│   └── external_validation/      # dataset externo de validação (Roboflow, 10 classes; nao versionado)
├── scripts/experimento_yolo26.py # comparação manual entre os 4 modelos
├── docs/                         # este manual + manual de reconstrução
└── requirements.txt
```

---

## 9. Problemas conhecidos

| Sintoma | Causa | Solução |
|---|---|---|
| `ImportError: DLL load failed while importing QtCore: Não foi possível encontrar o procedimento especificado` ao rodar `python -m labelme` | `PySide6` na versão mais recente (ex.: `6.11.2`) é incompatível com este build do Windows | Instalar `PySide6==6.8.3` (`pip install "PySide6==6.8.3"`), já fixado em `requirements.txt` |
| `torch.cuda.is_available()` retorna `False` | PyTorch instalado é CPU-only | Reinstalar com `--index-url https://download.pytorch.org/whl/cu121` se houver GPU NVIDIA |
| `ignoring corrupt image/label: labels mix segment and detection rows` durante treino no dataset externo | Dataset externo mistura anotações de segmentação e detecção | Esperado; o YOLO usa apenas as caixas. Não usar esse dataset como final do TCC |
| `FileNotFoundError` ao treinar dataset próprio | `data/labelme_annotations/` vazio | Anote as imagens no LabelMe antes de treinar (seção 4) |
| Modelo não detecta nada | Treino de teste com `fraction` baixo ou poucas épocas | Treinar com `fraction=1.0` e mais épocas |
| `/api/stream` fica sem exibir vídeo | ESP32-CAM inacessível; `camera_service` tenta reconectar indefinidamente sem lançar erro | Verificar rede/IP da câmera; a página não trava, só fica sem imagem |

## 10. Experimentos e validação da entrega

Na raiz do repositório, confira os caminhos sem iniciar um treino:

```powershell
.\.venv\Scripts\python.exe scripts/experimento_yolo26.py --help
.\.venv\Scripts\python.exe scripts/experimento_yolo26.py yolo26s.pt comparativo_novo 4 2 --check
```

Para executar as 50 épocas, remova `--check`. Use batch 2 para o modelo M e confirme que nenhum treino está rodando na interface ou em outro terminal. O script usa GPU `device=0`. O `path` de `data/dataset/data.yaml` deve apontar para a pasta absoluta atual; ao mudar de computador, regenere pelo pipeline ou ajuste esse campo.

A API retorna 201 ao criar eventos. Os testes ficam em `backend/app/tests`, e o comando de inicializa??o acima resolve os imports atuais. O treino e a captura exibem status; a interface ainda não possui barra de progresso por época e o total capturado só é atualizado ao concluir. Atualize a p?gina para recarregar a galeria ap?s capturar/anotar.

Veja os resultados e pend?ncias no [checklist da Fase 6](VALIDACAO_FASE_6.md).

## Camera compartilhada (correcao de concorrencia)

O backend abre uma unica conexao HTTP com a ESP32-CAM quando o primeiro consumidor inicia. Proxy MJPEG, monitoramento e captura pela API recebem copias do ultimo frame, sem disputar conexoes. A conexao permanece disponivel ate encerrar o backend. Consumidores lentos pulam frames; nao acumulam uma fila de imagens antigas.

Execute apenas um processo do servidor:

```powershell
.\.venv\Scripts\python.exe -m uvicorn main:app --app-dir backend/app --port 8000 --workers 1
```

Reinicie o servidor depois de atualizar o codigo. Nao mantenha outro servidor, script de captura/CLI ou navegador conectado diretamente ao IP da camera enquanto usa o backend. Os scripts desktop ainda acessam a camera diretamente; prefira a captura pela aba Dataset durante o monitoramento.

`GET /api/monitoramento/status` agora inclui `camera.status`, `camera.erro`, `camera.idade_frame_segundos`, `camera.frames_recebidos` e `idade_processamento_segundos`. O monitoramento informa `aguardando_camera` quando nao recebe novos frames. A imagem fica oculta na interface quando a camera nao esta recebendo. Frames com mais de tres segundos nao sao entregues aos consumidores; a captura encerra com erro depois de 15 segundos sem novos frames. O leitor tenta reconectar automaticamente. Parar o monitoramento cancela a espera por frames sem precisar receber outra imagem.


### LabelMe: janela ausente apos listar imagens

Diagnostico em 2026-09-06: o LabelMe aguardava um dialogo de erro durante a carga inicial, antes de mostrar a janela principal. Corrigidas 95 referencias imagePath nos JSONs para ../raw_frames/arquivo.jpg; todas as anotacoes foram lidas pelo proprio LabelMe sem erro. O endpoint de anotacao agora verifica e repara referencias quebradas quando encontra uma unica imagem correspondente, antes de iniciar o processo. Classes e caixas permanecem preservadas.

# Manual de Instruções de Uso — Controle Autônomo de Inventário

Este manual descreve como usar o sistema já reconstruído e configurado neste workspace (`G:\000. TCC`). Para o histórico de como o projeto foi reconstruído, veja [MANUAL_RECONSTRUCAO.md](MANUAL_RECONSTRUCAO.md).

---

## 1. Pré-requisitos

- Ambiente virtual `.venv` já criado na raiz do projeto, com todas as dependências de [requirements.txt](requirements.txt) instaladas.
- ESP32-CAM ligada na mesma rede, transmitindo em:
  ```text
  http://192.168.15.59:81/stream
  ```
  (configurável em `ESP32_STREAM_URL`, ver seção 2).

Sempre execute os comandos a partir da raiz do workspace:

```powershell
cd "G:\000. TCC"
$env:PYTHONPATH = "$PWD\projeto"
```

Todos os exemplos abaixo assumem que essas duas linhas já foram executadas no terminal.

---

## 2. Configuração central (`projeto/utils/config.py`)

| Variável | Função |
|---|---|
| `ESP32_STREAM_URL` | Endereço do stream MJPEG da câmera |
| `API_ENDPOINT` | Backend HTTP que recebe os eventos de inventário |
| `CLASSES` | Classes do dataset próprio do TCC (`creme_leite`, `gelatina`, `cha`, `mao`) |
| `EXTERNAL_CLASSES` | Classes do dataset externo de validação (`yolo/`, 10 produtos) |
| `USE_EXTERNAL_VALIDATION_DATASET` | `True` = usa o dataset externo `yolo/`; `False` = usa o dataset próprio |
| `MODEL_PATH` | Caminho do modelo treinado usado na inferência |

> **Estado atual:** `USE_EXTERNAL_VALIDATION_DATASET = True`. O sistema está apontando para o dataset externo em `G:\000. TCC\yolo`. Para treinar com suas próprias imagens, mude para `False` (ver seção 5).

---

## 3. Capturar frames da ESP32-CAM

Script: [projeto/capturar_frames.py](projeto/capturar_frames.py)

Captura frames **automaticamente por intervalo de tempo** (não precisa apertar tecla) e salva em `dataset_fotos/`.

```powershell
.\.venv\Scripts\python.exe .\projeto\capturar_frames.py --intervalo 2 --max-frames 100
```

| Parâmetro | Padrão | Descrição |
|---|---|---|
| `--saida` | `dataset_fotos` | Pasta onde os JPEGs são salvos |
| `--intervalo` | `2.0` | Segundos entre cada captura automática |
| `--max-frames` | `0` (ilimitado) | Encerra sozinho ao atingir esse número de frames |
| `--sem-janela` | desligado | Roda sem abrir janela (modo headless) |

Para encerrar antes do limite: pressione `Q` com a janela em foco, ou `Ctrl+C` no terminal.

---

## 4. Anotar as imagens no LabelMe

Não use LabelImg (instável neste ambiente). O fluxo oficial é **LabelMe**.

```powershell
.\.venv\Scripts\python.exe -m labelme
```

1. **Open Dir** → selecione `dataset_fotos`.
2. Desenhe retângulos em todos os objetos visíveis.
3. Use exatamente estas classes (definidas em `CLASSES`):
   ```text
   creme_leite
   gelatina
   cha
   mao
   ```
4. Salve cada JSON em `dataset_labels/`.
5. Sempre que houver uma mão interagindo com um produto, anote também a caixa `mao`.

---

## 5. Treinar o modelo

### 5.1. Com o dataset próprio (recomendado para o TCC)

1. Em `projeto/utils/config.py`, defina:
   ```python
   USE_EXTERNAL_VALIDATION_DATASET = False
   ```
2. Garanta que existam JSONs em `dataset_labels/` (gerados no passo anterior).
3. Execute:
   ```powershell
   .\.venv\Scripts\python.exe -c "from services.training_service import rodar_pipeline_treinamento; rodar_pipeline_treinamento(epochs=50, imgsz=640, fraction=1.0)"
   ```

O pipeline converte os JSONs para YOLO (`labels_yolo/`), monta `dataset/images|labels/{train,val}`, gera `dataset/data.yaml` e treina o modelo.

### 5.2. Com o dataset externo (`yolo/`, validação de pipeline)

Mantenha `USE_EXTERNAL_VALIDATION_DATASET = True` e execute o mesmo comando acima. Nesse modo, o treino usa diretamente `yolo/data.yaml` (10 classes de produtos), sem passar por LabelMe.

Use `fraction` para treinos rápidos de teste (ex.: `fraction=0.01`) e `fraction=1.0` para um treino completo.

### 5.3. Resultado

O modelo treinado é salvo em:

```text
treinamentos/modelo_produtos/weights/best.pt
```

Esse é o caminho lido por `MODEL_PATH` e usado na inferência.

> **Aviso:** um modelo treinado com `fraction` baixo ou poucas épocas é apenas um teste de pipeline, não um modelo confiável. Para uso real, treine com `fraction=1.0` e um número adequado de épocas.

---

## 6. Executar o monitoramento (inferência + eventos + API)

```powershell
.\.venv\Scripts\python.exe .\projeto\main.py
```

O que acontece:

1. Conecta na ESP32-CAM e abre a janela **Monitoramento de Estoque**.
2. A cada `INTERVALO_PROCESSAMENTO` segundos (padrão `0.05s`, ~12 detecções/segundo neste hardware), roda o YOLO no frame atual.
3. Compara com o frame anterior e gera eventos: `inserido`, `retirado`, `interacao_mao`.
4. Envia cada evento via `POST` para `API_ENDPOINT`.

Para encerrar: pressione `Q` com a janela em foco.

Se o backend em `API_ENDPOINT` não estiver ativo, o sistema continua rodando normalmente e apenas registra `[API_ERRO]` no console.

---

## 7. Rodar os testes automatizados

```powershell
.\.venv\Scripts\python.exe -m pytest projeto\tests -v
```

Os testes atuais cobrem o módulo de captura de frames ([projeto/tests/test_capturar_frames.py](projeto/tests/test_capturar_frames.py)) com casos unitários e mockados, sem depender da câmera real.

---

## 8. Estrutura de pastas relevante

```text
G:\000. TCC\
├── .venv/                  # ambiente virtual com todas as dependências
├── projeto/
│   ├── main.py             # inferência + eventos + API
│   ├── capturar_frames.py  # captura automática de frames
│   ├── controllers/        # api_controller.py
│   ├── services/           # camera, vision, event, annotation_converter, training
│   ├── utils/config.py     # configuração central
│   └── tests/              # testes automatizados
├── dataset_fotos/          # imagens capturadas da ESP32-CAM
├── dataset_labels/         # JSONs do LabelMe
├── labels_yolo/            # .txt convertidos (gerado automaticamente)
├── dataset/                # dataset final YOLO (gerado automaticamente)
├── treinamentos/           # pesos treinados (best.pt)
├── yolo/                   # dataset externo de validação (Roboflow, 10 classes)
└── requirements.txt
```

---

## 9. Problemas conhecidos

| Sintoma | Causa | Solução |
|---|---|---|
| `ImportError: DLL load failed while importing QtCore: Não foi possível encontrar o procedimento especificado` ao rodar `python -m labelme` | `PySide6` na versão mais recente (ex.: `6.11.2`) é incompatível com este build do Windows | Instalar `PySide6==6.8.3` (`pip install "PySide6==6.8.3"`), já fixado em `requirements.txt` |
| `torch.cuda.is_available()` retorna `False` | PyTorch instalado é CPU-only | Reinstalar com `--index-url https://download.pytorch.org/whl/cu121` se houver GPU NVIDIA |
| `ignoring corrupt image/label: labels mix segment and detection rows` durante treino no dataset `yolo/` | Dataset externo mistura anotações de segmentação e detecção | Esperado; o YOLO usa apenas as caixas. Não usar esse dataset como final do TCC |
| `FileNotFoundError` ao treinar dataset próprio | `dataset_labels/` vazio | Anote as imagens no LabelMe antes de treinar (seção 4) |
| Modelo não detecta nada | Treino de teste com `fraction` baixo ou poucas épocas | Treinar com `fraction=1.0` e mais épocas |

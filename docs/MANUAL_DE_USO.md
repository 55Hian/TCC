# Manual de Uso

Este manual descreve como instalar, configurar e operar o **Controle Autônomo de Inventário**, pela interface, linha de comando, Python e API. Revisão: 08/09/2026. Para explicações internas de funções e métodos, consulte o [Manual Técnico](MANUAL_TECNICO.md).

## Sumário

1. [O que o sistema oferece](#1-o-que-o-sistema-oferece)
2. [Preparar o ambiente](#2-preparar-o-ambiente)
3. [Primeira execução](#3-primeira-execução)
4. [Configurações](#4-configurações)
5. [Usar a interface](#5-usar-a-interface)
6. [Capturar e anotar o dataset](#6-capturar-e-anotar-o-dataset)
7. [Treinar e administrar os modelos](#7-treinar-e-administrar-os-modelos)
8. [Executar pelo terminal e por Python](#8-executar-pelo-terminal-e-por-python)
9. [Usar a API e o WebSocket](#9-usar-a-api-e-o-websocket)
10. [Comparar interações em vídeos](#10-comparar-interações-em-vídeos)
11. [Executar benchmarks](#11-executar-benchmarks)
12. [Diagnóstico e manutenção](#12-diagnóstico-e-manutenção)

## 1. O que o sistema oferece

- Vídeo ao vivo da ESP32-CAM no navegador.
- Reconhecimento de produtos por YOLO.
- Pontos da mão com MediaPipe e confirmação temporal de interação com produtos.
- Captura de imagens e abertura do LabelMe para anotação.
- Treinamento da arquitetura escolhida e publicação local de seus pesos.
- Consulta de resultados, eventos e modelos pela API.
- Monitor visual OpenCV e replay de vídeos para diagnóstico.

Não há atualização automática de quantidade em estoque. O evento interacao_mao sinaliza contato/manipulação provável; não comprova que um produto foi retirado. Os eventos ficam em memória e são perdidos ao reiniciar o backend.

A janela da CLI mostra caixas, IDs e dedos numerados. O vídeo do navegador mostra a câmera sem essas marcações. Atualmente a CLI imprime eventos, mas **não os envia ao backend**, porque o POST está comentado no controller. Para ver eventos no navegador, inicie o monitoramento da própria interface.

## 2. Preparar o ambiente

### 2.1 Requisitos

O ambiente usado no projeto é Windows/PowerShell, com Python 3.13. A instalação existente foi testada com Python 3.13.9. É necessário ter:

- Câmera ESP32-CAM já configurada para fornecer stream MJPEG e acessível na rede.
- Python e ambiente virtual do projeto.
- Pesos genéricos em models/pretrained e treinados em models/trained.
- Interface gráfica local para LabelMe e janelas OpenCV.
- GPU CUDA opcional para o monitor/pipeline normal; o script de benchmark exige CUDA.

A configuração/gravação do firmware da ESP32-CAM não é implementada neste repositório. A aplicação consome uma URL já operacional.

### 2.2 Diretório de trabalho

Todos os comandos abaixo partem da raiz, que neste workspace é:

```powershell
Set-Location -LiteralPath 'G:\000. TCC'
```

Em outro computador, use a pasta em que clonou/copiu o projeto. Não é necessário manter a mesma letra de unidade para os caminhos calculados a partir de BASE_DIR, mas YAMLs de datasets e metadados históricos podem conter caminhos absolutos que precisam ser conferidos.

### 2.3 Ambiente virtual e dependências

Se .venv já existe e funciona, use-o. Para uma instalação nova, com o Python desejado selecionado no terminal:

```powershell
python --version
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt -r requirements-hands.txt
.\.venv\Scripts\python.exe scripts/setup_hands.py
```

Usar o executável completo evita depender de ativação do PowerShell. Não há npm install ou build de frontend.

requirements.txt instala as bibliotecas de API, visão, treinamento, anotação e testes. requirements-hands.txt fixa MediaPipe 0.10.35 e OpenCV contrib 5.0.0.93. O setup baixa o modelo de mão em models/hand_landmarker.task; se já existir, não o substitui.

Ultralytics exige opencv-python e MediaPipe exige opencv-contrib-python; ambos fornecem cv2. O ambiente validado usou a mesma versão 5.0.0.93 nas duas distribuições. Se reinstalar/atualizar, confira versões e imports. As demais dependências não estão todas fixadas: instalar em outro momento pode produzir versões diferentes.

Verifique os imports:

```powershell
.\.venv\Scripts\python.exe -c "import cv2, torch, mediapipe, ultralytics, fastapi; print('Imports OK'); print('CUDA:', torch.cuda.is_available())"
```

CUDA false não impede o pipeline normal de usar CPU, mas impede o benchmark atual. Ter uma GPU NVIDIA não garante que o pacote PyTorch instalado tenha suporte CUDA compatível. Se precisar instalar outra build de PyTorch, use uma compatível com seu driver e valide novamente; não altere o ambiente durante um treino em execução.

### 2.4 Arquivos que precisam existir

| Uso | Arquivos |
|---|---|
| Inferência | models/trained/<MODELO_ATIVO>/best.pt |
| Novo treinamento | models/pretrained/<MODELO_ATIVO>.pt e dados anotados |
| Pontos da mão | models/hand_landmarker.task e requirements-hands instalados |
| Dataset próprio | data/raw_frames e data/labelme_annotations |
| Comparativo reproduzível | data/dataset preparado e quatro pesos genéricos |

O projeto contém quatro arquiteturas: yolov8n, yolo12n, yolo26s e yolo26m. Os pesos treinados foram importados do benchmark corrigido. Não substitua best.pt treinado pelo arquivo genérico: o genérico não aprendeu automaticamente as classes do projeto.

## 3. Primeira execução

### 3.1 Conferir câmera e modelo

Abra [config.py](../backend/app/core/config.py) e confira ESP32_STREAM_URL e MODELO_ATIVO. O padrão de câmera é http://192.168.15.59:81/stream; ajuste se o IP real for outro.

Para mudar a arquitetura, altere **somente o valor de MODELO_ATIVO**, mantendo a declaração e suas opções válidas. Exemplo de valor: yolo26m. O padrão atual é yolo12n.

Também é possível criar .env na raiz:

```dotenv
TCC_ESP32_STREAM_URL=http://192.168.15.59:81/stream
TCC_MODELO_ATIVO=yolo12n
```

Se TCC_MODELO_ATIVO existir no .env ou no ambiente, ele prevalece sobre o padrão de config.py. Para controlar exclusivamente pelo código, remova esse override.

### 3.2 Iniciar servidor

```powershell
.\.venv\Scripts\python.exe -m uvicorn main:app --app-dir backend/app --host 127.0.0.1 --port 8000 --workers 1
```

Abra http://localhost:8000. Use apenas um worker: câmera, clientes e estados são compartilhados em memória dentro de um processo. Reiniciar servidor durante uma captura/treino interrompe suas threads.

Swagger: http://localhost:8000/docs. Referência alternativa: http://localhost:8000/redoc. Esquema: http://localhost:8000/openapi.json.

A URL /docs exibe a documentação interativa da API, não a pasta docs dos manuais.

### 3.3 Verificação inicial

1. Abra Monitoramento e clique Iniciar monitoramento.
2. Confira no status a câmera recebendo e o modelo esperado.
3. Aproxime a mão de um produto detectável por tempo suficiente.
4. Observe um evento na lista.
5. Clique Parar ao terminar. Para encerrar o servidor, use Ctrl+C no terminal.

Exibir vídeo não prova que a inferência está funcionando: câmera e processamento têm estados próprios. Se o modelo falhar, o stream ainda pode continuar aberto pelo navegador.

## 4. Configurações

As configurações ficam em config.py, com prefixo TCC_ para ambiente/.env. Reinicie backend e CLI após editar. Caminhos abaixo são relativos à raiz na tabela, mas o padrão do código produz caminhos absolutos via BASE_DIR.

### 4.1 Câmera, classes e modelo

| Campo | Padrão | Como usar |
|---|---|---|
| ESP32_STREAM_URL | http://192.168.15.59:81/stream | Endereço MJPEG da câmera |
| API_ENDPOINT | http://localhost:8000/api/eventos | Destino previsto do controller da CLI; POST atualmente desativado no código |
| MODELO_ATIVO | yolo12n | yolov8n, yolo12n, yolo26s ou yolo26m; escolhe treino e inferência |
| CLASSES | creme_leite, gelatina, cha, mao | Ordem dos IDs do dataset próprio; deve corresponder aos pesos |
| EXTERNAL_CLASSES | DUCOCO, coca_cola, creme_nestle, extrato_turma_monica, garrafa_agua, margarina_dorianna, pasta_colgate, sabonete_dove, sardinha_coqueiro, todinho | Classes do modo externo, na ordem declarada |
| INTERVALO_PROCESSAMENTO | 0.05 s | Intervalo mínimo entre inícios de inferência; não garante 20 FPS |

Listas em .env usam JSON, por exemplo `TCC_CLASSES=["creme_leite","gelatina","cha","mao"]`. Não mude nomes/ordem sem preparar anotações e pesos compatíveis. O serviço rejeita classes divergentes.

### 4.2 Pontos da mão e interações

| Campo | Padrão | Efeito e limites |
|---|---|---|
| HAND_LANDMARKS_ENABLED | true | Usa MediaPipe; false exige classe mao no YOLO |
| HAND_MODEL_PATH | models/hand_landmarker.task | Arquivo do modelo de mão |
| HAND_MAX_HANDS | 2 | Máximo de mãos; inteiro ≥ 1 |
| HAND_CONTACT_MARGIN | 0.08 | Margem relativa à distância punho–base do médio; entre 0 e 0,5 |
| IOU_THRESHOLD | 0.10 | Sobreposição mínima no modo sem landmarks; > 0 e ≤ 1 |
| INTERACTION_CONFIRM_SECONDS | 0.3 s | Duração mínima para confirmar; ≥ 0 |
| INTERACTION_MIN_SAMPLES | 3 | Observações mínimas; inteiro ≥ 2 |
| INTERACTION_MAX_GAP_SECONDS | 0.5 s | Maior intervalo que pode acumular evidência consecutiva; > 0 |
| INTERACTION_RELEASE_SECONDS | 0.6 s | Tolerância de ausência e TTL de tracking; > 0 |
| INTERACTION_RESET_SECONDS | 2.0 s | Pausa que reinicia sessão; > 0 |
| INTERACTION_MOTION_MIN_RATIO | 0.1 | Deslocamento relativo mínimo para movimento conjunto; > 0 e ≤ 1 |

Exemplo de ajuste conservador para passagens rápidas:

```dotenv
TCC_INTERACTION_CONFIRM_SECONDS=0.4
TCC_HAND_CONTACT_MARGIN=0.06
```

Aumentar a duração pode perder toques breves; reduzir margem pode perder contatos parcialmente ocultos. Ajuste usando vídeos rotulados e observe falsos eventos e perdas. Os valores exemplificados são parâmetros para experimentar, não uma garantia de melhor precisão.

IOU_THRESHOLD não é confiança do YOLO nem seu limiar de NMS. No modo de pontos da mão, alterar apenas esse campo normalmente não muda a decisão geométrica da mão.

Se MediaPipe/modelo faltar, iniciar monitoramento falha com mensagem. Para operar provisoriamente sem ele, configure HAND_LANDMARKS_ENABLED=false e use pesos capazes de detectar mao. Não há fallback silencioso quando as mãos somem.

### 4.3 Pastas e dataset externo

| Campo | Padrão |
|---|---|
| RAW_FRAMES_DIR | data/raw_frames |
| LABELME_ANNOTATIONS_DIR | data/labelme_annotations |
| YOLO_LABELS_DIR | data/yolo_labels |
| DATASET_DIR | data/dataset |
| PRETRAINED_MODELS_DIR | models/pretrained |
| TRAINED_MODELS_DIR | models/trained |
| TRAINING_PROJECT | experiments/runs |
| BENCHMARKS_DIR | experiments/benchmarks |
| USE_EXTERNAL_VALIDATION_DATASET | false |
| EXTERNAL_VALIDATION_DATASET_DIR | data/external_validation |
| EXTERNAL_VALIDATION_DATASET_YAML | data/external_validation/data.yaml |

O modo externo faz o pipeline treinar diretamente pelo YAML indicado. A validação de classes também muda para EXTERNAL_CLASSES. Não o habilite para usar pesos treinados com as quatro classes próprias. O dataset externo não vem automaticamente com o repositório.

Cada campo de caminho é independente: alterar EXTERNAL_VALIDATION_DATASET_DIR não recalcula automaticamente EXTERNAL_VALIDATION_DATASET_YAML; confira ambos.

### 4.4 Caminhos calculados

| Nome | Valor para MODELO_ATIVO=yolo26m |
|---|---|
| BASE_MODEL | models/pretrained/yolo26m.pt |
| MODEL_PATH | models/trained/yolo26m/best.pt |
| TRAINING_NAME | yolo26m |

São propriedades, não escolhas separadas. Remova TCC_BASE_MODEL/TCC_MODEL_PATH de configurações antigas. O treinamento real acrescenta identificador ao nome da execução.

**Quando reiniciar:** mudança de config/.env → reinicie o processo inteiro. Novo treino que publicou best.pt na mesma arquitetura → pare e inicie o monitoramento para recarregar. A CLI também precisa ser reaberta.

## 5. Usar a interface

### 5.1 Monitoramento

Clique Iniciar monitoramento para abrir vídeo e iniciar processamento. O status informa estado, modelo e consumidores da câmera. Eventos aparecem à direita com horário local, tipo, produto e quantidade.

O detector avalia cada par mão–produto e pode confirmar vários produtos simultaneamente. Um contato contínuo produz um evento por par, não um por frame. Duas mãos no mesmo produto podem produzir dois eventos. Os detalhes mao_id, produto_id, pontos_mao, metodo e interpretacao estão no JSON da API, mesmo que não sejam mostrados no cartão.

Clique Parar para interromper o worker e fechar o stream daquele navegador. Captura ou outro navegador ainda aberto pode manter a conexão da câmera.

Trocar de aba ou fechar a página não é um comando de parada do worker. Se quiser encerrar inferência, use Parar.

### 5.2 Treino

1. Confira o modelo ativo exibido. O seletor desabilitado é intencional.
2. Ajuste épocas, tamanho da imagem e fração.
3. Clique Iniciar treino.
4. Acompanhe status; detalhes por época ficam no terminal do backend.
5. Ao concluir, os pesos validados são publicados para a arquitetura ativa.
6. Reabra o monitoramento para usar a nova carga.

Valores iniciais: 50 épocas, imgsz 640, fração 1.0. Fração pequena pode servir a teste de execução; não trate um treino de 1% como modelo final.

Não existe botão de cancelar treino nem barra de progresso por época. Execute um treino por vez, incluindo scripts externos. A proteção da API só detecta a própria thread.

### 5.3 Dataset

Informe intervalo (inicialmente 2 s) e quantidade (20), clique Capturar e aguarde. As imagens são salvas mesmo sem iniciar monitoramento. Ao concluir/errar a captura, a galeria é recarregada. O contador é final, não incremental.

Cada imagem aparece como anotado ou pendente. Anotado indica presença de JSON, não qualidade ou completude das caixas. Se uma miniatura falhar, use Tentar novamente.

Clique Abrir LabelMe para anotar. A janela abre no computador do backend. Depois de salvar anotações, recarregue a página para refletir os novos estados.

A interface não oferece captura ilimitada nem cancelamento de captura. Pela API, zero pode produzir execução ilimitada; prefira sempre uma quantidade finita nesse fluxo.

### 5.4 Experimentos

Mostra execuções com results.csv em runs e benchmarks. Cartões indicam existência de pesos/resultados e mostram results.png quando disponível. Atualize a página depois de um treino: essa lista não faz polling.

Esses gráficos medem o treinamento/validação de produtos, não a qualidade final da regra de interação nem FPS da aplicação.

## 6. Capturar e anotar o dataset

### 6.1 Captura por terminal

```powershell
.\.venv\Scripts\python.exe backend/app/capturar_frames.py --intervalo 2 --max-frames 30
```

Sem janela:

```powershell
.\.venv\Scripts\python.exe backend/app/capturar_frames.py --saida data/raw_frames --intervalo 1 --max-frames 50 --sem-janela
```

| Argumento | Padrão | Significado |
|---|---|---|
| --saida | RAW_FRAMES_DIR | Pasta de JPEGs |
| --intervalo | 2.0 | Segundos entre salvamentos; CLI aplica mínimo 0,1 |
| --max-frames | 0 | Limite; zero é ilimitado |
| --sem-janela | Desativado | Não abre OpenCV |

Q ou Ctrl+C encerra captura direta. Os nomes incluem data, UUID e contador. Arquivos .part são temporários; a galeria só deve mostrar JPEGs concluídos.

Não inicie várias capturas diretas e backend desnecessariamente: cada processo abre sua conexão com a ESP32-CAM. Pela interface, os consumidores do mesmo backend compartilham a conexão.

### 6.2 O que fotografar

Inclua produtos separados e encostados, diferentes orientações, unidades parcialmente ocultas, mãos em diversas posições e variações reais de iluminação/distância. Se o erro aparece com produtos agrupados, inclua exatamente essas situações.

Anote cada embalagem individualmente. Não desenhe uma caixa única sobre três unidades. Evite preencher o dataset apenas com centenas de frames quase idênticos. Reserve gravações/disposições novas para avaliar depois dos ajustes.

Melhor ângulo e iluminação podem revelar divisórias entre embalagens; aumentar o número de épocas não recupera informação visual totalmente escondida.

### 6.3 LabelMe

Pela interface, use Abrir LabelMe. Pelo terminal:

```powershell
.\.venv\Scripts\python.exe -m labelme data/raw_frames --output data/labelme_annotations
```

1. Abra a imagem e escolha a ferramenta de retângulo.
2. Desenhe uma caixa por objeto.
3. Use nomes exatos: creme_leite, gelatina, cha e mao.
4. Salve JSON com mesmo nome-base da imagem na pasta de anotações.
5. Revise imagens com sobreposição, caixas degeneradas ou objetos sem rótulo.

**Para o pipeline padrão, use retângulos.** O conversor atual considera os dois primeiros pontos de cada shape; polígonos/máscaras precisam de conversão apropriada. O script de benchmark tem conversão diferente e não corrige automaticamente o conversor normal.

A classe mao continua nos pesos atuais e permite o modo sem MediaPipe. Mudar o conjunto de classes exige treinar pesos compatíveis.

A abertura pela API repara referências imagePath quebradas quando encontra exatamente uma imagem correspondente. A abertura direta por terminal não executa esse reparador automaticamente.

### 6.4 Converter sem treinar

Na raiz, execute este bloco PowerShell:

```powershell
@'
import sys
sys.path.insert(0, "backend/app")
from core.config import settings
from services.annotation_converter import converter_labelme_para_yolo

arquivos = converter_labelme_para_yolo(
    settings.LABELME_ANNOTATIONS_DIR,
    settings.YOLO_LABELS_DIR,
    settings.CLASSES,
)
print("TXT gerados:", len(arquivos))
'@ | .\.venv\Scripts\python.exe -
```

Isso grava os TXT, mas não monta train/val nem inicia treinamento. Verifique os rótulos antes de prosseguir, especialmente se suas anotações antigas forem polígonos.

## 7. Treinar e administrar os modelos

### 7.1 Conferir seleção

```powershell
.\.venv\Scripts\python.exe scripts/experimento_yolo26.py --check
```

O comando informa modelo ativo, peso genérico e destino de inferência. Confere o arquivo genérico, mas não valida integralmente o dataset.

### 7.2 Treino por terminal

```powershell
.\.venv\Scripts\python.exe scripts/experimento_yolo26.py --epochs 50 --imgsz 640
```

Apesar do nome do script, usa qualquer uma das quatro arquiteturas definida em MODELO_ATIVO. Não aceita os antigos argumentos posicionais de modelo/nome/batch/workers.

O pipeline monta data/dataset, treina em GPU se disponível (CPU senão), grava uma pasta nova em experiments/runs e publica o best.pt validado.

**Antes de repetir preparação do dataset:** o pipeline não limpa automaticamente arquivos antigos de train/val. Para evitar resíduos, prepare uma pasta nova usando pasta_dataset na chamada Python abaixo, ou revise os derivados existentes. Preserve imagens originais e JSONs.

### 7.3 Treino por Python, com pastas explícitas

```powershell
@'
import sys
sys.path.insert(0, "backend/app")
from services.training_service import rodar_pipeline_treinamento

resultado = rodar_pipeline_treinamento(
    pasta_fotos="data/raw_frames",
    pasta_json="data/labelme_annotations",
    pasta_yolo="data/yolo_labels",
    pasta_dataset="data/dataset_novo",
    epochs=50,
    imgsz=640,
    fraction=1.0,
)
print(resultado)
'@ | .\.venv\Scripts\python.exe -
```

Use um nome de pasta de dataset que ainda não contenha splits antigos. O script de benchmark usa data/dataset fixo, portanto uma pasta alternativa não muda automaticamente a entrada dele.

A divisão padrão é 80/20 por imagens, sem agrupamento por gravação. Para avaliação rigorosa entre sessões, organize/valide os splits de acordo com o experimento; não atribua essa capacidade ao pipeline atual.

### 7.4 O que acontece com os pesos

| Situação | Resultado |
|---|---|
| Novo treino começa | Pesos de inferência anteriores continuam disponíveis |
| Treino falha/interrompe | Não ocorre publicação final |
| Treino termina, mas best.pt tem classes/arquitetura incompatíveis | Publicação falha; pesos anteriores permanecem |
| Treino e validação do arquivo concluem | best.pt é copiado por temporário, conferido por hash e substituído atomicamente |
| Worker já estava rodando | Continua com o objeto em memória até parar/iniciar |

Os resultados completos ficam em experiments/runs/<modelo>_<id>. Os originais dos benchmarks não são sobrescritos. models/trained/origens.json é registro da importação inicial, não um log de todos os treinos posteriores.

### 7.5 Restaurar/publicar um best.pt de benchmark pelo código

Use apenas um peso correspondente à arquitetura ativa e às classes configuradas:

```powershell
@'
import sys
from pathlib import Path
sys.path.insert(0, "backend/app")
from core.config import settings
from services.model_service import publish_weights

origem = (
    Path(settings.BENCHMARKS_DIR)
    / "comparativo_20260907_50ep_corrigido"
    / settings.MODELO_ATIVO
    / "weights"
    / "best.pt"
)
print(publish_weights(origem, settings.MODELO_ATIVO))
'@ | .\.venv\Scripts\python.exe -
```

Esse comando **substitui os pesos locais publicados** após validação. Pare/inicie monitoramento para carregar a nova cópia. Não altera a arquitetura selecionada e não publica nada na internet.

## 8. Executar pelo terminal e por Python

### 8.1 Monitor OpenCV

```powershell
.\.venv\Scripts\python.exe backend/app/cli_monitor.py
```

Mostra caixas, IDs, pontos numerados e pares candidatos/confirmados. Q encerra. Requer desktop e câmera acessível.

O log inicial mostra o caminho de pesos. O texto “Evento enviado” posterior é apenas impressão no estado atual do controller: requests.post está comentado. Não espere eventos dessa CLI no navegador. Para publicar pela API, use as chamadas explícitas da próxima seção ou o worker da interface.

### 8.2 Processar imagens em Python

Exemplo com várias imagens da mesma sequência; arquivos e tempos são ilustrativos e devem ser substituídos por dados reais:

```python
import sys
import cv2
sys.path.insert(0, "backend/app")

from services.vision_service import VisionService
from services.event_service import EventService

visao = VisionService(device="cpu")
interacoes = EventService()
try:
    for segundo, caminho in [(0.0, "frame0.jpg"), (0.15, "frame1.jpg"), (0.30, "frame2.jpg")]:
        frame = cv2.imread(caminho)
        if frame is None:
            raise FileNotFoundError(caminho)
        deteccoes = visao.processar_frame(frame, timestamp=segundo)
        novos_eventos = interacoes.processar(deteccoes, timestamp=segundo)
        print(novos_eventos)
finally:
    visao.close()
```

Salve o exemplo em arquivo e execute com o Python da .venv, a partir da raiz. Mantenha uma instância de EventService por sequência/sessão, em vez de criar uma por frame. As três observações só confirmam se houver evidência suficiente; o exemplo não garante evento.

VisionService devolve DataFrame; coordenadas são pixels. Mãos incluem landmarks. As funções não enviam eventos por conta própria. Imagem isolada permite detecção, mas não fornece o tempo necessário para confirmar interação.

### 8.3 Testes

```powershell
.\.venv\Scripts\python.exe -m pytest backend/app/tests -q
```

Para uma área específica:

```powershell
.\.venv\Scripts\python.exe -m pytest backend/app/tests/test_interactions.py -q
.\.venv\Scripts\python.exe -m pytest backend/app/tests/test_model_selection.py -q
```

Os testes verificam regras/contratos e usam mocks para tarefas longas. Não são substituto de teste com câmera e novas disposições dos produtos.

## 9. Usar a API e o WebSocket

### 9.1 Consultar saúde, estado e modelos

Com servidor rodando:

```powershell
Invoke-RestMethod -Uri 'http://localhost:8000/api/health'
Invoke-RestMethod -Uri 'http://localhost:8000/api/monitoramento/status'
Invoke-RestMethod -Uri 'http://localhost:8000/api/modelos'
Invoke-RestMethod -Uri 'http://localhost:8000/api/treino/experimentos'
```

modelo_configurado indica seleção do processo. modelo_carregado/pesos_carregados mostram última inicialização bem-sucedida do worker; confira também status.

### 9.2 Iniciar/parar e assistir stream

```powershell
Invoke-RestMethod -Method Post -Uri 'http://localhost:8000/api/monitoramento/iniciar'
Invoke-RestMethod -Method Post -Uri 'http://localhost:8000/api/monitoramento/parar'
```

Execute a chamada de parar quando quiser encerrar, não imediatamente se pretende observar o vídeo. As respostas são assíncronas: iniciado=true não garante que os pesos carregaram ou a câmera conectou. Consulte status.

Para apenas visualizar o MJPEG, abra http://localhost:8000/api/stream no navegador. Isso usa a câmera, mas não inicia detecção.

### 9.3 Publicar e consultar um evento manual

```powershell
$evento = @{
    tipo = 'interacao_mao'
    produto = 'cha'
    quantidade = 1
    mao_id = 1
    produto_id = 3
    pontos_mao = @(8)
    metodo = 'landmarks'
    interpretacao = 'contato_provavel'
} | ConvertTo-Json
Invoke-RestMethod -Method Post -Uri 'http://localhost:8000/api/eventos' -ContentType 'application/json' -Body $evento
Invoke-RestMethod -Uri 'http://localhost:8000/api/eventos'
```

Esse evento é manual, não prova uma observação da câmera. tipo e produto são obrigatórios; quantidade vale 1 quando omitida. IDs, pontos, método e interpretação são opcionais. API acrescenta timestamp UTC, retorna 201 e transmite aos clientes.

### 9.4 Captura, LabelMe e treino

```powershell
$captura = @{ intervalo = 2; max_frames = 20 } | ConvertTo-Json
Invoke-RestMethod -Method Post -Uri 'http://localhost:8000/api/dataset/capturar' -ContentType 'application/json' -Body $captura
Invoke-RestMethod -Uri 'http://localhost:8000/api/dataset/capturar/status'
Invoke-RestMethod -Uri 'http://localhost:8000/api/dataset/imagens'
```

Depois de terminar a captura:

```powershell
Invoke-RestMethod -Method Post -Uri 'http://localhost:8000/api/dataset/anotar'
```

Depois de salvar/revisar as anotações:

```powershell
$treino = @{ epochs = 50; imgsz = 640; fraction = 1.0 } | ConvertTo-Json
Invoke-RestMethod -Method Post -Uri 'http://localhost:8000/api/treino/start' -ContentType 'application/json' -Body $treino
Invoke-RestMethod -Uri 'http://localhost:8000/api/treino/status'
```

Não envie base_model para trocar arquitetura: a API segue MODELO_ATIVO. Campo legado diferente é rejeitado. 409 significa tarefa correspondente já em andamento no processo; 400 pode indicar modelo inválido/ausente; 422 significa corpo inválido; erros posteriores à inicialização aparecem no endpoint de status.

Para baixar uma imagem listada, use /api/dataset/imagens/{nome} com nome codificado em URL. Para gráficos, use grafico_url fornecido por /api/treino/experimentos.

### 9.5 WebSocket no navegador

No console de uma página servida pelo próprio backend:

```javascript
const protocolo = location.protocol === "https:" ? "wss" : "ws";
const socket = new WebSocket(protocolo + "://" + location.host + "/ws/eventos");
socket.onmessage = (mensagem) => console.log(JSON.parse(mensagem.data));
socket.onerror = (erro) => console.error(erro);
// Quando terminar:
// socket.close();
```

Recebe eventos futuros. Para histórico, consulte GET /api/eventos. Não precisa enviar mensagem para cada evento. Após desconexão, seu cliente deve reconectar; não há replay por cursor nem persistência durável.

A lista completa de rotas, schemas e efeitos está no [Manual Técnico](MANUAL_TECNICO.md#9-api-http-websocket-e-arquivos).

## 10. Comparar interações em vídeos

Use vídeos gravados na posição real da câmera, incluindo casos corretos e erros. O replay não grava automaticamente um vídeo ao vivo: recebe um arquivo existente.

### 10.1 Executar os três modos

Escolha saídas novas e pastas-pai já existentes:

```powershell
.\.venv\Scripts\python.exe scripts/replay_interactions.py cena.mp4 --device cpu --output resultado_landmarks.json --annotated-video cena_anotada.mp4
.\.venv\Scripts\python.exe scripts/replay_interactions.py cena.mp4 --device cpu --iou-only --output resultado_temporal.json
.\.venv\Scripts\python.exe scripts/replay_interactions.py cena.mp4 --device cpu --baseline --output resultado_original.json
```

| Opção | Significado |
|---|---|
| video | Caminho posicional do vídeo |
| --output | JSON de saída obrigatório; arquivo não pode existir |
| --weights | Peso alternativo apenas neste replay; classes precisam ser compatíveis |
| --device | cpu ou seleção de GPU aceita pelo YOLO |
| --iou-only | Mãos detectadas pelo YOLO, com confirmação temporal |
| --baseline | Regra antiga: primeiro produto por mão/frame, sem memória |
| --annotated-video | Salva MP4 com overlay disponível no serviço |
| --annotations | JSON de interações esperadas para comparação |

Não passe baseline e iou-only juntos. Baseline prevalece se ambos forem usados. O baseline não alimenta o overlay de EventService; use os eventos JSON para analisar esse modo.

O modo padrão ativa MediaPipe. Para comparar em outra arquitetura, altere MODELO_ATIVO e reabra o processo, ou use --weights somente para esse diagnóstico:

```powershell
.\.venv\Scripts\python.exe scripts/replay_interactions.py cena.mp4 --device cpu --weights models/trained/yolo26m/best.pt --output resultado_yolo26m.json
```

### 10.2 Anotar o resultado esperado

Crie verdade.json com uma entrada por interação esperada, em segundos do vídeo:

```json
[
  {"produto": "cha", "inicio": 1.0, "fim": 2.0},
  {"produto": "gelatina", "inicio": 1.0, "fim": 2.0}
]
```

Execute:

```powershell
.\.venv\Scripts\python.exe scripts/replay_interactions.py cena.mp4 --device cpu --annotations verdade.json --output avaliacao.json
```

O relatório contém eventos, modo, parâmetros, frames, FPS do vídeo, FPS medido e contagens corretos/falsos_ou_duplicados/perdidos. A associação aceita o fim do intervalo mais o tempo de confirmação.

A avaliação compara classe e tempo, não a identidade exata da embalagem ou mão. Unidades iguais e interações simultâneas exigem inspeção manual. FPS do replay inclui processamento e escrita de vídeo se ativada, mas exclui carregamento/aquecimento dos modelos; não equivale ao FPS total da câmera.

### 10.3 Como escolher ajustes

Compare, em vídeos reservados:

- Passagem diante de A para pegar B.
- Toque breve sem deslocamento.
- Movimento conjunto da mão e produto.
- Três produtos simultâneos.
- Duas mãos e unidades iguais.
- Oclusão e reaparecimento.
- Câmera/iluminação diferentes das cenas de treino.

Se o detector agrupa unidades, corrija primeiro dados/enquadramento/detecção. Tempo de confirmação não separa uma caixa que já veio agrupada. Segmentação e tracking mais sofisticado são possibilidades de evolução, não recursos já implementados.

## 11. Executar benchmarks

### 11.1 Preparação

O benchmark compara yolov8n, yolo12n, yolo26s e yolo26m sequencialmente, com 50 épocas cada. Exige CUDA, quatro pesos genéricos, data/dataset organizado e JSONs LabelMe correspondentes em data/labelme_annotations.

Não depende de MODELO_ATIVO e não publica automaticamente o vencedor. O processo congela uma cópia dos dados e registra hashes. A conversão das caixas nesse script usa os extremos de todos os pontos, diferentemente do pipeline padrão.

### 11.2 Rodar comparativo

Use uma pasta que não exista:

```powershell
.\.venv\Scripts\python.exe scripts/benchmark_tcc.py --out experiments/benchmarks/NOVA_EXECUCAO
```

O script treina todos, registra logs e produz resumos. Não execute junto com outro treino. A opção --model é usada internamente para um modelo sobre uma cópia já preparada; não é um mecanismo geral de retomar treino interrompido.

Para o relatório, após os quatro terminarem:

```powershell
.\.venv\Scripts\python.exe scripts/relatorio_benchmark_tcc.py experiments/benchmarks/NOVA_EXECUCAO
```

Produz RELATORIO_TCC.md, comparativo_por_classe.csv e curvas_map.png junto ao experimento. **O texto do protocolo do gerador contém valores fixos da execução original**, como hardware, versões e contagens. Revise esse texto antes de usar um relatório de outra execução.

### 11.3 Interpretar artefatos

| Artefato | Uso |
|---|---|
| protocol.json | Ambiente, configurações e hashes de entradas |
| dataset/ e annotations/ | Cópia congelada do experimento |
| <modelo>/args.yaml | Parâmetros efetivos do treino |
| <modelo>/results.csv | Evolução por época |
| <modelo>/weights/best.pt | Melhor checkpoint produzido |
| <modelo>_summary.json e summary.json | Métricas da reavaliação e hashes |
| comparativo.csv | Comparação global |
| comparativo_por_classe.csv | Métricas por classe |
| curvas_map.png | Evolução de mAP50–95 |
| <modelo>.log | Log de treino/reavaliação |

Precisão avalia proporção de previsões corretas; recall, quanto dos objetos esperados foi recuperado. mAP resume precisão/recall por classe e critérios de sobreposição. Não compare diretamente esses números com a precisão de eventos de interação.

Ausência de duplicatas binárias entre train/val não garante independência visual: frames próximos podem ser muito parecidos. Avalie cenas de sessões distintas. O melhor checkpoint é escolhido pela validação; isso não constitui teste independente.

## 12. Diagnóstico e manutenção

### 12.1 Problemas frequentes

| Sintoma | O que conferir / ação |
|---|---|
| Import de core/services falha | Executar na raiz com --app-dir backend/app ou ajustar sys.path nos exemplos Python |
| Backend não abre | Verificar porta 8000, imports e mensagem do terminal |
| Câmera reconectando | IP, alimentação, rede e URL MJPEG; o leitor tenta novamente a cada 2 s após falha |
| Câmera aparece, mas não há eventos | Status do worker, modelo/pesos, classes e evidência por tempo suficiente |
| Peso ausente | MODELO_ATIVO e models/trained/<modelo>/best.pt |
| Modelo da mão ausente | Instalar requirements-hands.txt e executar setup_hands.py |
| Erro de classes | Peso pertence a outro dataset; conferir modo externo e nomes/IDs |
| Troquei config, mas modelo não mudou | Reiniciar processo; verificar override TCC_MODELO_ATIVO e log de carga |
| Treino terminou, mas resultado visual é igual | Parar/iniciar worker; verificar status de publicação e novo best.pt |
| Produto some ou vários viram uma caixa | Rever disposição, iluminação, anotações e diversidade do dataset; tracking não corrige detecção agrupada |
| Falso evento ao passar mão | Avaliar margem e duração; contato 2D ainda pode ser ambíguo |
| Interação nunca confirma em CPU lenta | Medir intervalo entre frames; lacunas acima do máximo reiniciam contagem |
| Evento repetido após oclusão | Pode ter expirado par/ID ou ocorrido troca de tracking |
| “Evento enviado” na CLI, nada no navegador | POST está comentado; usar worker web ou chamada HTTP explícita |
| LabelMe não aparece no navegador | Ele abre como desktop no computador do backend |
| LabelMe não acha imagem | Conferir nome-base, imagePath e executar abertura pela API para reparo |
| Galeria não marcou anotação salva | Recarregar página; JSON não gera notificação automática |
| total capturado fica zero durante captura | Contador final, atualizado ao concluir |
| Experimento novo não apareceu | Recarregar página e verificar results.csv na pasta efetiva |
| Treino retorna 409 | Outra thread de treino está viva naquele backend |
| Memória de GPU insuficiente | Encerrar inferência concorrente, usar arquitetura/entrada compatível; não há ajuste de batch na UI atual |
| Nenhum par para treinar | Conferir pastas, extensão e correspondência imagem/JSON/TXT |
| Validação estranha após repetir treino | Rever resíduos de splits e conversão de polígonos |
| Replay recusa saída | Usar nome novo; o script não sobrescreve JSON/vídeo existente |

### 12.2 Encerramento

Pare monitoramento pelo botão. Aguarde capturas finitas e treinos terminarem antes de Ctrl+C no servidor. O servidor não oferece endpoints de cancelamento para essas duas tarefas.

Na captura direta, Q ou Ctrl+C; na CLI de monitoramento, Q. Não confunda fechar a aba do navegador com parar os processos backend.

### 12.3 Backup e reprodução

Preserve imagens originais, JSONs, pesos selecionados, origens.json e pastas completas dos benchmarks/treinos relevantes. Os TXT e splits são derivados, mas fazem parte do registro exato de um experimento e devem ser guardados quando precisar reproduzir resultados.

Não copie a .venv como único método de instalação em outra máquina; registre versões e recrie dependências. O .env é local e pode conter caminhos/rede específicos. Os pesos já existentes não são baixados automaticamente, exceto o modelo de mão pelo script explícito.

Os eventos de API não são salvos em arquivo por padrão. Para registrar uma avaliação, prefira replay com JSON ou escreva um consumidor HTTP/WebSocket adequado.

### 12.4 Organização da documentação

A pasta docs contém somente:

- [Manual Técnico](MANUAL_TECNICO.md): arquitetura, arquivos, funções, métodos, regras, rotas, contratos e limitações.
- [Manual de Uso](MANUAL_DE_USO.md): este documento, com operação e configuração.

O README da raiz é uma porta de entrada. Relatórios e métricas de experimentos ficam nos próprios experimentos, sem criar novos manuais de referência.

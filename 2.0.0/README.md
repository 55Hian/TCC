# Controle de Inventario — 2.0.0

Aplicacao independente: codigo, pesos, dados e configuracao ficam nesta pasta.

## Instalar e iniciar

Execute os comandos a partir desta pasta. Copie `.env.example` para `.env` e ajuste as variaveis se necessario:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
docker compose up -d banco
.\.venv\Scripts\python.exe -m uvicorn app:app --host 0.0.0.0 --port 8000
```

Aguarde o banco ficar saudavel antes de iniciar a API. Abra `http://localhost:8000` para usar a interface ou `/docs` para consultar a API. Configure a camera principal com `TCC_CAMERA_URL` e a camera USB de evidencia com `TCC_CAMARA_SECUNDARIA` e `TCC_CAMARA_BACKEND`. O modelo inicial vem de `TCC_MODELO_ATIVO` (padrao `yolo12n`); a escolha salva por `/api/modelos/ativar` prevalece. `TCC_API_URL` define o endereco que o monitoramento usa para enviar interacoes a `/api/eventos`.

## Treinamento

1. `POST /api/treinamento/capturar` captura imagens em `data/frames`.
2. `POST /api/treinamento/labelme` abre o Labelme para anotar as imagens. Use caixas retangulares e os nomes das classes configuradas.
3. `POST /api/treinamento/treinar` converte anotacoes para YOLO, monta o dataset e inicia o treino.
4. Consulte `GET /api/treinamento/status`. O melhor peso fica em `models/trained/<arquitetura>/best.pt`.
5. Use `POST /api/modelos/ativar` com `{"nome":"yolo12n"}` para selecionar um modelo treinado. Pare o monitoramento antes de trocar.

## Monitoramento

`POST /api/monitoramento/iniciar` inicia camera, YOLO e landmarks da mao. As interacoes detectadas sao enviadas pela rota `/api/eventos` e gravadas no banco. Use `/api/monitoramento/parar`, `/api/monitoramento/status` e `/api/monitoramento/frame` para controlar e acompanhar o fluxo. `GET /api/eventos` consulta os registros persistidos.

## Banco de dados

Somente `POST /api/eventos` e `POST /api/balanca` gravam registros de entrada no PostgreSQL. `database/schema.sql` mantem o esquema completo: usuarios, sessoes de tracking e compra, eventos, variacoes da balanca e correlacoes de retirada. A API aplica o esquema ao iniciar. Os clipes da segunda camera sao salvos em `data/videos`; a rota de clipe nao grava novos registros no banco.

- `POST /api/eventos` recebe e grava interacoes da camera. `GET /api/eventos` lista os eventos recentes.
- `POST /api/balanca` recebe somente `variacao_peso`, gera o timestamp na API e grava ambos.
- Um processo da API varre os dados persistidos ao iniciar e a cada 60 segundos. Ele procura eventos `interacao_mao` e variacoes negativas da balanca, pareando cada evento e cada variacao no maximo uma vez. Um par precisa estar a ate 15 segundos de distancia e a variacao retirada precisa ficar dentro de 20% do peso cadastrado do produto. A correlacao guarda os dois timestamps e uma copia dos dados do produto. Registros sem produto cadastrado/peso conhecido ou sem par dentro desses limites ficam pendentes.
- Esses limites podem ser ajustados por `TCC_CORRELACAO_INTERVALO_SEGUNDOS`, `TCC_CORRELACAO_JANELA_SEGUNDOS` e `TCC_CORRELACAO_TOLERANCIA_PESO` (fracao; `0.2` equivale a 20%). O processamento inicial tambem tenta correlacionar registros antigos que ainda nao tenham sido usados.

A conexao e configurada por `TCC_DATABASE_URL`; sem essa variavel, a API usa `POSTGRES_USER`, `POSTGRES_PASSWORD`, `POSTGRES_DB`, `POSTGRES_HOST` e `POSTGRES_PORT` do `.env`. O Compose armazena os dados em `data/postgres` e usa uma imagem PostgreSQL com suporte a `pgvector`, necessario pela tabela de vetores faciais.

## Camera USB de evidencia

A API ja oferece `GET /api/camera-secundaria/status`, `POST /api/camera-secundaria/gravar` e `GET /api/camera-secundaria/gravacoes/{id_evento}`. O POST recebe `{"id_evento": 123, "timestamp": "2026-11-06T20:00:00Z"}` e, para esse instante, salva 20 segundos antes e 10 depois. `TCC_VIDEO_SEGUNDOS_BUFFER` define a idade maxima do evento que ainda pode ser recuperado (padrao 1800 segundos, ou 30 minutos); nao altera a duracao do clipe. Por exemplo, para permitir buscar eventos de ate 30 minutos atras, configure `TCC_VIDEO_SEGUNDOS_BUFFER=1800` no `.env`. Os frames ficam em `data/videos/.buffer`, em disco, e expiram da retencao circular. Para buscar um evento ocorrido ha 30 minutos, o buffer precisa ja conter os frames desde 30 minutos e 20 segundos atras. A camera e o buffer so capturam enquanto a API esta ligada. Ao confirmar uma correlacao, a API solicita automaticamente um clipe com o timestamp da balanca; se a camera ainda nao estiver pronta, tenta novamente no proximo ciclo.

## Interface

O menu organiza o sistema em Inicio (painel ao vivo), Treinamento, Monitoramento gondola, Monitoramento ambiente (camera secundaria), Dados do banco e Produtos. O inicio mostra indicadores de 24 horas, inferencia YOLO e as interacoes, variacoes e correlacoes recentes; correlacoes com clipe abrem o arquivo de video. A tela Dados do banco lista e permite cadastrar, editar e remover usuarios, sessoes, eventos, variacoes da balanca e correlacoes. Produtos tem uma tela propria de cadastro, edicao e remocao, com peso unitario positivo na mesma unidade usada por `variacao_peso`. A classe YOLO associa as interacoes ao produto cadastrado. Alteracoes em registros relacionados podem ser bloqueadas para preservar as referencias entre tabelas.

`GET /api/dashboard` alimenta os indicadores e as tabelas recentes do inicio. `GET /api/camera-secundaria/gravacoes/{id_evento}/arquivo` abre o clipe persistido da retirada, quando disponivel.

`/api/produtos` oferece CRUD de produtos. `/api/banco/tabelas` informa as tabelas administrativas; `/api/banco/{tabela}` lista registros com `limite` e `offset`, e aceita `POST`, `PUT /{id}` e `DELETE /{id}` para administrar as tabelas autorizadas. `GET /api/balanca` consulta variacoes persistidas. A rota de escrita da balanca continua aceitando somente `variacao_peso`, com timestamp gerado pela API.

O Labelme abre no computador que executa a API. Na tela inicial, a camera secundaria mostra o buffer, agenda clipes e permite consultar o estado por ID do evento.


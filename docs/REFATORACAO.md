# Tradução e simplificação do código

## Escopo e convenções

Abrange backend, frontend, scripts e testes. Preserva a arquitetura em camadas,
as rotas, chaves JSON, nomes de arquivos, opções CLI e variáveis TCC_*.
Python usa snake_case; JavaScript usa camelCase; classes usam PascalCase.
Identificadores próprios usam português sem acentos. Comentários e docstrings
explicam em português brasileiro as regras, unidades e efeitos colaterais.
Interfaces anteriores permanecem disponíveis quando houver consumidores existentes.

## Inventário e prioridades

| Módulos | Responsabilidade e risco | Verificação |
| --- | --- | --- |
| event_service, tracking_service | Geometria, identidade local, continuidade temporal | Contato, lacunas, movimento, duplicação |
| camera_service, shared_camera, worker, captura | MJPEG, sincronização, fechamento | Fonte simulada, consumidor lento, falhas |
| vision_service, hand_service, interaction_overlay | Inferência e representação | Modelos substituídos, coordenadas e instante |
| annotation_converter, annotation_paths | Conversão e referências LabelMe | JSON inválido, Unicode, escrita e normalização |
| training_service, model_service | Dataset, treino e publicação | Diretórios temporários, interrupção, integridade |
| routers, core, controllers | HTTP, WebSocket, estado | TestClient e clientes simulados |
| frontend/js | Estado visual e requisições | Node com DOM, fetch e timers simulados |
| scripts | Benchmark, relatório e replay | Entradas sintéticas e saídas temporárias |

A conversão histórica da aplicação usa os dois primeiros pontos. O benchmark
usa os extremos de todos os pontos, recortados à imagem. A refatoração mantém
essa diferença explícita; corrigir a regra da aplicação exige uma mudança funcional
separada e revalidação das anotações.

## Referência

A suíte original passou com 59 testes. O inventário em complexidade_antes.json
registra a situação após a primeira etapa já aprovada. A métrica conta decisões
sintáticas por função (condições, laços, operadores booleanos e compreensões);
não é uma implementação formal de complexidade ciclomática. A comparação usa
a mesma regra antes e depois. Linhas incluem comentários e docstrings.

## Validação reproduzível

Comando único: `.venv/Scripts/python.exe -B scripts/validar_projeto.py`.
Requer Node.js e o ambiente Python do projeto, sem dependências novas.
O limite automatizado é de 15 decisões por função de produção.

Executar a partir da raiz:

- `.venv/Scripts/python.exe -B -m pytest -q -p no:cacheprovider`
- `.venv/Scripts/python.exe -B scripts/verificar_codigo.py --comparar docs/complexidade_antes.json`
- `node --test frontend/tests/*.test.cjs`

A suíte comum usa arquivos temporários e substitutos de rede/inferência.
Testes com hardware devem receber a marca `hardware` e ser executados
separadamente, registrando câmera, pesos e ambiente utilizados.

## Execução das etapas

1. Inventário e convenções registrados; contratos HTTP/JSON, CLI e TCC_* mantidos.
2. Suíte original executada; fixtures temporárias e casos de fronteira acrescentados.
3. Classes, funções, métodos, variáveis locais e nomes de testes traduzidos.
4. Responsabilidades separadas nos serviços, rotas, interface e scripts, com testes
   intermediários a cada grupo de alterações.
5. Comentários e manuais atualizados; índice de símbolos regenerado.
6. Sintaxe, limite de complexidade, testes, comparação funcional e inferência local
   verificados. As limitações de hardware estão registradas abaixo.

## Compatibilidade e escolhas

- Classes principais: ServicoEventos, RastreadorObjetos, ServicoVisao,
  ServicoMaos, CameraCompartilhada, EstadoAplicacao e Configuracoes.
- Os nomes anteriores de classes continuam como aliases. Funções renomeadas têm
  adaptadores que aceitam os antigos parâmetros nomeados.
- Métodos como iniciar/adquirir/liberar/aguardar_frame/fechar têm aliases dos nomes
  anteriores. Campos públicos já consumidos por integrações e parâmetros desses
  métodos permanecem estáveis. Atributos privados da câmera foram traduzidos.
- As interfaces de bibliotecas continuam com nomes originais: train, names,
  detect_for_video, close de fontes externas, entre outras. Campos JSON,
  formatos de CSV e argumentos de Ultralytics não foram traduzidos.
- Os nomes físicos de módulos Python, arquivos JavaScript e scripts foram mantidos,
  preservando imports, URLs de arquivos estáticos e comandos existentes.
- A semente de divisão do dataset agora pertence a um gerador local: preserva a
  divisão para a mesma ordem de entrada e deixa de alterar o estado aleatório global.
- A interface informa falhas de consultas sem rejeições de promessa sem tratamento.
  Os cartões de experimentos usam nós DOM e exibem os nomes como texto literal.
- As consultas de imagens e experimentos passaram para dataset_service e
  experiment_service. As rotas mantêm respostas e códigos HTTP.
- O texto do relatório foi separado em scripts/templates/relatorio_tcc.md;
  cálculos, colunas e nomes de arquivos permanecem preservados.
- Testes de integração HTTP/WebSocket/câmera compartilhada podem ser selecionados
  com `pytest -m integracao`; os demais casos são executáveis sem hardware.
  `monkeypatch`, `tmp_path` e outros nomes de fixtures do pytest permanecem originais.

## Resultado da validação

- Suíte inicial: 59 testes Python.
- Suíte final: 87 testes Python e 7 testes JavaScript.
- Sintaxe dos 48 arquivos Python e dos 6 arquivos JavaScript validada.
- Limite de 15 decisões por função de produção atendido. O verificador mede
  decisões sintáticas, não uma estimativa de desempenho ou legibilidade absoluta.
- Permanecem dois avisos de depreciação do ambiente FastAPI/Starlette já existentes.
- Não foram adicionadas dependências nem executados treinamentos.
- Arquivos de dados, pesos e experimentos originais não foram alterados.

### Comparação funcional e tempo

Comparação em memória com o commit
`9f5ab3dc14b5b2a387d4c0878cdda96f000156ca`, usando os serviços de eventos e
rastreamento anteriores: 600 imagens sintéticas, 30 eventos, com eventos,
diagnósticos finais e IDs finais idênticos. Foram cinco execuções por versão;
medianas de 223,11 ms antes e 224,24 ms depois (aproximadamente 0,5% de diferença).
É uma medição local da regra temporal, sem inferência ou câmera, e não um
benchmark de FPS do sistema.

### Inferência e hardware

Foi executada inferência real em CPU com o modelo yolo12n de
models/trained/yolo12n/best.pt e MediaPipe habilitado, sobre
frame_20260905_153746_0003.jpg: 8 detecções, timestamp 1,0 preservado e
aproximadamente 128,81 ms nessa chamada, após aquecimento. O serviço fechou os
recursos ao terminar. Isso verifica execução, não precisão do detector.

Em 14/09/2026, a ESP32-CAM física respondeu pelo endereço configurado e entregou
um JPEG válido de 640×480. A verificação abriu apenas a leitura necessária para
esse quadro e encerrou a conexão.

A interface também foi validada no Chrome real em modo headless, contra uma
instância temporária do backend: as quatro abas abriram, o modelo ativo exibido
foi yolo12n, a galeria listou 100 imagens e foram exibidos 4 experimentos.
Não houve exceções JavaScript. A renderização foi inspecionada em capturas de
1280×900 e 390×844; na largura móvel, conteúdo e viewport mediram 390 px, sem
rolagem horizontal. A galeria usa carregamento progressivo: 98 miniaturas já
estavam carregadas no instante da medição.

As ações que iniciam treino, captura ou monitoramento continuam cobertas pelos
testes simulados; essa inspeção real consultou a interface e alternou abas.
Os processos temporários de navegador e backend foram encerrados ao terminar.
Novas avaliações de precisão ou treinamento comparativo devem ocorrer
separadamente desta refatoração.

## Comparação de complexidade

Máximo de decisões sintáticas por função em cada módulo selecionado:

| Módulo | Antes | Depois |
|---|---:|---:|
| `backend/app/services/event_service.py` | 22 | 15 |
| `backend/app/services/tracking_service.py` | 14 | 8 |
| `backend/app/services/camera_service.py` | 12 | 8 |
| `backend/app/services/shared_camera.py` | 8 | 6 |
| `backend/app/services/training_service.py` | 18 | 9 |
| `backend/app/services/annotation_paths.py` | 12 | 7 |
| `backend/app/services/interaction_overlay.py` | 10 | 6 |
| `scripts/benchmark_tcc.py` | 19 | 8 |
| `scripts/relatorio_benchmark_tcc.py` | 14 | 7 |
| `scripts/replay_interactions.py` | 27 | 11 |

Inventários completos: [antes](complexidade_antes.json) e [depois](complexidade_depois.json).
A extração de funções pode aumentar o total de linhas e a soma de decisões;
a comparação acima mostra o maior bloco de decisão a compreender por vez.

# Fase 6 - registro de validacao (2026-09-06)

Para entender módulos, dependências, fluxos e pontos de extensão, consulte o [Guia do código e da arquitetura](GUIA_DO_CODIGO.md).

## Executado

- 24 testes passaram: API, WebSocket, captura com fonte simulada, eventos, conversao de anotacoes, MJPEG simulado, arquivos do frontend e galeria comparada com arquivos reais.
- JavaScript: todos os arquivos passaram em `node --check`.
- Experimento: `--help` e `yolo26s.pt comparativo_novo 4 2 --check` executados com sucesso; nenhum treino iniciado.
- Configuracao importada por `backend.app.core.config`; MODEL_PATH existe.
- Corrigido o path antigo de `data/dataset/data.yaml` para a pasta atual.
- Manuais atualizados com inicializacao, reconstrucao atual e limites reais da interface.
- Limpeza anterior registrada no commit 435b6fd; nenhuma nova exclusao nesta rodada.
- Inventario atual: 97 JPG brutos, 95 JSON LabelMe, 95 TXT YOLO. Essas quantidades ja existiam antes desta rodada e diferem da previsao do plano (100/91/91); nao houve alteracao das amostras nesta rodada.
- Dois avisos de depreciacao das dependencias Starlette/httpx/AnyIO; nenhuma falha na suite.

## Pendencias para aceite completo

- [ ] Abrir http://localhost:8000 e verificar as quatro abas e o console do navegador. A verificacao HTTP e de sintaxe nao substitui esse teste visual.
- [ ] Publicar um evento e confirmar que aparece na tela sem F5 (o transporte WebSocket passou no teste automatizado).
- [ ] Conferir stream e latencia com a ESP32-CAM real; capturar cinco frames e abrir/anotar no LabelMe.
- [ ] Executar um treino real isolado e conferir status/resultados. O --check valida caminhos; nao valida CUDA, VRAM ou treinamento.
- [ ] Aprovar push antes de publicar no GitHub.

## Diferencas remanescentes em relacao ao plano original

Os testes ficam em backend/app/tests e o servidor usa `uvicorn main:app --app-dir backend/app`. POST /api/eventos retorna 201. O detector gera interacao_mao; eventos inserido/retirado podem ser publicados pela API, mas nao sao inferidos automaticamente pelo servico atual. Treino e captura exibem status sem progresso incremental; a galeria precisa ser recarregada apos captura/anotacao. A protecao de treino da API nao coordena processos externos: nunca iniciar treino na interface e no script simultaneamente.

## Correcao da conexao compartilhada - 2026-09-06

- Suite atual: 27 testes passaram, incluindo concorrencia, reconexao/fechamento de respostas, consumidores independentes, captura e evento WebSocket com inferencia simulada, parada sem frames.
- ESP32-CAM real em 192.168.15.59:81: dois consumidores MJPEG receberam tres partes cada; YOLO real processou frames; captura concluiu cinco imagens em pasta temporaria, sem alterar o dataset.
- No teste real: 39 frames recebidos, um leitor de origem, estado recebendo, monitor rodando sem erro. Nenhum evento foi observado na cena durante a janela do teste. O evento de interacao foi validado com deteccoes controladas nos testes automatizados.
- Queda/reconexao foi simulada; nao foi desligada fisicamente a camera. Checklist visual no navegador e interacao real com produtos continuam pendentes.

## Correcao de parada e galeria - 2026-09-06

- 31 testes passaram: inclui liberacao por consumidor, tres ciclos de inicio/parada, captura encerrando o leitor, desconexao MJPEG e JPEG com nome Unicode/espacos/caracteres especiais.
- Na ESP32-CAM real: cinco capturas temporarias retornaram HTTP 200 e decodificaram corretamente; o video permaneceu como consumidor ao terminar a captura. Ao liberar o video, o leitor encerrou. Reinicio e segunda parada tambem confirmados.
- As 97 imagens existentes foram consultadas e decodificadas sem falhas. O sintoma original de imagem quebrada nao foi reproduzido nesses arquivos.
- JavaScript validado com node --check. Teste da logica da galeria em Node com DOM simulado confirmou atualizacao apos captura, codificacao da URL e botao de nova tentativa. Nao equivale a teste visual em navegador.
- Nenhuma imagem de teste foi adicionada ao dataset permanente.


### LabelMe: janela ausente apos listar imagens

Diagnostico em 2026-09-06: o LabelMe aguardava um dialogo de erro durante a carga inicial, antes de mostrar a janela principal. Corrigidas 95 referencias imagePath nos JSONs para ../raw_frames/arquivo.jpg; todas as anotacoes foram lidas pelo proprio LabelMe sem erro. O endpoint de anotacao agora verifica e repara referencias quebradas quando encontra uma unica imagem correspondente, antes de iniciar o processo. Classes e caixas permanecem preservadas.

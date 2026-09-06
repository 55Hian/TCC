# Fase 6 - registro de validacao (2026-09-06)

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

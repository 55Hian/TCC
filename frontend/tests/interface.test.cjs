const test = require("node:test");
const assert = require("node:assert/strict");
const { criarAmbiente, concluirPromessas } = require("./ambiente.cjs");

const estadoMonitor = {
  status: "rodando", erro: null, modelo_configurado: "yolo12n",
  camera: { status: "recebendo", consumidores: ["monitoramento"] },
};

test("HTTP mantém corpo, cabeçalhos e erros com ou sem JSON", async () => {
  const ambiente = criarAmbiente({ "/dados": { valor: 1 } });
  assert.equal((await ambiente.contexto.obterJson("/dados")).valor, 1);
  await ambiente.contexto.enviarJson("/dados", { quantidade: 2 });
  assert.equal(ambiente.requisicoes[1].opcoes.body, '{"quantidade":2}');
  assert.equal(ambiente.requisicoes[1].opcoes.headers["Content-Type"], "application/json");
  await ambiente.contexto.enviarJson("/dados");
  assert.equal(ambiente.requisicoes[2].opcoes.body, undefined);
  ambiente.rotas["/dados"] = { respostaHttp: { ok: false, status: 400, json: async () => ({ detail: "Inválido" }) } };
  await assert.rejects(ambiente.contexto.enviarJson("/dados"), /Inválido/);
  await assert.rejects(ambiente.contexto.obterJson("/dados"), /GET \/dados -> 400/);
  ambiente.rotas["/dados"].respostaHttp.json = async () => { throw new Error("HTML"); };
  await assert.rejects(ambiente.contexto.enviarJson("/dados"), /POST \/dados -> 400/);
});

test("monitor inicia, para, recebe eventos e reconecta após fechamento", async () => {
  const ambiente = criarAmbiente({
    "/api/eventos": { eventos: [] }, "/api/monitoramento/status": estadoMonitor,
    "/api/monitoramento/iniciar": { iniciado: true }, "/api/monitoramento/parar": { parado: true },
  });
  ambiente.carregar("dashboard");
  await concluirPromessas();
  assert.equal(ambiente.elemento("stream-img").style.visibility, "visible");
  await ambiente.elemento("btn-iniciar-monitor").listeners.click();
  assert.match(ambiente.elemento("stream-img").src, /^\/api\/stream/);
  await ambiente.elemento("btn-parar-monitor").listeners.click();
  assert.equal(ambiente.elemento("stream-img").src, undefined);
  assert.equal(ambiente.conexoes[0].url, "wss://inventario.local/ws/eventos");
  ambiente.conexoes[0].onmessage({ data: JSON.stringify({
    timestamp: "2026-09-13T12:00:00Z", tipo: "interacao_mao", produto: "cha", quantidade: 1,
  }) });
  assert.match(ambiente.elemento("lista-eventos").children[0].textContent, /cha/);
  ambiente.conexoes[0].onclose();
  assert.equal(ambiente.atrasos[0].tempo, 3000);
  ambiente.atrasos[0].funcao();
  assert.equal(ambiente.conexoes.length, 2);
});

test("falha de monitoramento informa erro e mantém botões utilizáveis", async () => {
  const ambiente = criarAmbiente({
    "/api/eventos": { eventos: [] }, "/api/monitoramento/status": new Error("Offline"),
    "/api/monitoramento/iniciar": new Error("Sem conexão"),
  });
  ambiente.carregar("dashboard");
  await concluirPromessas();
  await ambiente.elemento("btn-iniciar-monitor").listeners.click();
  assert.deepEqual(ambiente.alertas, ["Sem conexão"]);
  assert.equal(ambiente.elemento("stream-status").textContent, "erro");
});

test("galeria preserva Unicode, repete imagem e recarrega após captura", async () => {
  const ambiente = criarAmbiente({
    "/api/dataset/imagens": { imagens: [{ nome: "ação #1.jpg", versao: "2", anotado: true }] },
    "/api/dataset/capturar/status": { status: "ocioso", total: 0 },
    "/api/dataset/capturar": { iniciado: true },
  });
  ambiente.carregar("dataset");
  await concluirPromessas();
  const [imagem, legenda, repetir] = ambiente.elemento("galeria").children[0].children;
  assert.match(imagem.src, /a%C3%A7%C3%A3o%20%231.jpg/);
  assert.match(legenda.textContent, /anotado/);
  imagem.onerror();
  assert.equal(repetir.hidden, false);
  repetir.onclick();
  assert.match(imagem.src, /&retry=/);
  imagem.onload();
  assert.equal(repetir.hidden, true);
  ambiente.elemento("input-intervalo").value = "2";
  ambiente.elemento("input-max-frames").value = "5";
  await ambiente.elemento("form-captura").listeners.submit({ preventDefault() {} });
  const envio = ambiente.requisicoes.find((item) => item.url === "/api/dataset/capturar");
  assert.deepEqual(JSON.parse(envio.opcoes.body), { intervalo: 2, max_frames: 5 });
  ambiente.rotas["/api/dataset/capturar/status"] = { status: "concluido", total: 5 };
  await ambiente.contexto.atualizarStatusCaptura();
  assert.equal(ambiente.requisicoes.filter((item) => item.url === "/api/dataset/imagens").length, 2);
});

test("treinamento envia parâmetros e mostra rejeição da API", async () => {
  const ambiente = criarAmbiente({
    "/api/modelos": { modelo_ativo: "yolo12n", modelos: [{ nome: "yolo12n", disponivel: true }] },
    "/api/treino/status": { status: "ocioso", modelo_ativo: "yolo12n" },
    "/api/treino/start": new Error("Treino em andamento"),
  });
  ambiente.carregar("treino");
  await concluirPromessas();
  for (const [nome, valor] of Object.entries({ epochs: "50", imgsz: "640", fraction: "0.5" })) {
    ambiente.elemento("input-" + nome).value = valor;
  }
  await ambiente.elemento("form-treino").listeners.submit({ preventDefault() {} });
  const envio = ambiente.requisicoes.find((item) => item.url === "/api/treino/start");
  assert.deepEqual(JSON.parse(envio.opcoes.body), { epochs: 50, imgsz: 640, fraction: 0.5 });
  assert.deepEqual(ambiente.alertas, ["Treino em andamento"]);
  assert.equal(ambiente.elemento("select-modelo").disabled, true);
});

test("experimentos exibem nome literal e gráfico opcional", async () => {
  const ambiente = criarAmbiente({ "/api/treino/experimentos": { experimentos: [
    { nome: "<ensaio>", tem_pesos: true, tem_resultados: true, grafico_url: "/grafico.png" },
    { nome: "sem gráfico", tem_pesos: false, tem_resultados: true },
  ] } });
  ambiente.carregar("experimentos");
  await concluirPromessas();
  const cartoes = ambiente.elemento("lista-experimentos").children;
  assert.equal(cartoes[0].children[0].textContent, "<ensaio>");
  assert.equal(cartoes[0].children[2].src, "/grafico.png");
  assert.equal(cartoes[1].children.length, 2);
});

test("abas alternam conteúdo e botão selecionado", () => {
  const ambiente = criarAmbiente();
  for (const nome of ["monitor", "treino"]) {
    const botao = ambiente.elemento("botao-" + nome);
    botao.seletor = ".tab-btn";
    botao.dataset.tab = nome;
    ambiente.elemento("tab-" + nome).seletor = ".tab-content";
  }
  ambiente.carregar("tabs");
  ambiente.elemento("botao-monitor").listeners.click();
  ambiente.elemento("botao-treino").listeners.click();
  assert.equal(ambiente.elemento("tab-monitor").classList.contains("active"), false);
  assert.equal(ambiente.elemento("tab-treino").classList.contains("active"), true);
});

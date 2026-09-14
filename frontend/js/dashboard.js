const listaEventos = document.getElementById("lista-eventos");
const imagemTransmissao = document.getElementById("stream-img");
const statusTransmissao = document.getElementById("stream-status");
const botaoIniciarMonitor = document.getElementById("btn-iniciar-monitor");
const botaoPararMonitor = document.getElementById("btn-parar-monitor");

function adicionarEventoNaLista(evento) {
  const item = document.createElement("li");
  const hora = new Date(evento.timestamp).toLocaleTimeString("pt-BR");
  item.textContent = `[${hora}] ${evento.tipo} — ${evento.produto} (x${evento.quantidade})`;
  listaEventos.appendChild(item);
}

async function carregarEventosIniciais() {
  const { eventos } = await obterJson("/api/eventos");
  eventos.forEach(adicionarEventoNaLista);
}

function conectarWebSocket() {
  const protocolo = location.protocol === "https:" ? "wss" : "ws";
  const conexao = new WebSocket(`${protocolo}://${location.host}/ws/eventos`);
  conexao.onmessage = (mensagem) => adicionarEventoNaLista(JSON.parse(mensagem.data));
  // Uma conexão fechada é refeita após três segundos, sem bloquear os botões.
  conexao.onclose = () => setTimeout(conectarWebSocket, 3000);
}

function exibirStatusMonitor({ status, erro, camera, modelo_configurado, modelo_carregado }) {
  const modelo = modelo_carregado || modelo_configurado;
  const consumidores = camera.consumidores.join(", ") || "sem consumidores";
  statusTransmissao.textContent = `${status} | modelo: ${modelo} | camera: ${camera.status} (${consumidores})`
    + (erro ? ` | ${erro}` : "");
  imagemTransmissao.style.visibility = camera.status === "recebendo" ? "visible" : "hidden";
}

async function atualizarStatusMonitor() {
  try {
    exibirStatusMonitor(await obterJson("/api/monitoramento/status"));
  } catch (erro) {
    statusTransmissao.textContent = "erro";
  }
}

function interromperTransmissao() {
  imagemTransmissao.src = "data:,";
  imagemTransmissao.removeAttribute("src");
}

async function alterarMonitoramento(acao) {
  if (acao === "iniciar") {
    imagemTransmissao.src = "/api/stream?_=" + Date.now();
  } else {
    interromperTransmissao();
  }
  try {
    await enviarJson(`/api/monitoramento/${acao}`);
  } catch (erro) {
    alert(erro.message);
  }
  await atualizarStatusMonitor();
}

botaoIniciarMonitor.addEventListener("click", () => alterarMonitoramento("iniciar"));
botaoPararMonitor.addEventListener("click", () => alterarMonitoramento("parar"));

carregarEventosIniciais().catch(() => { statusTransmissao.textContent = "erro"; });
conectarWebSocket();
atualizarStatusMonitor();
setInterval(atualizarStatusMonitor, 5000);

const listaEventos = document.getElementById("lista-eventos");
const streamImg = document.getElementById("stream-img");
const streamStatus = document.getElementById("stream-status");
const btnIniciarMonitor = document.getElementById("btn-iniciar-monitor");
const btnPararMonitor = document.getElementById("btn-parar-monitor");

function adicionarEventoNaLista(evento) {
  const li = document.createElement("li");
  const hora = new Date(evento.timestamp).toLocaleTimeString("pt-BR");
  li.textContent = `[${hora}] ${evento.tipo} — ${evento.produto} (x${evento.quantidade})`;
  listaEventos.appendChild(li);
}

async function carregarEventosIniciais() {
  const { eventos } = await apiGet("/api/eventos");
  eventos.forEach(adicionarEventoNaLista);
}

function conectarWebSocket() {
  const protocolo = location.protocol === "https:" ? "wss" : "ws";
  const ws = new WebSocket(`${protocolo}://${location.host}/ws/eventos`);
  ws.onmessage = (msg) => adicionarEventoNaLista(JSON.parse(msg.data));
  ws.onclose = () => setTimeout(conectarWebSocket, 3000);
}

async function atualizarStatusMonitor() {
  try {
    const { status } = await apiGet("/api/monitoramento/status");
    streamStatus.textContent = status;
  } catch (e) {
    streamStatus.textContent = "erro";
  }
}

btnIniciarMonitor.addEventListener("click", async () => {
  streamImg.src = "/api/stream?_=" + Date.now();
  try {
    await apiPost("/api/monitoramento/iniciar");
  } catch (e) {
    alert(e.message);
  }
  atualizarStatusMonitor();
});

btnPararMonitor.addEventListener("click", async () => {
  try {
    await apiPost("/api/monitoramento/parar");
  } catch (e) {
    alert(e.message);
  }
  streamImg.removeAttribute("src");
  atualizarStatusMonitor();
});

carregarEventosIniciais();
conectarWebSocket();
atualizarStatusMonitor();
setInterval(atualizarStatusMonitor, 5000);

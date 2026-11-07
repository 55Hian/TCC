import { api, addCell, formatTime } from "../api.js";

let frameUrl;
let loading = false;

function renderTable(element, rows, columns, empty) {
  element.replaceChildren();
  if (!rows.length) {
    const row = document.createElement("tr");
    addCell(row, empty, "muted-cell").colSpan = columns.length;
    element.append(row);
    return;
  }
  for (const record of rows) {
    const row = document.createElement("tr");
    for (const column of columns) column(row, record);
    element.append(row);
  }
}

function renderVideo(row, correlation) {
  const cell = document.createElement("td");
  if (correlation.video_status === "concluida" && correlation.video_url) {
    const link = document.createElement("a");
    link.href = correlation.video_url;
    link.target = "_blank";
    link.rel = "noreferrer";
    link.textContent = `Ver clipe · #${correlation.id_event}`;
    link.title = correlation.video_path;
    cell.append(link);
  } else {
    cell.textContent = correlation.video_path || correlation.video_status || "Sem clipe";
  }
  row.append(cell);
}

async function refreshFrame() {
  try {
    const response = await fetch(`/api/monitoramento/frame?t=${Date.now()}`);
    if (!response.ok) return;
    if (frameUrl) URL.revokeObjectURL(frameUrl);
    frameUrl = URL.createObjectURL(await response.blob());
    document.getElementById("dashboardCameraFrame").src = frameUrl;
    document.getElementById("dashboardCameraFrame").hidden = false;
    document.getElementById("dashboardCameraPlaceholder").hidden = true;
    document.getElementById("dashboardLiveLabel").hidden = false;
  } catch { /* A próxima atualização tenta novamente. */ }
}

export function init() {}

export async function refresh() {
  if (loading) return;
  loading = true;
  try {
    const [data, monitor] = await Promise.all([
      api("/api/dashboard"),
      api("/api/monitoramento/status"),
    ]);
    document.getElementById("kpiEvents").textContent = data.resumo.interacoes_24h;
    document.getElementById("kpiScale").textContent = data.resumo.variacoes_24h;
    document.getElementById("kpiCorrelations").textContent = data.resumo.correlacoes_24h;
    document.getElementById("kpiVideos").textContent = data.resumo.clipes_pendentes_ou_com_erro;
    document.getElementById("dashboardMonitorState").textContent = monitor.status;
    document.getElementById("dashboardMonitorState").className = `state-pill ${monitor.status === "rodando" ? "good" : monitor.status === "erro" ? "bad" : "neutral"}`;
    document.getElementById("dashboardModel").textContent = `Modelo ativo: ${data.modelo_ativo || "—"}`;
    if (monitor.status === "rodando") await refreshFrame();
    else {
      document.getElementById("dashboardCameraFrame").hidden = true;
      document.getElementById("dashboardLiveLabel").hidden = true;
      document.getElementById("dashboardCameraPlaceholder").hidden = false;
      document.querySelector("#dashboardCameraPlaceholder strong").textContent = monitor.status === "erro" ? "Falha no monitoramento" : "Monitoramento parado";
      document.querySelector("#dashboardCameraPlaceholder span:last-child").textContent = monitor.erro || "Inicie o monitoramento gôndola para ver detecções e pontos da mão.";
    }
    renderTable(document.getElementById("dashboardEvents"), data.eventos, [
      (row, item) => addCell(row, formatTime(item.timestamp)),
      (row, item) => addCell(row, item.produto),
      (row, item) => addCell(row, item.id),
    ], "Nenhuma interação registrada.");
    renderTable(document.getElementById("dashboardScale"), data.balanca, [
      (row, item) => addCell(row, formatTime(item.timestamp)),
      (row, item) => addCell(row, item.variacao_peso),
      (row, item) => addCell(row, item.id),
    ], "Nenhuma variação registrada.");
    renderTable(document.getElementById("dashboardCorrelations"), data.correlacoes, [
      (row, item) => addCell(row, formatTime(item.timestamp_balanca)),
      (row, item) => addCell(row, item.nome_produto || "Produto removido"),
      (row, item) => addCell(row, item.peso_produto),
      renderVideo,
    ], "Nenhuma correlação encontrada.");
    document.getElementById("dashboardUpdated").textContent = `Atualizado às ${new Intl.DateTimeFormat("pt-BR", { timeStyle: "medium" }).format(new Date())}`;
  } catch (error) {
    document.getElementById("dashboardUpdated").textContent = `Não foi possível atualizar o painel: ${error.message}`;
  } finally {
    loading = false;
  }
}

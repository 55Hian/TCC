import { api, showToast, statePill, elements, startStream, stopStream, formatMetrics } from "../api.js";
const { monitorStart, monitorStop, monitorError, monitorState, modelSelect, activateModel, cameraFrame, cameraPlaceholder, liveLabel, monitorMetrics } = elements("monitorStart", "monitorStop", "monitorError", "monitorState", "modelSelect", "activateModel", "cameraFrame", "cameraPlaceholder", "liveLabel", "monitorMetrics");

let wasActive = false;

export function init() {
  monitorStart.addEventListener("click", async () => {
    try { await api("/api/monitoramento/iniciar", { method: "POST", body: "{}" }); showToast("Monitoramento iniciado."); await refresh(); }
    catch (error) { monitorError.textContent = error.message; showToast(error.message, true); }
  });
  monitorStop.addEventListener("click", async () => {
    try { await api("/api/monitoramento/parar", { method: "POST", body: "{}" }); showToast("Monitoramento parado."); await refresh(); }
    catch (error) { showToast(error.message, true); }
  });
}

function showStream() {
  startStream(cameraFrame);
  cameraFrame.hidden = false;
  cameraPlaceholder.hidden = true;
  liveLabel.hidden = false;
}

export function leave() {
  stopStream(cameraFrame);
}

export async function refresh() {
  try {
    const result = await api("/api/monitoramento/status");
    const active = ["rodando", "iniciando", "aguardando_camera"].includes(result.status);
    statePill(monitorState, result.status);
    monitorStart.disabled = active;
    monitorStop.disabled = !active;
    modelSelect.disabled = active;
    activateModel.disabled = active;
    monitorError.textContent = result.erro || "";
    monitorMetrics.textContent = active ? formatMetrics(result.metricas) : "";
    if (!active) stopStream(cameraFrame);
    if (result.status === "erro" || (!active && wasActive)) {
      cameraPlaceholder.hidden = false;
      cameraPlaceholder.querySelector("strong").textContent = result.status === "erro" ? "Não foi possível iniciar" : "Câmera desligada";
      cameraPlaceholder.querySelector("span:last-child").textContent = result.erro || "Inicie o monitoramento para ver o vídeo.";
      cameraFrame.hidden = true;
      liveLabel.hidden = true;
    }
    if (active && !wasActive) stopStream(cameraFrame); // nova execução: reabre a conexão
    wasActive = active;
    if (result.status === "rodando") showStream();
  } catch (error) { monitorError.textContent = error.message; }
}

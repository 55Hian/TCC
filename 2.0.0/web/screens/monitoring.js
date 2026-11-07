import { api, showToast, statePill, elements } from "../api.js";
const { monitorStart, monitorStop, monitorError, monitorState, modelSelect, activateModel, cameraFrame, cameraPlaceholder, liveLabel } = elements("monitorStart", "monitorStop", "monitorError", "monitorState", "modelSelect", "activateModel", "cameraFrame", "cameraPlaceholder", "liveLabel");

let frameUrl;
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

async function showFrame() {
  try {
    const response = await fetch(`/api/monitoramento/frame?t=${Date.now()}`);
    if (!response.ok) return;
    if (frameUrl) URL.revokeObjectURL(frameUrl);
    frameUrl = URL.createObjectURL(await response.blob());
    cameraFrame.src = frameUrl;
    cameraFrame.hidden = false;
    cameraPlaceholder.hidden = true;
    liveLabel.hidden = false;
  } catch { /* Preserva o último frame exibido. */ }
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
    if (result.status === "erro" || (!active && wasActive)) {
      cameraPlaceholder.hidden = false;
      cameraPlaceholder.querySelector("strong").textContent = result.status === "erro" ? "Não foi possível iniciar" : "Câmera desligada";
      cameraPlaceholder.querySelector("span:last-child").textContent = result.erro || "Inicie o monitoramento para ver o vídeo.";
      cameraFrame.hidden = true;
      liveLabel.hidden = true;
    }
    wasActive = active;
    if (active) await showFrame();
  } catch (error) { monitorError.textContent = error.message; }
}

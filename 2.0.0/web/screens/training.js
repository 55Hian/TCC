import { api, showToast, statePill, elements } from "../api.js";
const { captureForm, captureButton, captureInterval, captureCount, captureFeedback, labelmeButton, labelmeFeedback, trainForm, trainButton, trainEpochs, trainSize, trainFeedback, trainingState, modelSelect, activateModel, monitorModel, modelMessage } = elements("captureForm", "captureButton", "captureInterval", "captureCount", "captureFeedback", "labelmeButton", "labelmeFeedback", "trainForm", "trainButton", "trainEpochs", "trainSize", "trainFeedback", "trainingState", "modelSelect", "activateModel", "monitorModel", "modelMessage");

export function init() {
  document.getElementById("captureForm").addEventListener("submit", async (event) => {
    event.preventDefault();
    await runAction("captureButton", "Captura iniciada.", () => api("/api/treinamento/capturar", {
      method: "POST", body: JSON.stringify({ intervalo: Number(captureInterval.value), quantidade: Number(captureCount.value) }),
    }));
    refresh();
  });
  document.getElementById("labelmeButton").addEventListener("click", async () => {
    try {
      const result = await api("/api/treinamento/labelme", { method: "POST", body: "{}" });
      document.getElementById("labelmeFeedback").textContent = `Labelme aberto (processo ${result.pid}).`;
      showToast("Labelme aberto no computador da API.");
    } catch (error) { showToast(error.message, true); }
  });
  document.getElementById("trainForm").addEventListener("submit", async (event) => {
    event.preventDefault();
    await runAction("trainButton", "Treinamento iniciado.", () => api("/api/treinamento/treinar", {
      method: "POST", body: JSON.stringify({ epochs: Number(trainEpochs.value), imgsz: Number(trainSize.value) }),
    }));
    refresh();
  });
  document.getElementById("activateModel").addEventListener("click", async () => {
    try {
      const result = await api("/api/modelos/ativar", { method: "POST", body: JSON.stringify({ nome: modelSelect.value }) });
      document.getElementById("modelMessage").textContent = `Modelo ${result.modelo_ativo} selecionado.`;
      showToast("Modelo ativo atualizado.");
      await loadModels();
    } catch (error) { showToast(error.message, true); }
  });
}

async function runAction(buttonId, message, action) {
  const button = document.getElementById(buttonId);
  button.disabled = true;
  try { await action(); showToast(message); }
  catch (error) { showToast(error.message, true); button.disabled = false; }
}

async function loadModels() {
  try {
    const result = await api("/api/modelos");
    const select = document.getElementById("modelSelect");
    select.replaceChildren();
    for (const item of result.modelos) {
      const option = document.createElement("option");
      option.value = item.nome;
      option.textContent = item.treinado ? item.nome : `${item.nome} · não treinado`;
      option.disabled = !item.treinado;
      option.selected = item.nome === result.modelo_ativo;
      select.append(option);
    }
    document.getElementById("monitorModel").textContent = result.modelo_ativo;
  } catch (error) { document.getElementById("modelMessage").textContent = error.message; }
}

export async function refresh() {
  try {
    const [capture, training] = await Promise.all([
      api("/api/treinamento/captura/status"), api("/api/treinamento/status"),
    ]);
    captureButton.disabled = capture.status === "rodando";
    if (capture.status === "concluido") captureFeedback.textContent = `${capture.total} frame(s) capturado(s).`;
    if (capture.status === "erro") captureFeedback.textContent = capture.erro;
    statePill(trainingState, training.status);
    trainButton.disabled = training.status === "rodando";
    if (training.status === "rodando") trainFeedback.textContent = "Treinamento em andamento…";
    if (training.status === "concluido" && training.resultado) {
      trainFeedback.textContent = `Pesos prontos: ${training.resultado.pesos}`;
      await loadModels();
    }
    if (training.status === "erro") trainFeedback.textContent = training.erro;
    await loadModels();
  } catch (error) { trainingState.textContent = error.message; }
}

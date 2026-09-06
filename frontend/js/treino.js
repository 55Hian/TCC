const selectModelo = document.getElementById("select-modelo");
const formTreino = document.getElementById("form-treino");
const treinoStatusEl = document.getElementById("treino-status");

async function carregarModelos() {
  const { pretreinados } = await apiGet("/api/modelos");
  selectModelo.innerHTML = pretreinados
    .map((m) => `<option value="${m.nome}" ${m.em_uso ? "selected" : ""}>${m.nome} (${m.tamanho_mb} MB)</option>`)
    .join("");
}

async function atualizarStatusTreino() {
  const { status, erro } = await apiGet("/api/treino/status");
  treinoStatusEl.textContent = `Status: ${status}` + (erro ? ` — erro: ${erro}` : "");
}

formTreino.addEventListener("submit", async (ev) => {
  ev.preventDefault();
  try {
    await apiPost("/api/treino/start", {
      base_model: selectModelo.value,
      epochs: Number(document.getElementById("input-epochs").value),
      imgsz: Number(document.getElementById("input-imgsz").value),
      fraction: Number(document.getElementById("input-fraction").value),
    });
  } catch (e) {
    alert(e.message);
  }
  atualizarStatusTreino();
});

carregarModelos();
atualizarStatusTreino();
setInterval(atualizarStatusTreino, 4000);

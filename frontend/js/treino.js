const selectModelo = document.getElementById("select-modelo");
const formTreino = document.getElementById("form-treino");
const treinoStatusEl = document.getElementById("treino-status");

async function carregarModelos() {
  const { modelo_ativo, modelos } = await apiGet("/api/modelos");
  selectModelo.replaceChildren();
  const modelo = modelos.find((m) => m.nome === modelo_ativo);
  const option = document.createElement("option");
  option.value = modelo_ativo;
  option.textContent = modelo_ativo + (modelo?.disponivel ? " — treino e inferência" : " — pesos ausentes");
  selectModelo.appendChild(option);
  selectModelo.disabled = true;
  selectModelo.title = "Altere MODELO_ATIVO em config.py e reinicie o backend.";
}

async function atualizarStatusTreino() {
  const { status, erro, modelo_ativo } = await apiGet("/api/treino/status");
  treinoStatusEl.textContent = `Modelo: ${modelo_ativo} · Status: ${status}` + (erro ? ` — erro: ${erro}` : "");
}

formTreino.addEventListener("submit", async (ev) => {
  ev.preventDefault();
  try {
    await apiPost("/api/treino/start", {
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

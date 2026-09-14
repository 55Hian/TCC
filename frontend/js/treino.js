const seletorModelo = document.getElementById("select-modelo");
const formularioTreino = document.getElementById("form-treino");
const statusTreino = document.getElementById("treino-status");

async function carregarModelos() {
  const { modelo_ativo, modelos } = await obterJson("/api/modelos");
  seletorModelo.replaceChildren();
  const modelo = modelos.find((m) => m.nome === modelo_ativo);
  const opcao = document.createElement("option");
  opcao.value = modelo_ativo;
  opcao.textContent = modelo_ativo + (modelo?.disponivel ? " — treino e inferência" : " — pesos ausentes");
  seletorModelo.appendChild(opcao);
  seletorModelo.disabled = true;
  seletorModelo.title = "Altere MODELO_ATIVO em config.py e reinicie o backend.";
}

async function atualizarStatusTreino() {
  const { status, erro, modelo_ativo } = await obterJson("/api/treino/status");
  statusTreino.textContent = `Modelo: ${modelo_ativo} · Status: ${status}` + (erro ? ` — erro: ${erro}` : "");
}

formularioTreino.addEventListener("submit", async (evento) => {
  evento.preventDefault();
  try {
    await enviarJson("/api/treino/start", {
      epochs: Number(document.getElementById("input-epochs").value),
      imgsz: Number(document.getElementById("input-imgsz").value),
      fraction: Number(document.getElementById("input-fraction").value),
    });
  } catch (erro) {
    alert(erro.message);
  }
  await consultarTreino();
});

async function consultarTreino() {
  try {
    await atualizarStatusTreino();
  } catch (erro) {
    statusTreino.textContent = erro.message;
  }
}

carregarModelos().catch((erro) => { statusTreino.textContent = erro.message; });
consultarTreino();
setInterval(consultarTreino, 4000);

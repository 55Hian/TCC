const listaExperimentosEl = document.getElementById("lista-experimentos");

async function carregarExperimentos() {
  const { experimentos } = await apiGet("/api/treino/experimentos");
  listaExperimentosEl.innerHTML = experimentos
    .map(
      (exp) => `
      <div class="card">
        <h3>${exp.nome}</h3>
        <p>Pesos: ${exp.tem_pesos ? "sim" : "nao"} · Resultados: ${exp.tem_resultados ? "sim" : "nao"}</p>
        ${
          exp.tem_resultados
            ? `<img class="grafico" src="/static/experiments/${exp.nome}/results.png" alt="resultados ${exp.nome}" loading="lazy">`
            : ""
        }
      </div>`
    )
    .join("");
}

carregarExperimentos();

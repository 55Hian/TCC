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
          exp.grafico_url
            ? `<img class="grafico" src="${exp.grafico_url}" alt="resultados ${exp.nome}" loading="lazy">`
            : ""
        }
      </div>`
    )
    .join("");
}

carregarExperimentos();

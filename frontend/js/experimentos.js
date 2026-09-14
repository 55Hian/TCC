const listaExperimentos = document.getElementById("lista-experimentos");

function criarCartaoExperimento(experimento) {
  const cartao = document.createElement("div");
  cartao.className = "card";
  const titulo = document.createElement("h3");
  titulo.textContent = experimento.nome;
  const descricao = document.createElement("p");
  descricao.textContent = `Pesos: ${experimento.tem_pesos ? "sim" : "nao"} · Resultados: ${experimento.tem_resultados ? "sim" : "nao"}`;
  cartao.append(titulo, descricao);
  if (experimento.grafico_url) {
    const grafico = document.createElement("img");
    grafico.className = "grafico";
    grafico.src = experimento.grafico_url;
    grafico.alt = `resultados ${experimento.nome}`;
    grafico.loading = "lazy";
    cartao.appendChild(grafico);
  }
  return cartao;
}

async function carregarExperimentos() {
  const { experimentos } = await obterJson("/api/treino/experimentos");
  listaExperimentos.replaceChildren(...experimentos.map(criarCartaoExperimento));
}

carregarExperimentos().catch((erro) => { listaExperimentos.textContent = erro.message; });

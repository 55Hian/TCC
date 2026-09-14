const botoesAbas = document.querySelectorAll(".tab-btn");
const conteudosAbas = document.querySelectorAll(".tab-content");

function selecionarAba(botao) {
  botoesAbas.forEach((item) => item.classList.remove("active"));
  conteudosAbas.forEach((conteudo) => conteudo.classList.remove("active"));
  botao.classList.add("active");
  document.getElementById(`tab-${botao.dataset.tab}`).classList.add("active");
}

botoesAbas.forEach((botao) => {
  botao.addEventListener("click", () => selecionarAba(botao));
});

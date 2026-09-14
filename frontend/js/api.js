// Centraliza envio e leitura JSON para as telas usarem o mesmo fluxo HTTP.
async function requisitarJson(caminho, metodo, corpo) {
  const opcoes = { method: metodo };
  if (metodo === "POST") {
    opcoes.headers = { "Content-Type": "application/json" };
    opcoes.body = corpo !== undefined ? JSON.stringify(corpo) : undefined;
  }

  const resposta = await fetch(caminho, opcoes);
  if (!resposta.ok) {
    // O FastAPI informa o motivo em "detail"; respostas sem JSON usam o status.
    const detalhe = metodo === "POST"
      ? await resposta.json().catch(() => ({}))
      : {};
    throw new Error(detalhe.detail || `${metodo} ${caminho} -> ${resposta.status}`);
  }
  return resposta.json();
}

function obterJson(caminho) {
  return requisitarJson(caminho, "GET");
}

function enviarJson(caminho, corpo) {
  return requisitarJson(caminho, "POST", corpo);
}

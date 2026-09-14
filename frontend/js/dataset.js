const formularioCaptura = document.getElementById("form-captura");
const statusCaptura = document.getElementById("captura-status");
const galeria = document.getElementById("galeria");
const totalGaleria = document.getElementById("galeria-total");

let capturaAnterior = null;
let recarregarAposCaptura = false;

async function atualizarStatusCaptura() {
  const { status, erro, total } = await obterJson("/api/dataset/capturar/status");
  const terminou = status === "concluido" || status === "erro";
  if (terminou && (recarregarAposCaptura || capturaAnterior !== status)) {
    await carregarGaleria();
    recarregarAposCaptura = false;
  }
  capturaAnterior = status;
  statusCaptura.textContent = `Status: ${status} (total capturado: ${total})` + (erro ? ` — erro: ${erro}` : "");
}

async function consultarCaptura() {
  try {
    await atualizarStatusCaptura();
  } catch (erro) {
    statusCaptura.textContent = erro.message;
  }
}

formularioCaptura.addEventListener("submit", async (evento) => {
  evento.preventDefault();
  try {
    recarregarAposCaptura = true;
    await enviarJson("/api/dataset/capturar", {
      intervalo: Number(document.getElementById("input-intervalo").value),
      max_frames: Number(document.getElementById("input-max-frames").value),
    });
  } catch (erro) {
    alert(erro.message);
  }
  await consultarCaptura();
});

document.getElementById("btn-abrir-labelme").addEventListener("click", async () => {
  try {
    await enviarJson("/api/dataset/anotar");
    alert("LabelMe aberto em uma janela separada.");
  } catch (erro) {
    alert(erro.message);
  }
});

function criarMiniatura(item) {
  const figura = document.createElement("figure");
  figura.className = `thumb ${item.anotado ? "anotado" : "pendente"}`;
  const imagem = document.createElement("img");
  imagem.loading = "lazy";
  imagem.alt = item.nome;
  const url = `/api/dataset/imagens/${encodeURIComponent(item.nome)}?v=${encodeURIComponent(item.versao || "")}`;
  const legenda = document.createElement("figcaption");
  legenda.textContent = `${item.anotado ? "anotado" : "pendente"} - ${item.nome}`;
  const botaoRepetir = document.createElement("button");
  botaoRepetir.type = "button";
  botaoRepetir.textContent = "Imagem indisponivel. Tentar novamente";
  botaoRepetir.hidden = true;
  // A nova consulta evita reaproveitar uma resposta de imagem que tenha falhado.
  imagem.onerror = () => { botaoRepetir.hidden = false; };
  imagem.onload = () => { botaoRepetir.hidden = true; };
  botaoRepetir.onclick = () => { imagem.src = `${url}&retry=${Date.now()}`; };
  imagem.src = url;
  figura.append(imagem, legenda, botaoRepetir);
  return figura;
}

async function carregarGaleria() {
  const { imagens } = await obterJson("/api/dataset/imagens");
  totalGaleria.textContent = imagens.length;
  const fragmento = document.createDocumentFragment();
  imagens.forEach((item) => fragmento.appendChild(criarMiniatura(item)));
  galeria.replaceChildren(fragmento);
}

carregarGaleria().catch((erro) => { statusCaptura.textContent = erro.message; });
consultarCaptura();
setInterval(consultarCaptura, 4000);

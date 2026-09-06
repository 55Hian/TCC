const formCaptura = document.getElementById("form-captura");
const capturaStatusEl = document.getElementById("captura-status");
const galeriaEl = document.getElementById("galeria");
const galeriaTotalEl = document.getElementById("galeria-total");

let capturaAnterior = null;
let recarregarAposCaptura = false;

async function atualizarStatusCaptura() {
  const { status, erro, total } = await apiGet("/api/dataset/capturar/status");
  if ((status === "concluido" || status === "erro") && (recarregarAposCaptura || capturaAnterior !== status)) {
    await carregarGaleria();
    recarregarAposCaptura = false;
  }
  capturaAnterior = status;
  capturaStatusEl.textContent = `Status: ${status} (total capturado: ${total})` + (erro ? ` — erro: ${erro}` : "");
}

formCaptura.addEventListener("submit", async (ev) => {
  ev.preventDefault();
  try {
    recarregarAposCaptura = true;
    await apiPost("/api/dataset/capturar", {
      intervalo: Number(document.getElementById("input-intervalo").value),
      max_frames: Number(document.getElementById("input-max-frames").value),
    });
  } catch (e) {
    alert(e.message);
  }
  atualizarStatusCaptura();
});

document.getElementById("btn-abrir-labelme").addEventListener("click", async () => {
  try {
    await apiPost("/api/dataset/anotar");
    alert("LabelMe aberto em uma janela separada.");
  } catch (e) {
    alert(e.message);
  }
});

async function carregarGaleria() {
  const { imagens } = await apiGet("/api/dataset/imagens");
  galeriaTotalEl.textContent = imagens.length;
  const fragmento = document.createDocumentFragment();
  for (const item of imagens) {
    const figure = document.createElement("figure");
    figure.className = `thumb ${item.anotado ? "anotado" : "pendente"}`;
    const img = document.createElement("img");
    img.loading = "lazy";
    img.alt = item.nome;
    const url = `/api/dataset/imagens/${encodeURIComponent(item.nome)}?v=${encodeURIComponent(item.versao || "")}`;
    const legenda = document.createElement("figcaption");
    legenda.textContent = `${item.anotado ? "anotado" : "pendente"} - ${item.nome}`;
    const retry = document.createElement("button");
    retry.type = "button";
    retry.textContent = "Imagem indisponivel. Tentar novamente";
    retry.hidden = true;
    img.onerror = () => { retry.hidden = false; };
    img.onload = () => { retry.hidden = true; };
    retry.onclick = () => { img.src = `${url}&retry=${Date.now()}`; };
    img.src = url;
    figure.append(img, legenda, retry);
    fragmento.appendChild(figure);
  }
  galeriaEl.replaceChildren(fragmento);
}

carregarGaleria();
atualizarStatusCaptura();
setInterval(() => atualizarStatusCaptura().catch((e) => { capturaStatusEl.textContent = e.message; }), 4000);

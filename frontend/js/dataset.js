const formCaptura = document.getElementById("form-captura");
const capturaStatusEl = document.getElementById("captura-status");
const galeriaEl = document.getElementById("galeria");
const galeriaTotalEl = document.getElementById("galeria-total");

async function atualizarStatusCaptura() {
  const { status, erro, total } = await apiGet("/api/dataset/capturar/status");
  capturaStatusEl.textContent = `Status: ${status} (total capturado: ${total})` + (erro ? ` — erro: ${erro}` : "");
}

formCaptura.addEventListener("submit", async (ev) => {
  ev.preventDefault();
  try {
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
  galeriaEl.innerHTML = imagens
    .map(
      (img) => `
      <figure class="thumb ${img.anotado ? "anotado" : "pendente"}">
        <img src="/api/dataset/imagens/${img.nome}" loading="lazy" alt="${img.nome}">
        <figcaption>${img.anotado ? "anotado" : "pendente"} · ${img.nome}</figcaption>
      </figure>`
    )
    .join("");
}

carregarGaleria();
atualizarStatusCaptura();
setInterval(atualizarStatusCaptura, 4000);

import { api, showToast, statePill, addCell } from "../api.js";
let lastClipId = null;

function formatDuration(value) {
  const seconds = Math.floor(value || 0);
  const hours = Math.floor(seconds / 3600);
  const minutes = Math.floor((seconds % 3600) / 60);
  if (hours) return `${hours} h ${minutes} min`;
  if (minutes) return `${minutes} min`;
  return `${seconds} s`;
}

export function init() {
  const clipTimestamp = document.getElementById("clipTimestamp");
  const clipForm = document.getElementById("clipForm");
  const clipButton = document.getElementById("clipButton");
  const clipCheckButton = document.getElementById("clipCheckButton");
  const clipEventId = document.getElementById("clipEventId");
  clipTimestamp.value = new Date(Date.now() - new Date().getTimezoneOffset() * 60000).toISOString().slice(0, 16);
  clipForm.addEventListener("submit", async (event) => {
    event.preventDefault();
    clipButton.disabled = true;
    try {
      const timestamp = new Date(clipTimestamp.value).toISOString();
      const result = await api("/api/camera-secundaria/gravar", {
        method: "POST",
        body: JSON.stringify({ id_evento: Number(document.getElementById("clipEventId").value), timestamp }),
      });
      lastClipId = result.id_evento;
      showToast(`Clipe agendado para o evento ${result.id_evento}.`);
      await loadClip(result.id_evento);
      await refresh();
    } catch (error) {
      document.getElementById("clipResult").textContent = error.message;
      document.getElementById("clipResult").className = "inline-result error";
      showToast(error.message, true);
    } finally {
      clipButton.disabled = false;
    }
  });
  clipCheckButton.addEventListener("click", () => {
    const id = Number(clipEventId.value);
    if (!Number.isInteger(id) || id < 1) {
      document.getElementById("clipResult").textContent = "Informe um ID de evento válido.";
      document.getElementById("clipResult").className = "inline-result error";
      return;
    }
    loadClip(id);
  });
}

async function loadClip(id) {
  try {
    const clip = await api(`/api/camera-secundaria/gravacoes/${id}`);
    const body = document.getElementById("clipsTable");
    const row = document.createElement("tr");
    addCell(row, clip.id_evento);
    addCell(row, clip.status);
    addCell(row, clip.caminho || clip.erro || "Aguardando clipe");
    body.replaceChildren(row);
    document.getElementById("clipResult").textContent = "Estado atualizado.";
    document.getElementById("clipResult").className = "inline-result success";
  } catch (error) {
    document.getElementById("clipResult").textContent = error.message;
    document.getElementById("clipResult").className = "inline-result error";
  }
}

export async function refresh() {
  const details = document.getElementById("usbDetails");
  try {
    const status = await api("/api/camera-secundaria/status");
    statePill(document.getElementById("usbState"), status.status);
    details.textContent = status.erro ||
      `Armazenado: ${formatDuration(status.segundos_buffer)} / ${formatDuration(status.segundos_retencao)} · ` +
      `busca até ${formatDuration(status.segundos_retencao)} atrás · clipe: ${status.segundos_antes}s antes + ` +
      `${status.segundos_depois}s depois · ${status.megabytes_buffer} MB em disco`;
  } catch (error) {
    statePill(document.getElementById("usbState"), "erro");
    details.textContent = error.message;
  }
  if (lastClipId != null) await loadClip(lastClipId);
}

export async function api(path, options = {}) {
  const response = await fetch(path, {
    ...options,
    headers: { "Content-Type": "application/json", ...(options.headers || {}) },
  });
  const type = response.headers.get("content-type") || "";
  const body = type.includes("application/json") ? await response.json() : await response.text();
  if (!response.ok) {
    const detail = body && typeof body === "object" ? body.detail : body;
    throw new Error(detail || `Falha na API (${response.status})`);
  }
  return body;
}

export function formatTime(value) {
  if (!value) return "—";
  const date = new Date(value);
  return Number.isNaN(date.getTime())
    ? String(value)
    : new Intl.DateTimeFormat("pt-BR", { dateStyle: "short", timeStyle: "medium" }).format(date);
}

export function addCell(row, value, className = "") {
  const cell = document.createElement("td");
  cell.textContent = value == null || value === "" ? "—" : String(value);
  if (className) cell.className = className;
  row.append(cell);
  return cell;
}

export function showToast(message, error = false) {
  const toast = document.getElementById("toast");
  toast.textContent = message;
  toast.classList.toggle("error", error);
  toast.classList.add("show");
  clearTimeout(showToast.timer);
  showToast.timer = setTimeout(() => toast.classList.remove("show"), 3200);
}

export function statePill(element, state) {
  element.textContent = state || "indisponível";
  element.className = "state-pill";
  element.classList.add(["rodando", "agendada", "concluida"].includes(state) ? "busy" : ["parado", "concluida", "nao_solicitado"].includes(state) ? "good" : ["erro", "reconectando"].includes(state) ? "bad" : "neutral");
}

// Vídeo processado em MJPEG: uma conexão contínua por <img>, no lugar de buscar fotos a cada atualização.
export function startStream(img) {
  if (img.dataset.streaming === "1") return;
  img.dataset.streaming = "1";
  img.onerror = () => { delete img.dataset.streaming; };
  img.src = `/api/monitoramento/stream?t=${Date.now()}`;
}

export function stopStream(img) {
  delete img.dataset.streaming;
  img.onerror = null;
  img.removeAttribute("src");
}

export function formatMetrics(metrics) {
  if (!metrics || metrics.fps == null) return "";
  const stages = metrics.etapas_ms || {};
  return `${metrics.fps} FPS · YOLO ${stages.yolo ?? "—"} ms · mãos ${stages.maos ?? "—"} ms · latência ${metrics.latencia_ms} ms · ${metrics.dispositivo_yolo || "?"}`;
}

export function elements(...ids) {
  return Object.fromEntries(ids.map((id) => [id, document.getElementById(id)]));
}

import { api, showToast } from "./api.js";
import { init as initHome, refresh as refreshHome } from "./screens/home.js";
import { init as initEnvironment, refresh as refreshEnvironment } from "./screens/environment.js";
import { init as initTraining, refresh as refreshTraining } from "./screens/training.js";
import { init as initMonitoring, refresh as refreshMonitoring } from "./screens/monitoring.js";
import { init as initDatabase, refresh as refreshDatabase } from "./screens/database.js";
import { init as initProducts, refresh as refreshProducts } from "./screens/products.js";

const pages = {
  inicio: { title: "Início", description: "Resumo ao vivo das interações, da balança, das correlações e da inferência YOLO.", refresh: refreshHome },
  treinamento: { title: "Treinamento", description: "Capture imagens, anote e treine seu modelo YOLO.", refresh: refreshTraining },
  "monitoramento-gondola": { title: "Monitoramento gôndola", description: "Acompanhe e controle a câmera principal, as mãos e os produtos detectados.", refresh: refreshMonitoring },
  "monitoramento-ambiente": { title: "Monitoramento ambiente", description: "Acompanhe o buffer e os clipes da câmera secundária.", refresh: refreshEnvironment },
  dados: { title: "Dados do banco", description: "Visualize e administre as tabelas persistidas pela API.", refresh: refreshDatabase },
  produtos: { title: "Produtos", description: "Gerencie o catálogo associado às classes do modelo.", refresh: refreshProducts },
};

let activePage = "inicio";
let refreshTimer;

async function checkHealth() {
  try {
    await api("/api/health");
    document.getElementById("healthDot").className = "connection-dot online";
    document.getElementById("healthText").textContent = "API conectada";
  } catch {
    document.getElementById("healthDot").className = "connection-dot offline";
    document.getElementById("healthText").textContent = "API indisponível";
  }
}

function showPage(name) {
  activePage = pages[name] ? name : "inicio";
  document.querySelectorAll(".view").forEach((view) => {
    view.classList.toggle("active", view.id === `view-${activePage}`);
  });
  document.querySelectorAll(".app-nav [data-view]").forEach((link) => {
    const selected = link.dataset.view === activePage;
    link.classList.toggle("active", selected);
    if (selected) link.setAttribute("aria-current", "page");
    else link.removeAttribute("aria-current");
  });
  document.getElementById("pageTitle").textContent = pages[activePage].title;
  document.getElementById("pageDescription").textContent = pages[activePage].description;
  document.title = `${pages[activePage].title} · Inventário`;
  clearInterval(refreshTimer);
  pages[activePage].refresh();
  const refreshEvery = activePage === "monitoramento-gondola" ? 1200 : activePage === "inicio" ? 2500 : activePage === "monitoramento-ambiente" || activePage === "treinamento" ? 4000 : 0;
  if (refreshEvery) refreshTimer = setInterval(pages[activePage].refresh, refreshEvery);
}

function updateClock() {
  document.getElementById("localClock").textContent = new Intl.DateTimeFormat("pt-BR", {
    hour: "2-digit", minute: "2-digit", second: "2-digit",
  }).format(new Date());
}

initHome();
initEnvironment();
initTraining();
initMonitoring();
initDatabase();
initProducts();
document.querySelectorAll("[data-view]").forEach((link) => link.addEventListener("click", () => {
  if (location.hash === link.getAttribute("href")) showPage(link.dataset.view);
}));
window.addEventListener("hashchange", () => showPage(location.hash.slice(1)));
showPage(location.hash.slice(1));
updateClock();
checkHealth();
setInterval(updateClock, 1000);
setInterval(checkHealth, 10000);

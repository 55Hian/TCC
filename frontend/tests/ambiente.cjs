// Substitutos controlados de DOM, rede e relógios; nenhuma conexão real é aberta.
const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");

function criarElemento(tagName = "div") {
  const classes = new Set();
  return {
    tagName, children: [], style: {}, dataset: {}, listeners: {}, value: "",
    classList: {
      add: (nome) => classes.add(nome),
      remove: (nome) => classes.delete(nome),
      contains: (nome) => classes.has(nome),
    },
    append(...itens) {
      for (const item of itens) {
        if (item.tagName === "fragment") this.children.push(...item.children);
        else this.children.push(item);
      }
    },
    appendChild(item) { this.append(item); return item; },
    replaceChildren(...itens) { this.children = []; this.append(...itens); },
    removeAttribute(nome) { delete this[nome]; },
    addEventListener(nome, funcao) { this.listeners[nome] = funcao; },
  };
}

function criarAmbiente(rotas = {}) {
  const elementos = new Map();
  const requisicoes = [];
  const alertas = [];
  const atrasos = [];
  const intervalos = [];
  const conexoes = [];
  const elemento = (id) => {
    if (!elementos.has(id)) elementos.set(id, criarElemento());
    return elementos.get(id);
  };
  const contexto = vm.createContext({
    document: {
      getElementById: elemento,
      createElement: criarElemento,
      createDocumentFragment: () => criarElemento("fragment"),
      querySelectorAll: (seletor) => [...elementos.values()].filter((item) => item.seletor === seletor),
    },
    fetch: async (url, opcoes) => {
      requisicoes.push({ url, opcoes });
      const resultado = rotas[url];
      if (resultado instanceof Error) throw resultado;
      if (resultado === undefined) throw new Error("Rota simulada ausente: " + url);
      if (resultado.respostaHttp) return resultado.respostaHttp;
      return { ok: true, json: async () => resultado };
    },
    location: { protocol: "https:", host: "inventario.local" },
    WebSocket: class {
      constructor(url) { this.url = url; conexoes.push(this); }
    },
    setTimeout: (funcao, tempo) => atrasos.push({ funcao, tempo }),
    setInterval: (funcao, tempo) => intervalos.push({ funcao, tempo }),
    alert: (mensagem) => alertas.push(mensagem),
  });
  function carregar(nome) {
    const arquivo = path.join(__dirname, "../js", nome + ".js");
    vm.runInContext(fs.readFileSync(arquivo, "utf8"), contexto, { filename: arquivo });
  }
  carregar("api");
  return { contexto, elemento, carregar, requisicoes, alertas, atrasos, intervalos, conexoes, rotas };
}

const concluirPromessas = () => new Promise((resolve) => setImmediate(resolve));
module.exports = { criarAmbiente, concluirPromessas };

import { api, addCell, formatTime, showToast, elements } from "../api.js";
const { productForm, productCancel, productReload, productFormTitle, productSave, productMessage, productName, productClass, productWeight, productDescription, productActive, productRows } = elements("productForm", "productCancel", "productReload", "productFormTitle", "productSave", "productMessage", "productName", "productClass", "productWeight", "productDescription", "productActive", "productRows");

let products = [];
let editingId = null;

export function init() {
  productForm.addEventListener("submit", saveProduct);
  productCancel.addEventListener("click", resetForm);
  productReload.addEventListener("click", refresh);
}

function resetForm() {
  editingId = null;
  productForm.reset();
  productActive.checked = true;
  productFormTitle.textContent = "Novo produto";
  productSave.textContent = "Cadastrar produto";
  productCancel.hidden = true;
  productMessage.textContent = "";
}

async function saveProduct(event) {
  event.preventDefault();
  const data = {
    nome: productName.value.trim(), classe_modelo: productClass.value.trim(),
    peso: Number(productWeight.value), descricao: productDescription.value.trim(), ativo: productActive.checked,
  };
  try {
    await api(`/api/produtos${editingId == null ? "" : `/${editingId}`}`, {
      method: editingId == null ? "POST" : "PUT", body: JSON.stringify(data),
    });
    showToast(editingId == null ? "Produto cadastrado." : "Produto atualizado.");
    resetForm(); await refresh();
  } catch (error) { productMessage.textContent = error.message; productMessage.className = "inline-result error"; }
}

function renderProducts() {
  productRows.replaceChildren();
  if (!products.length) {
    const row = document.createElement("tr");
    addCell(row, "Nenhum produto cadastrado.", "muted-cell").colSpan = 9;
    productRows.append(row); return;
  }
  for (const product of products) {
    const row = document.createElement("tr");
    addCell(row, product.id); addCell(row, product.nome); addCell(row, product.classe_modelo); addCell(row, product.peso);
    addCell(row, product.descricao);
    addCell(row, product.ativo ? "Sim" : "Não"); addCell(row, formatTime(product.criado_em)); addCell(row, formatTime(product.atualizado_em));
    const actions = document.createElement("td"); actions.className = "row-actions";
    const edit = document.createElement("button"); edit.className = "text-button"; edit.textContent = "Editar";
    edit.addEventListener("click", () => {
      editingId = product.id; productName.value = product.nome; productClass.value = product.classe_modelo;
      productWeight.value = product.peso ?? "";
      productDescription.value = product.descricao; productActive.checked = product.ativo;
      productFormTitle.textContent = `Editar produto #${product.id}`; productSave.textContent = "Salvar alterações";
      productCancel.hidden = false; productName.focus();
    });
    const remove = document.createElement("button"); remove.className = "text-button danger-text"; remove.textContent = "Remover";
    remove.addEventListener("click", async () => {
      if (!window.confirm(`Remover o produto “${product.nome}”?`)) return;
      try { await api(`/api/produtos/${product.id}`, { method: "DELETE" }); showToast("Produto removido."); await refresh(); }
      catch (error) { showToast(error.message, true); }
    });
    actions.append(edit, remove); row.append(actions); productRows.append(row);
  }
}

export async function refresh() {
  try {
    const result = await api("/api/produtos"); products = result.produtos; renderProducts();
  } catch (error) { productMessage.textContent = error.message; productMessage.className = "inline-result error"; }
}

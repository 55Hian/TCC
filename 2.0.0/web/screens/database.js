import { api, addCell, formatTime, showToast, elements } from "../api.js";
const { dbTableSelect, dbReload, dbPrevious, dbNext, dbNew, dbCancel, dbForm, dbEditorTitle, dbEditor, dbMessage, dbTableHelp, dbHead, dbRows, dbCount, dbPage } = elements("dbTableSelect", "dbReload", "dbPrevious", "dbNext", "dbNew", "dbCancel", "dbForm", "dbEditorTitle", "dbEditor", "dbMessage", "dbTableHelp", "dbHead", "dbRows", "dbCount", "dbPage");

let definitions = [];
let selected = "";
let offset = 0;
const pageSize = 50;
let editingId = null;

export function init() {
  dbTableSelect.addEventListener("change", () => { selected = dbTableSelect.value; offset = 0; refresh(); });
  dbReload.addEventListener("click", refresh);
  dbPrevious.addEventListener("click", () => { offset = Math.max(0, offset - pageSize); refresh(); });
  dbNext.addEventListener("click", () => { offset += pageSize; refresh(); });
  dbNew.addEventListener("click", () => openEditor());
  dbCancel.addEventListener("click", closeEditor);
  dbForm.addEventListener("submit", saveRecord);
}

async function loadTables() {
  if (definitions.length) return;
  const result = await api("/api/banco/tabelas");
  definitions = result.tabelas;
  dbTableSelect.replaceChildren();
  for (const table of definitions) {
    const option = document.createElement("option");
    option.value = table.nome;
    option.textContent = table.rotulo;
    dbTableSelect.append(option);
  }
  dbTableSelect.disabled = false;
  dbNew.disabled = false;
  selected = dbTableSelect.value;
}

function tableInfo() { return definitions.find((item) => item.nome === selected); }

function formatValue(field, value) {
  if (value == null || value === "") return "—";
  if (field.tipo === "boolean") return value ? "Sim" : "Não";
  if (["datetime", "timestamp"].includes(field.tipo)) return formatTime(value);
  const text = typeof value === "object" ? JSON.stringify(value) : String(value);
  return text.length > 90 ? `${text.slice(0, 87)}…` : text;
}

function renderRows(rows) {
  const table = tableInfo();
  dbHead.replaceChildren();
  dbRows.replaceChildren();
  const header = document.createElement("tr");
  for (const title of [table.chave, ...table.campos.map((field) => field.rotulo), "Ações"]) {
    const cell = document.createElement("th");
    cell.textContent = title;
    header.append(cell);
  }
  dbHead.append(header);
  if (!rows.length) {
    const row = document.createElement("tr");
    addCell(row, "Nenhum registro nesta tabela.", "muted-cell").colSpan = table.campos.length + 2;
    dbRows.append(row);
    return;
  }
  for (const record of rows) {
    const row = document.createElement("tr");
    addCell(row, record[table.chave]);
    for (const field of table.campos) {
      if (selected === "correlacoes" && field.nome === "video_path" && record[field.nome]) {
        const cell = document.createElement("td");
        const link = document.createElement("a");
        link.href = `/api/camera-secundaria/gravacoes/${record.id_event}/arquivo`;
        link.target = "_blank";
        link.rel = "noreferrer";
        link.textContent = "Abrir vídeo";
        link.title = record[field.nome];
        cell.append(link);
        row.append(cell);
        continue;
      }
      const cell = addCell(row, formatValue(field, record[field.nome]));
      cell.title = record[field.nome] == null ? "" : String(record[field.nome]);
    }
    const actions = document.createElement("td");
    actions.className = "row-actions";
    const edit = document.createElement("button");
    edit.className = "text-button";
    edit.textContent = "Editar";
    edit.addEventListener("click", () => openEditor(record));
    const remove = document.createElement("button");
    remove.className = "text-button danger-text";
    remove.textContent = "Remover";
    remove.addEventListener("click", () => removeRecord(record[table.chave]));
    actions.append(edit, remove);
    row.append(actions);
    dbRows.append(row);
  }
}

function openEditor(record = null) {
  const table = tableInfo();
  editingId = record ? record[table.chave] : null;
  dbEditorTitle.textContent = editingId == null ? `Novo registro · ${table.rotulo}` : `Editar registro #${editingId}`;
  dbForm.replaceChildren();
  for (const field of table.campos.filter((item) => item.editavel !== false)) {
    const label = document.createElement("label");
    label.textContent = field.rotulo + (field.obrigatorio ? " *" : "");
    let input;
    if (field.tipo === "boolean") {
      input = document.createElement("select");
      for (const [value, text] of [["true", "Sim"], ["false", "Não"]]) {
        const option = document.createElement("option"); option.value = value; option.textContent = text; input.append(option);
      }
      input.value = String(record ? record[field.nome] : field.padrao ?? false);
    } else if (field.tipo === "vector" || field.nome === "pontos_mao") {
      input = document.createElement("textarea"); input.rows = 3;
      input.value = record?.[field.nome] ?? "";
      input.placeholder = field.tipo === "vector" ? "JSON com 128 números" : "JSON ou texto";
    } else {
      input = document.createElement("input");
      input.type = field.tipo === "integer" || field.tipo === "number" ? "number" : ["datetime", "timestamp"].includes(field.tipo) ? "datetime-local" : "text";
      if (input.type === "number") input.step = field.tipo === "integer" ? "1" : "any";
      if (field.obrigatorio) input.required = true;
      const value = record?.[field.nome] ?? field.padrao ?? "";
      if (input.type === "datetime-local" && value) {
        const date = new Date(value);
        input.value = new Date(date.getTime() - date.getTimezoneOffset() * 60000).toISOString().slice(0, 16);
      } else input.value = value;
    }
    input.name = field.nome;
    label.append(input);
    dbForm.append(label);
  }
  const actions = document.createElement("div"); actions.className = "form-actions wide-field";
  const save = document.createElement("button"); save.className = "button button-primary"; save.textContent = editingId == null ? "Cadastrar" : "Salvar alterações";
  const cancel = document.createElement("button"); cancel.type = "button"; cancel.className = "button button-secondary"; cancel.textContent = "Cancelar"; cancel.addEventListener("click", closeEditor);
  actions.append(save, cancel); dbForm.append(actions);
  dbMessage.textContent = "";
  dbEditor.hidden = false;
  dbEditor.scrollIntoView({ behavior: "smooth", block: "start" });
}

function closeEditor() { dbEditor.hidden = true; editingId = null; }

async function saveRecord(event) {
  event.preventDefault();
  const table = tableInfo();
  const data = {};
  for (const field of table.campos.filter((item) => item.editavel !== false)) {
    const control = dbForm.elements[field.nome];
    let value = control.value;
    if (field.tipo === "boolean") value = value === "true";
    else if (control.type === "datetime-local" && value) value = new Date(value).toISOString();
    else if (value === "" && !field.obrigatorio) continue;
    else if (value === "") value = null;
    data[field.nome] = value;
  }
  try {
    const path = `/api/banco/${selected}${editingId == null ? "" : `/${editingId}`}`;
    await api(path, { method: editingId == null ? "POST" : "PUT", body: JSON.stringify(data) });
    showToast(editingId == null ? "Registro cadastrado." : "Registro atualizado.");
    closeEditor(); await refresh();
  } catch (error) { dbMessage.textContent = error.message; dbMessage.className = "inline-result error"; }
}

async function removeRecord(id) {
  if (!window.confirm(`Remover o registro #${id} de ${tableInfo().rotulo}?`)) return;
  try {
    await api(`/api/banco/${selected}/${id}`, { method: "DELETE" });
    showToast("Registro removido."); await refresh();
  } catch (error) { showToast(error.message, true); }
}

export async function refresh() {
  try {
    await loadTables();
    const table = tableInfo();
    dbTableHelp.textContent = `Tabela ${table.rotulo}. Alterações e remoções afetam os dados persistidos.`;
    const result = await api(`/api/banco/${selected}?limite=${pageSize}&offset=${offset}`);
    dbCount.textContent = `${result.total} registro(s)`;
    dbPage.textContent = `Página ${Math.floor(offset / pageSize) + 1}`;
    dbPrevious.disabled = offset === 0;
    dbNext.disabled = offset + pageSize >= result.total;
    renderRows(result.registros);
  } catch (error) {
    dbTableHelp.textContent = error.message;
    dbRows.replaceChildren();
  }
}

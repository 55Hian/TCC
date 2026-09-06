async function apiGet(path) {
  const resp = await fetch(path);
  if (!resp.ok) throw new Error(`GET ${path} -> ${resp.status}`);
  return resp.json();
}

async function apiPost(path, body) {
  const resp = await fetch(path, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: body !== undefined ? JSON.stringify(body) : undefined,
  });
  if (!resp.ok) {
    const detalhe = await resp.json().catch(() => ({}));
    throw new Error(detalhe.detail || `POST ${path} -> ${resp.status}`);
  }
  return resp.json();
}

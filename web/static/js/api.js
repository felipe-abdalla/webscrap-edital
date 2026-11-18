/* Comunicação com o servidor */

export async function fetchEditais() {
  const r = await fetch('/api/editais');
  const data = await r.json();
  if (!r.ok) throw new Error(data.error || `HTTP ${r.status}`);
  return data;
}

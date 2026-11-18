/* Funções auxiliares: segurança do HTML e datas */

export function escapeHTML(s) {
  return String(s ?? '').replace(/[&<>"']/g, c => (
    { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]
  ));
}

// Só links http(s): bloqueia "javascript:" e similares vindos da Web
export function safeURL(url) {
  try {
    const u = new URL(url);
    return (u.protocol === 'http:' || u.protocol === 'https:') ? u.href : '#';
  } catch (e) {
    return '#';
  }
}

// Aceita "AAAA-MM-DD" e também "AAAA-MM-DDThh:mm:ss" (listas salvas antes da correção)
function dateOnly(iso) {
  return String(iso).slice(0, 10);
}

export function fmtDate(iso) {
  const [y, m, d] = dateOnly(iso).split('-');
  return `${d}/${m}/${y}`;
}

export function fmtDateTime(iso) {
  if (!iso) return null;
  return new Date(iso).toLocaleString('pt-BR', { dateStyle: 'short', timeStyle: 'short' });
}

export function daysUntil(iso) {
  const today = new Date(); today.setHours(0, 0, 0, 0);
  return Math.round((new Date(dateOnly(iso) + 'T00:00:00') - today) / 86400000);
}

/* Montagem do quadro de cards */

import { daysUntil, escapeHTML, fmtDate, fmtDateTime, safeURL } from './utils.js';

function badge(cls, icon, text, title = '') {
  return `<span class="meta-badge ${cls}"${title ? ` title="${title}"` : ''}><i class="bi ${icon}"></i><span>${text}</span></span>`;
}

function deadlineBadge(iso) {
  const days = daysUntil(iso);
  const label = fmtDate(iso);
  if (days === 0) return badge('deadline-warn', 'bi-exclamation-triangle-fill', `Encerra hoje (${label})`);
  if (days === 1) return badge('deadline-warn', 'bi-exclamation-triangle-fill', `Até ${label} · amanhã`);
  if (days <= 7)  return badge('deadline-warn', 'bi-exclamation-triangle-fill', `Até ${label} · ${days} dias`);
  if (days <= 30) return badge('deadline-warn', 'bi-clock', `Até ${label} · ${days} dias`);
  return badge('deadline-ok', 'bi-calendar-check', `Até ${label}`);
}

// Cada card ocupa uma coluna do grid do Bootstrap (.row-cols-*)
function cardHTML(e) {
  const title = escapeHTML(e.title);
  const domain = escapeHTML(e.domain);
  return `
    <div class="col">
      <article class="edital-card">
        <h3 class="edital-title" title="${title}">
          <a href="${escapeHTML(safeURL(e.url))}" target="_blank" rel="noopener noreferrer">${title}</a>
        </h3>
        <div class="edital-meta">
          ${deadlineBadge(e.deadline)}
          ${e.domain ? badge('domain', 'bi-globe2', domain, domain) : ''}
        </div>
      </article>
    </div>`;
}

function emptyHTML(icon, text) {
  return `<div class="col-12"><div class="empty-state"><i class="bi ${icon}"></i><p>${text}</p></div></div>`;
}

function statusText(cache) {
  const parts = [];
  if (cache.updated_at) parts.push(`Lista do servidor de ${fmtDateTime(cache.updated_at)}`);
  if (cache.fetched_at) parts.push(`carregada aqui em ${fmtDateTime(cache.fetched_at)}`);
  if (cache.next_update_at && new Date(cache.next_update_at) > new Date()) {
    parts.push(`próxima atualização prevista para ${fmtDateTime(cache.next_update_at)}`);
  }
  return parts.join(' · ');
}

export function renderBoard(cache) {
  const cards  = document.getElementById('cards');
  const count  = document.getElementById('board-count');
  const status = document.getElementById('board-status');

  if (!cache) {
    count.textContent = '';
    status.textContent = '';
    cards.innerHTML = emptyHTML('bi-inbox', 'Nenhum edital carregado ainda.<br>Clique em <strong>Atualizar</strong> para buscar a lista mais recente.');
    return;
  }

  // A lista salva pode ser antiga: editais vencidos desde então saem do quadro
  const open = cache.editais.filter(e => daysUntil(e.deadline) >= 0);

  count.textContent = `(${open.length})`;
  status.textContent = statusText(cache);
  cards.innerHTML = open.length
    ? open.map(cardHTML).join('')
    : emptyHTML('bi-search', 'Nenhum edital com inscrições abertas no momento.');
}

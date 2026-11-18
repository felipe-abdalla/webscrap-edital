/* Mensagens temporárias no canto da tela */

import { escapeHTML } from './utils.js';

const ICONS = { success: 'bi-check-circle-fill', error: 'bi-x-circle-fill', info: 'bi-info-circle-fill' };

export function toast(msg, type = 'info') {
  const el = document.createElement('div');
  el.className = `toast-msg ${type}`;
  el.innerHTML = `<i class="bi ${ICONS[type] || ICONS.info}"></i>${escapeHTML(msg)}`;
  document.getElementById('toast-wrap').appendChild(el);
  setTimeout(() => el.remove(), 4000);
}

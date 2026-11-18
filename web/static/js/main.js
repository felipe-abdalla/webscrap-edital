/* Ponto de entrada da página */

import { fetchEditais } from './api.js';
import { renderBoard } from './render.js';
import { loadCache, saveCache } from './storage.js';
import { toast } from './toast.js';

async function update() {
  const btn = document.getElementById('update-btn');
  btn.disabled = true;
  btn.classList.add('loading');

  try {
    const data = await fetchEditais();

    const cache = {
      editais: data.editais || [],
      updated_at: data.updated_at,
      next_update_at: data.next_update_at,
      fetched_at: new Date().toISOString(),
    };
    saveCache(cache);
    renderBoard(cache);

    toast(data.updating
      ? 'Lista atualizada. O servidor está coletando novos editais agora; tente de novo em alguns minutos.'
      : `Lista atualizada: ${cache.editais.length} edital(is).`, 'success');
  } catch (e) {
    toast(`Não foi possível atualizar: ${e.message}`, 'error');
  } finally {
    btn.disabled = false;
    btn.classList.remove('loading');
  }
}

document.getElementById('update-btn').addEventListener('click', update);

// Início: mostra a lista salva, sem requisição
renderBoard(loadCache());

/* Lista de editais guardada no navegador (localStorage), para que reabrir a
   página não faça uma nova requisição. Ela só é substituída quando o usuário
   clica em "Atualizar". */

const STORAGE_KEY = 'webgate.editais.v1';

export function loadCache() {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    return raw ? JSON.parse(raw) : null;
  } catch (e) {
    return null;
  }
}

export function saveCache(data) {
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(data));
  } catch (e) {
    /* navegação privada ou armazenamento cheio: a página segue funcionando */
  }
}

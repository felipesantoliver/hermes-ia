/* ===================== INTERAÇÕES DE INTERFACE ===================== */
/* Responsabilidade: sidebar (recolher/expandir, novo chat), tema
   (claro/escuro) e comportamento geral do campo de entrada
   (auto-resize, foco, chips de modo). Não lida com envio/mensagens. */

/* ---------- Sidebar ---------- */
const sidebar = document.getElementById('sidebar');

document.getElementById('collapse-btn').addEventListener('click', () => {
  sidebar.classList.toggle('collapsed');
});

document.getElementById('new-chat-btn').addEventListener('click', () => {
  document.getElementById('msg-col').innerHTML = `
    <div class="empty-state" id="empty-state">
      <h1>O que vamos construir hoje?</h1>
      <p>Escreva uma mensagem para acordar o núcleo. Hermes escuta, pensa e responde com clareza.</p>
    </div>`;
});

/* ---------- Tema claro/escuro ---------- */
const themeBtn = document.getElementById('theme-btn');
const themeIcon = document.getElementById('theme-icon');
const ICON_MOON = 'M21 12.79A9 9 0 1111.21 3 7 7 0 0021 12.79z';
const ICON_SUN = 'M12 4.5V2m0 20v-2.5M4.5 12H2m20 0h-2.5M5.6 5.6L4 4m16 16l-1.6-1.6M18.4 5.6L20 4M4 20l1.6-1.6';

themeBtn.addEventListener('click', () => {
  const isLight = document.body.getAttribute('data-theme') === 'light';
  document.body.setAttribute('data-theme', isLight ? 'dark' : 'light');
  themeIcon.innerHTML = isLight
    ? `<path d="${ICON_MOON}"/>`
    : `<circle cx="12" cy="12" r="4"/><path d="${ICON_SUN}" stroke-linecap="round"/>`;
});

/* ---------- Campo de entrada (comportamento visual) ---------- */
const input = document.getElementById('msg-input');
const shell = document.getElementById('input-shell');

input.addEventListener('focus', () => shell.classList.add('focused'));
input.addEventListener('blur', () => shell.classList.remove('focused'));

input.addEventListener('input', () => {
  input.style.height = 'auto';
  input.style.height = Math.min(input.scrollHeight, 160) + 'px';
});

['mode-code', 'mode-think'].forEach((id) => {
  document.getElementById(id).addEventListener('click', function () {
    this.classList.toggle('active');
  });
});
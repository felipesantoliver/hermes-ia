/* ===================== INTERAÇÕES DE INTERFACE ===================== */
/* Responsabilidade: sidebar (recolher/expandir, novo chat), tema
   (claro/escuro) e comportamento geral do campo de entrada
   (auto-resize, foco, chips de modo). Não lida com envio/mensagens. */

/* ---------- Sidebar ---------- */
const sidebar = document.getElementById('sidebar');

document.getElementById('collapse-btn').addEventListener('click', () => {
  sidebar.classList.toggle('collapsed');
});

/* ---------- Novo chat (com chamada à API) ---------- */
document.getElementById('new-chat-btn').addEventListener('click', async () => {
  // Se estiver na view projetos, sair e ir para chat
  const viewProjects = document.getElementById('view-projects');
  if (viewProjects.classList.contains('active')) {
    window.HermesState.activeProjectId = null;
    window.HermesChats.showView('chat');
  }

  try {
    const res = await fetch(HermesState.API_BASE + '/chats/', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ title: 'Nova conversa', project_id: null }),
    });
    if (!res.ok) throw new Error('Falha ao criar chat');
    const chat = await res.json();

    HermesState.activeProjectId = null;
    window.HermesChats.loadChat(chat);
    window.HermesChats.showView('chat');
    window.HermesChats.renderSidebar();
  } catch (err) {
    console.error('[Hermes] Erro ao criar novo chat:', err);
  }
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

/* ---------- Chips de modo: apenas um ativo por vez (code / engineer / analyst) ---------- */
const MODE_CHIP_IDS = ['mode-code', 'mode-engineer', 'mode-analyst'];
MODE_CHIP_IDS.forEach((id) => {
  document.getElementById(id).addEventListener('click', function () {
    const wasActive = this.classList.contains('active');
    MODE_CHIP_IDS.forEach((otherId) => {
      document.getElementById(otherId).classList.remove('active');
    });
    if (!wasActive) {
      this.classList.add('active');
    }
  });
});

/* ---------- Chip Web (toggle, não exclusivo) ---------- */
const webToggle = document.getElementById('web-toggle');
if (!window.HermesState.webSearchEnabled) {
  window.HermesState.webSearchEnabled = false;
}
webToggle.addEventListener('click', function () {
  const enabled = !this.classList.contains('active');
  this.classList.toggle('active', enabled);
  window.HermesState.webSearchEnabled = enabled;
});
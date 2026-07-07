/* ===================== INTERAÇÕES DE INTERFACE ===================== */
/* Responsabilidade: sidebar (recolher/expandir, novo chat), tema
   (claro/escuro) e comportamento geral do campo de entrada
   (auto-resize, foco, chips de modo e domínio). Não lida com envio/mensagens. */

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

/* ===================== Tema (claro / escuro / sistema) ===================== */
/* Centralizado aqui para que qualquer parte da UI (botão rápido do topo OU
   os chips de aparência em Configurações) apliquem e PERSISTAM o tema da
   mesma forma. Antes, o botão rápido só mudava o atributo do DOM e nunca
   salvava via PATCH /profile — por isso o tema "voltava" ao reabrir o app. */
const themeBtn = document.getElementById('theme-btn');
const themeIcon = document.getElementById('theme-icon');
const ICON_MOON = 'M21 12.79A9 9 0 1111.21 3 7 7 0 0021 12.79z';
const ICON_SUN = 'M12 4.5V2m0 20v-2.5M4.5 12H2m20 0h-2.5M5.6 5.6L4 4m16 16l-1.6-1.6M18.4 5.6L20 4M4 20l1.6-1.6';

/** Aplica visualmente o tema (claro/escuro/sistema) e atualiza o ícone. */
function applyThemeVisual(choice) {
  const resolved = choice === 'system'
    ? (window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light')
    : choice;
  document.body.setAttribute('data-theme', resolved);
  if (themeIcon) {
    themeIcon.innerHTML = resolved === 'light'
      ? `<circle cx="12" cy="12" r="4"/><path d="${ICON_SUN}" stroke-linecap="round"/>`
      : `<path d="${ICON_MOON}"/>`;
  }
}

/** Persiste o tema escolhido no backend (PATCH /profile). */
function persistTheme(choice) {
  return fetch(`${window.HermesState.API_BASE}/profile/`, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ theme: choice }),
  }).catch((err) => {
    console.error('[Hermes] Erro ao salvar tema:', err);
  });
}

/** Aplica e persiste em uma única chamada — usado pelos chips de Configurações. */
function setTheme(choice) {
  applyThemeVisual(choice);
  persistTheme(choice);
}

/** Carrega o tema salvo no perfil assim que o app abre. */
async function loadInitialTheme() {
  try {
    const res = await fetch(`${window.HermesState.API_BASE}/profile/`);
    if (!res.ok) throw new Error('Falha ao carregar perfil');
    const profile = await res.json();
    applyThemeVisual(profile.theme || 'dark');
  } catch (err) {
    console.error('[Hermes] Erro ao carregar tema salvo:', err);
  }
}

// Exposto para outros módulos (settings.js) reaproveitarem a mesma lógica.
window.HermesTheme = {
  apply: applyThemeVisual,
  set: setTheme,
};

themeBtn.addEventListener('click', () => {
  const isLight = document.body.getAttribute('data-theme') === 'light';
  const next = isLight ? 'dark' : 'light';
  setTheme(next);
});

loadInitialTheme();

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
/* A escolha de domínio (firmware/android/etc.) não é mais manual: o backend
   detecta automaticamente o agente ideal a partir da mensagem do usuário
   (HybridAgentRouter). Aqui só cuidamos da exclusividade visual dos chips
   de modo e do título do cabeçalho, que reflete o modo ativo (ex.: "Hermes · Engenheiro"). */
const MODE_CHIP_IDS = ['mode-code', 'mode-engineer', 'mode-analyst'];
const MODE_LABELS = {
  'mode-code': 'Programação',
  'mode-engineer': 'Engenheiro',
  'mode-analyst': 'Analista',
};

MODE_CHIP_IDS.forEach((id) => {
  document.getElementById(id).addEventListener('click', function () {
    const wasActive = this.classList.contains('active');
    MODE_CHIP_IDS.forEach((otherId) => {
      document.getElementById(otherId).classList.remove('active');
    });
    if (!wasActive) {
      this.classList.add('active');
      updateModeTitle(MODE_LABELS[this.id]);
    } else {
      updateModeTitle(null);
    }
  });
});

/* ---------- Função para atualizar o título no cabeçalho conforme o modo ativo ---------- */
function updateModeTitle(modeLabel) {
  const titleEl = document.getElementById('agent-title');
  titleEl.textContent = modeLabel ? `Hermes · ${modeLabel}` : 'Hermes';
}

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
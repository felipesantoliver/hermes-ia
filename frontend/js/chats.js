/* ===================== SIDEBAR DE CHATS + BUSCA ===================== */
/* Responsabilidade: listar chats fixados/recentes na sidebar, menu de
   contexto (fixar, renomear, mover, arquivar, excluir), carregar um
   chat na view-chat e busca de conversas. */

(function () {
  const API = () => window.HermesState.API_BASE;

  let sidebarChats = [];
  let openMenuEl = null;

  /* ---------- Troca de view (compartilhado com projects.js) ---------- */
  function showView(name) {
    document.querySelectorAll('.view').forEach((v) => v.classList.remove('active'));
    document.getElementById('view-' + name).classList.add('active');
    if (name === 'chat') {
      // Atualizar título do chat
      const projectId = window.HermesState.activeProjectId;
      if (projectId) {
        // Buscar nome do projeto
        fetch(`${API()}/projects/`)
          .then(res => res.json())
          .then(projects => {
            const proj = projects.find(p => p.id === projectId);
            if (proj) document.getElementById('agent-title').textContent = proj.name;
          })
          .catch(() => {});
      } else {
        document.getElementById('agent-title').textContent = 'Hermes';
      }
    }
  }

  /* ---------- Carrega um chat na view-chat ---------- */
  async function loadChat(chat) {
    window.HermesState.currentChatId = chat.id;
    document.getElementById('agent-title').textContent =
      chat.project_id && window.HermesProjects && window.HermesProjects.currentProjectName
        ? window.HermesProjects.currentProjectName
        : 'Hermes';

    const msgCol = document.getElementById('msg-col');
    msgCol.innerHTML = '';

    try {
      const res = await fetch(`${API()}/chats/${chat.id}/messages`);
      if (!res.ok) throw new Error('Falha ao buscar mensagens');
      const messages = await res.json();
      if (messages.length === 0) {
        msgCol.innerHTML = `
          <div class="empty-state" id="empty-state">
            <h1>O que vamos construir hoje?</h1>
            <p>Escreva uma mensagem para acordar o núcleo. Hermes escuta, pensa e responde com clareza.</p>
          </div>`;
      } else {
        messages.forEach((m) => addMessage(m.role, m.content));
      }
    } catch (err) {
      console.error('[Hermes] Erro ao carregar mensagens:', err);
    }
  }

  /* ---------- Busca chats para a sidebar ---------- */
  async function fetchSidebarChats() {
    try {
      const res = await fetch(`${API()}/chats/?scope=sidebar`);
      if (!res.ok) throw new Error('Falha ao buscar chats');
      sidebarChats = await res.json();
    } catch (err) {
      console.error('[Hermes] Erro ao buscar chats da sidebar:', err);
      sidebarChats = [];
    }
    return sidebarChats;
  }

  function fmtTime(iso) {
    const d = new Date(iso);
    return d.toLocaleDateString('pt-BR', { day: '2-digit', month: 'short' });
  }

  function buildChatItem(chat, { inProject = false } = {}) {
    const item = document.createElement('div');
    item.className = 'pinned-item chat-item';
    item.innerHTML = `
      <span class="pinned-dot"></span>
      <span class="chat-item-title">${escapeHtml(chat.title)}</span>
      <button class="chat-menu-btn" title="Mais opções">⋮</button>
    `;

    item.querySelector('.chat-item-title').addEventListener('click', () => {
      loadChat(chat);
      showView('chat');
    });

    const menuBtn = item.querySelector('.chat-menu-btn');
    menuBtn.addEventListener('click', (e) => {
      e.stopPropagation();
      openChatMenu(menuBtn, chat, { inProject });
    });

    return item;
  }

  function escapeHtml(str) {
    const div = document.createElement('div');
    div.textContent = str || '';
    return div.innerHTML;
  }

  /* ---------- Menu de contexto ---------- */
  function closeOpenMenu() {
    if (openMenuEl) {
      openMenuEl.remove();
      openMenuEl = null;
    }
  }

  async function buildChatContextMenu(chat, anchorEl, { inProject = false } = {}) {
    closeOpenMenu();

    const menu = document.createElement('div');
    menu.className = 'chat-context-menu';

    const actions = [
      { label: chat.pinned ? 'Desafixar' : 'Fixar', run: () => patchChat(chat.id, { pinned: !chat.pinned }) },
      { label: 'Renomear', run: () => renameChat(chat) },
    ];

    if (inProject) {
      actions.push({ label: 'Tirar do projeto', run: () => patchChat(chat.id, { project_id: null }) });
    } else {
      actions.push({ label: 'Mover para projeto ▸', run: null, submenu: true });
    }

    actions.push({ label: chat.archived ? 'Desarquivar' : 'Arquivar', run: () => patchChat(chat.id, { archived: !chat.archived }) });
    actions.push({ label: 'Excluir', danger: true, run: () => deleteChat(chat) });

    for (const action of actions) {
      const btn = document.createElement('button');
      btn.className = 'ctx-menu-item' + (action.danger ? ' danger' : '');
      btn.textContent = action.label;

      if (action.submenu) {
        btn.addEventListener('click', async (e) => {
          e.stopPropagation();
          await openMoveToProjectSubmenu(menu, chat);
        });
      } else {
        btn.addEventListener('click', async (e) => {
          e.stopPropagation();
          closeOpenMenu();
          await action.run();
        });
      }
      menu.appendChild(btn);
    }

    document.body.appendChild(menu);
    positionMenu(menu, anchorEl);
    openMenuEl = menu;

    setTimeout(() => {
      document.addEventListener('click', closeOpenMenu, { once: true });
    }, 0);
  }

  async function openMoveToProjectSubmenu(parentMenu, chat) {
    parentMenu.querySelectorAll('.ctx-submenu').forEach((s) => s.remove());
    try {
      const res = await fetch(`${API()}/projects/`);
      const projects = await res.json();
      const submenu = document.createElement('div');
      submenu.className = 'ctx-submenu';
      if (projects.length === 0) {
        submenu.innerHTML = `<div class="ctx-menu-empty">Nenhum projeto ainda</div>`;
      }
      projects.forEach((p) => {
        const pbtn = document.createElement('button');
        pbtn.className = 'ctx-menu-item';
        pbtn.textContent = p.name;
        pbtn.addEventListener('click', async (e) => {
          e.stopPropagation();
          closeOpenMenu();
          await patchChat(chat.id, { project_id: p.id });
        });
        submenu.appendChild(pbtn);
      });
      parentMenu.appendChild(submenu);
    } catch (err) {
      console.error('[Hermes] Erro ao buscar projetos para mover chat:', err);
    }
  }

  function positionMenu(menu, anchorEl) {
    const rect = anchorEl.getBoundingClientRect();
    menu.style.position = 'fixed';
    menu.style.top = rect.bottom + 4 + 'px';
    menu.style.left = Math.max(8, rect.right - 180) + 'px';
  }

  function renameChat(chat) {
    const newTitle = prompt('Renomear conversa:', chat.title);
    if (newTitle && newTitle.trim()) {
      patchChat(chat.id, { title: newTitle.trim() });
    }
  }

  async function deleteChat(chat) {
    if (!confirm(`Excluir a conversa "${chat.title}"? Essa ação não pode ser desfeita.`)) return;
    try {
      const res = await fetch(`${API()}/chats/${chat.id}`, { method: 'DELETE' });
      if (!res.ok && res.status !== 204) throw new Error('Falha ao excluir');
      afterMutation();
    } catch (err) {
      console.error('[Hermes] Erro ao excluir chat:', err);
    }
  }

  async function patchChat(chatId, payload) {
    try {
      const res = await fetch(`${API()}/chats/${chatId}`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      });
      if (!res.ok) throw new Error('Falha ao atualizar chat');
      afterMutation();
    } catch (err) {
      console.error('[Hermes] Erro ao atualizar chat:', err);
    }
  }

  function afterMutation() {
    renderSidebar();
    if (window.HermesProjects && window.HermesProjects.refreshCurrentProjectChats) {
      window.HermesProjects.refreshCurrentProjectChats();
    }
  }

  /* ---------- Renderiza sidebar (fixados + recentes) ---------- */
  async function renderSidebar() {
    const pinnedList = document.getElementById('pinned-list');
    const recentList = document.getElementById('recent-list');
    pinnedList.innerHTML = '';
    recentList.innerHTML = '';

    const chats = await fetchSidebarChats();
    const sorted = [...chats].sort((a, b) => new Date(b.updated_at) - new Date(a.updated_at));
    const pinned = sorted.filter((c) => c.pinned);
    const recent = sorted.filter((c) => !c.pinned);

    if (pinned.length === 0) {
      pinnedList.innerHTML = `<div class="chat-list-empty">Nenhum chat fixado</div>`;
    }
    pinned.forEach((c) => pinnedList.appendChild(buildChatItem(c)));

    if (recent.length === 0) {
      recentList.innerHTML = `<div class="chat-list-empty">Nenhuma conversa recente</div>`;
    }
    recent.forEach((c) => recentList.appendChild(buildChatItem(c)));
  }

  /* ---------- Busca de conversas (overlay) ---------- */
  const searchOverlay = document.getElementById('search-overlay');
  const searchBtn = document.getElementById('search-chat-btn');
  const searchInput = document.getElementById('search-input');
  const searchResults = document.getElementById('search-results');

  function openSearch() {
    searchOverlay.classList.add('open');
    searchInput.value = '';
    renderSearchResults('');
    setTimeout(() => searchInput.focus(), 50);
  }
  function closeSearch() {
    searchOverlay.classList.remove('open');
  }

  function renderSearchResults(query) {
    const q = query.trim().toLowerCase();
    const matches = q
      ? sidebarChats.filter((c) => c.title.toLowerCase().includes(q))
      : sidebarChats;

    searchResults.innerHTML = '';
    if (matches.length === 0) {
      searchResults.innerHTML = `<div class="chat-list-empty">Nenhuma conversa encontrada</div>`;
      return;
    }
    matches.forEach((c) => {
      const row = document.createElement('div');
      row.className = 'search-result-item';
      row.innerHTML = `<span class="pinned-dot"></span><span>${escapeHtml(c.title)}</span>`;
      row.addEventListener('click', () => {
        loadChat(c);
        showView('chat');
        closeSearch();
      });
      searchResults.appendChild(row);
    });
  }

  searchBtn.addEventListener('click', openSearch);
  searchInput.addEventListener('input', () => renderSearchResults(searchInput.value));
  searchOverlay.addEventListener('click', (e) => { if (e.target === searchOverlay) closeSearch(); });
  document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape' && searchOverlay.classList.contains('open')) closeSearch();
  });

  /* ---------- Exposição pública ---------- */
  window.HermesChats = {
    renderSidebar,
    loadChat,
    showView,
    buildChatContextMenu: async (chat, anchorEl, opts) => openChatMenu(anchorEl, chat, opts),
    buildChatItem,
  };

  function openChatMenu(anchorEl, chat, opts) {
    buildChatContextMenu(chat, anchorEl, opts);
  }

  document.addEventListener('DOMContentLoaded', renderSidebar);
})();
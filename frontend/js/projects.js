/* ===================== TELA DE PROJETOS ===================== */
/* Responsabilidade: listar projetos, criar novo projeto, tela de
   detalhe (instruções, persona, referências, escopo de memória,
   chats do projeto). */

(function () {
  const API = () => window.HermesState.API_BASE;
  const view = document.getElementById('view-projects');
  let currentProject = null;

  window.HermesProjects = {
    currentProjectName: null,
    refreshCurrentProjectChats: () => {
      if (currentProject) renderProjectChatsSection(currentProject.id);
    },
    renderProjectsList: renderProjectsList,
    openProject: openProject,
    openNewProjectModal: openNewProjectModal,
  };

  /* ---------- Navegação para a view de projetos ---------- */
  document.getElementById('projects-nav-btn').addEventListener('click', () => {
    window.HermesChats.showView('projects');
    renderProjectsList();
  });

  /* ---------- Lista de projetos (grid) ---------- */
  async function renderProjectsList() {
    view.innerHTML = `
      <div class="projects-header">
        <h1>Projetos</h1>
        <button class="primary-btn" id="new-project-btn">+ Novo projeto</button>
      </div>
      <div id="projects-grid" class="projects-grid"></div>
    `;

    document.getElementById('new-project-btn').addEventListener('click', () => {
      document.getElementById('new-project-modal').style.display = 'flex';
    });

    await loadProjectsGrid();
  }

  async function loadProjectsGrid() {
    const grid = document.getElementById('projects-grid');
    grid.innerHTML = `<div class="chat-list-empty">Carregando projetos...</div>`;

    try {
      const res = await fetch(`${API()}/projects/`);
      const projects = await res.json();

      if (projects.length === 0) {
        grid.innerHTML = `<div class="chat-list-empty">Nenhum projeto ainda. Crie o primeiro acima.</div>`;
        return;
      }

      grid.innerHTML = '';
      for (const p of projects) {
        let chatCount = 0;
        try {
          const cres = await fetch(`${API()}/projects/${p.id}/chats`);
          const chats = await cres.json();
          chatCount = chats.length;
        } catch (_) {}

        const card = document.createElement('div');
        card.className = 'project-card';
        card.innerHTML = `
          <svg class="project-card-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6">
            <path d="M3 7l3-3h5l2 2h8v11a2 2 0 01-2 2H5a2 2 0 01-2-2V7z"/>
          </svg>
          <div class="project-card-name">${escapeHtml(p.name)}</div>
          <div class="project-card-desc">${escapeHtml(p.description || 'Sem descrição')}</div>
          <div class="project-card-meta">${chatCount} chat${chatCount === 1 ? '' : 's'}</div>
        `;
        card.addEventListener('click', () => openProject(p.id));
        grid.appendChild(card);
      }
    } catch (err) {
      console.error('[Hermes] Erro ao carregar projetos:', err);
      grid.innerHTML = `<div class="chat-list-empty">Erro ao carregar projetos.</div>`;
    }
  }

  /* ---------- Modal de novo projeto ---------- */
  const modal = document.getElementById('new-project-modal');
  const cancelModal = document.getElementById('cancel-new-project-modal');
  const confirmModal = document.getElementById('confirm-new-project-modal');
  const nameInput = document.getElementById('new-project-name-modal');
  const descInput = document.getElementById('new-project-desc-modal');

  // Callback opcional chamado com o projeto recém-criado. Usado quando o
  // modal é aberto a partir de outro fluxo (ex: "Mover para projeto" no
  // menu de contexto de um chat), para poder agir sobre o projeto novo
  // assim que ele é confirmado (ex: mover o chat pra ele).
  let onProjectCreated = null;

  /**
   * Abre o modal de criação de projeto. Se `onCreated` for passado, é
   * chamado com o projeto criado assim que a criação for confirmada
   * (além do fluxo padrão de abrir a tela de detalhe do projeto).
   */
  function openNewProjectModal({ onCreated } = {}) {
    onProjectCreated = onCreated || null;
    modal.style.display = 'flex';
  }

  function closeModal() {
    modal.style.display = 'none';
    nameInput.value = '';
    descInput.value = '';
  }

  cancelModal.addEventListener('click', () => {
    onProjectCreated = null;
    closeModal();
  });
  modal.addEventListener('click', (e) => {
    if (e.target === modal) {
      onProjectCreated = null;
      closeModal();
    }
  });

  confirmModal.addEventListener('click', async () => {
    const name = nameInput.value.trim();
    if (!name) return;
    const description = descInput.value.trim();
    try {
      const res = await fetch(`${API()}/projects/`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ name, description: description || null }),
      });
      if (!res.ok) throw new Error('Falha ao criar projeto');
      const project = await res.json();
      const callback = onProjectCreated;
      onProjectCreated = null;
      closeModal();
      if (callback) {
        // Fluxo alternativo (ex: mover chat pra este projeto): não navega
        // automaticamente para a tela de detalhe do projeto.
        await callback(project);
      } else {
        openProject(project.id);
      }
    } catch (err) {
      console.error('[Hermes] Erro ao criar projeto:', err);
    }
  });

  /* ---------- Tela de detalhe do projeto ---------- */
  async function openProject(id) {
    try {
      const res = await fetch(`${API()}/projects/`);
      const projects = await res.json();
      const project = projects.find((p) => p.id === id);
      if (!project) throw new Error('Projeto não encontrado');
      currentProject = project;
      window.HermesProjects.currentProjectName = project.name;

      view.innerHTML = `
        <div class="project-detail-header">
          <button id="back-to-projects" class="ghost-btn">← Voltar</button>
          <h1>${escapeHtml(project.name)}</h1>
        </div>
        <div id="project-config-panel"></div>
      `;

      document.getElementById('back-to-projects').addEventListener('click', renderProjectsList);
      renderProjectConfigPanel(project);
    } catch (err) {
      console.error('[Hermes] Erro ao abrir projeto:', err);
    }
  }

  function renderProjectConfigPanel(project) {
    const panel = document.getElementById('project-config-panel');
    panel.innerHTML = `
      <div style="display:flex; gap:12px; align-items:center; margin-bottom:16px;">
        <h1 style="flex:1; margin:0;">${escapeHtml(project.name)}</h1>
        <button id="new-project-chat-btn" class="primary-btn" style="padding:8px 16px;">+ Novo chat</button>
        <button id="exit-project-btn" class="ghost-btn" style="padding:8px 16px;">Sair do projeto</button>
      </div>

      <div class="settings-group project-config-block">
        <label class="settings-label">Instruções</label>
        <textarea id="project-instructions" class="profile-textarea" rows="4"
          placeholder="Como o Hermes deve se comportar dentro deste projeto...">${escapeHtml(project.instructions || '')}</textarea>
      </div>

      <div class="settings-group project-config-block">
        <label class="settings-label">Persona</label>
        <textarea id="project-persona" class="profile-textarea" rows="4"
          placeholder="Uma persona específica para este projeto...">${escapeHtml(project.persona || '')}</textarea>
      </div>

      <div class="settings-group project-config-block">
        <label class="settings-label">Referências</label>
        <input type="file" id="project-file-input" multiple accept=".pdf,.txt,.md,.docx" class="hidden">
        <button class="ghost-btn" id="project-file-btn">+ Adicionar arquivos</button>
        <div id="project-files-list" class="project-files-list"></div>
      </div>

      <div class="settings-group project-config-block">
        <label class="settings-label">Escopo de memória</label>
        <div class="chip-row memory-scope-row" id="memory-scope-chips">
          <button class="settings-chip memory-chip" data-scope="isolated">
            Isolado
            <span class="chip-hint">Memória só deste projeto, sem acesso a outras conversas.</span>
          </button>
          <button class="settings-chip memory-chip" data-scope="isolated_read_external">
            Isolado + leitura externa
            <span class="chip-hint">Memória isolada, mas pode ler contexto de fora do projeto.</span>
          </button>
          <button class="settings-chip memory-chip" data-scope="none">
            Sem memória
            <span class="chip-hint">Nada é salvo entre conversas deste projeto.</span>
          </button>
        </div>
      </div>

      <div class="settings-group project-config-block">
        <label class="settings-label">Chats do projeto</label>
        <div id="project-chats-list" class="project-chats-list"></div>
      </div>
    `;

    // Instruções / persona — salva no blur
    const instrEl = document.getElementById('project-instructions');
    instrEl.addEventListener('blur', () => saveProjectField(project.id, 'instructions', instrEl.value));

    const personaEl = document.getElementById('project-persona');
    personaEl.addEventListener('blur', () => saveProjectField(project.id, 'persona', personaEl.value));

    // Escopo de memória
    const chips = panel.querySelectorAll('.memory-chip');
    chips.forEach((chip) => {
      if (chip.dataset.scope === project.memory_scope) chip.classList.add('active');
      chip.addEventListener('click', async () => {
        chips.forEach((c) => c.classList.remove('active'));
        chip.classList.add('active');
        await saveProjectField(project.id, 'memory_scope', chip.dataset.scope);
      });
    });

    // Referências
    const fileInput = document.getElementById('project-file-input');
    document.getElementById('project-file-btn').addEventListener('click', () => fileInput.click());
    fileInput.addEventListener('change', async () => {
      for (const file of fileInput.files) {
        await uploadProjectFile(project.id, file);
      }
      fileInput.value = '';
      renderProjectFilesList(project.id);
    });
    renderProjectFilesList(project.id);

    // Chats do projeto
    document.getElementById('new-project-chat-btn').addEventListener('click', () => createProjectChat(project));
    document.getElementById('exit-project-btn').addEventListener('click', () => {
      window.HermesState.activeProjectId = null;
      renderProjectsList();
    });
    renderProjectChatsSection(project.id);
  }

  async function saveProjectField(projectId, field, value) {
    try {
      await fetch(`${API()}/projects/${projectId}`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ [field]: value }),
      });
    } catch (err) {
      console.error(`[Hermes] Erro ao salvar ${field}:`, err);
    }
  }

  async function uploadProjectFile(projectId, file) {
    const formData = new FormData();
    formData.append('file', file);
    try {
      const res = await fetch(`${API()}/projects/${projectId}/files`, { method: 'POST', body: formData });
      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        alert(err.detail || 'Erro ao enviar arquivo.');
      }
    } catch (err) {
      console.error('[Hermes] Erro ao enviar arquivo:', err);
    }
  }

  async function renderProjectFilesList(projectId) {
    const list = document.getElementById('project-files-list');
    if (!list) return;
    list.innerHTML = `<div class="chat-list-empty">Carregando...</div>`;
    try {
      const res = await fetch(`${API()}/projects/${projectId}/files`);
      const files = await res.json();
      if (files.length === 0) {
        list.innerHTML = `<div class="chat-list-empty">Nenhum arquivo de referência ainda.</div>`;
        return;
      }
      list.innerHTML = '';
      files.forEach((f) => {
        const row = document.createElement('div');
        row.className = 'project-file-row';
        row.innerHTML = `
          <span class="project-file-name">${escapeHtml(f.filename)}</span>
          <span class="project-file-size">${formatBytes(f.size_bytes)}</span>
          <button class="file-remove-btn" title="Remover">✕</button>
        `;
        row.querySelector('.file-remove-btn').addEventListener('click', async () => {
          if (!confirm(`Remover "${f.filename}"?`)) return;
          await fetch(`${API()}/projects/${projectId}/files/${f.id}`, { method: 'DELETE' });
          renderProjectFilesList(projectId);
        });
        list.appendChild(row);
      });
    } catch (err) {
      console.error('[Hermes] Erro ao listar arquivos do projeto:', err);
    }
  }

  function formatBytes(bytes) {
    if (bytes < 1024) return bytes + ' B';
    if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + ' KB';
    return (bytes / (1024 * 1024)).toFixed(1) + ' MB';
  }

  async function renderProjectChatsSection(projectId) {
    const list = document.getElementById('project-chats-list');
    if (!list) return;
    list.innerHTML = `<div class="chat-list-empty">Carregando...</div>`;
    try {
      const res = await fetch(`${API()}/projects/${projectId}/chats`);
      const chats = await res.json();
      if (chats.length === 0) {
        list.innerHTML = `<div class="chat-list-empty">Nenhum chat neste projeto ainda.</div>`;
        return;
      }
      list.innerHTML = '';
      chats.forEach((c) => {
        const item = window.HermesChats.buildChatItem(c, { inProject: true });
        list.appendChild(item);
      });
    } catch (err) {
      console.error('[Hermes] Erro ao listar chats do projeto:', err);
    }
  }

  async function createProjectChat(project) {
    try {
      const res = await fetch(`${API()}/chats/`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ title: `Novo chat — ${project.name}`, project_id: project.id }),
      });
      if (!res.ok) throw new Error('Falha ao criar chat do projeto');
      const chat = await res.json();

      window.HermesState.activeProjectId = project.id;
      document.getElementById('msg-col').innerHTML = `
        <div class="empty-state" id="empty-state">
          <h1>O que vamos construir hoje?</h1>
          <p>Escreva uma mensagem para acordar o núcleo. Hermes escuta, pensa e responde com clareza.</p>
        </div>`;
      document.getElementById('agent-title').textContent = project.name;
      window.HermesState.currentChatId = chat.id;

      window.HermesChats.showView('chat');
      window.HermesChats.renderSidebar();
    } catch (err) {
      console.error('[Hermes] Erro ao criar chat no projeto:', err);
    }
  }

  function escapeHtml(str) {
    const div = document.createElement('div');
    div.textContent = str || '';
    return div.innerHTML;
  }

})();

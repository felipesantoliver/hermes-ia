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
      <div id="new-project-form" class="new-project-form hidden">
        <input type="text" id="new-project-name" placeholder="Nome do projeto">
        <textarea id="new-project-desc" rows="2" placeholder="Descrição (opcional)"></textarea>
        <div class="new-project-actions">
          <button class="ghost-btn" id="cancel-new-project">Cancelar</button>
          <button class="primary-btn" id="confirm-new-project">Criar</button>
        </div>
      </div>
      <div id="projects-grid" class="projects-grid"></div>
    `;

    const newBtn = document.getElementById('new-project-btn');
    const form = document.getElementById('new-project-form');
    newBtn.addEventListener('click', () => form.classList.toggle('hidden'));
    document.getElementById('cancel-new-project').addEventListener('click', () => form.classList.add('hidden'));
    document.getElementById('confirm-new-project').addEventListener('click', createProject);

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

  async function createProject() {
    const name = document.getElementById('new-project-name').value.trim();
    const description = document.getElementById('new-project-desc').value.trim();
    if (!name) return;

    try {
      const res = await fetch(`${API()}/projects/`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ name, description: description || null }),
      });
      if (!res.ok) throw new Error('Falha ao criar projeto');
      const project = await res.json();
      openProject(project.id);
    } catch (err) {
      console.error('[Hermes] Erro ao criar projeto:', err);
    }
  }

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
        <button class="primary-btn" id="new-project-chat-btn">+ Novo chat neste projeto</button>
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

  window.HermesProjects.renderProjectsList = renderProjectsList;
  window.HermesProjects.openProject = openProject;
})();
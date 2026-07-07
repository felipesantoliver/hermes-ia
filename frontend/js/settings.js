/* ===================== MODAL DE CONFIGURAÇÕES ===================== */
/* Responsabilidade: abrir/fechar o modal, trocar entre painéis da
   sidebar interna, aparência, idioma, notificações push, controle de
   dados (ações destrutivas) e limite de armazenamento (memória RAM). */

(function () {
  const API = () => window.HermesState.API_BASE;

  const overlay = document.getElementById('settings-overlay');
  const openBtn = document.getElementById('settings-btn');
  const closeBtn = document.getElementById('settings-close');

  /* ---------- Abrir / fechar modal ---------- */
  let profileLoadedForSettings = false;

  function openSettings() {
    overlay.classList.add('open');
    if (!profileLoadedForSettings) {
      loadProfileIntoSettings();
      profileLoadedForSettings = true;
    }
    startResourceMeterPolling();
  }
  function closeSettings() {
    overlay.classList.remove('open');
    stopResourceMeterPolling();
  }

  openBtn.addEventListener('click', openSettings);
  closeBtn.addEventListener('click', closeSettings);

  // Fecha ao clicar fora do modal
  overlay.addEventListener('click', (e) => {
    if (e.target === overlay) closeSettings();
  });

  // Fecha com a tecla Esc
  document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape' && overlay.classList.contains('open')) closeSettings();
  });

  /* ---------- Navegação entre painéis (sidebar interna) ---------- */
  const navItems = document.querySelectorAll('.settings-nav-item');
  const panels = document.querySelectorAll('.settings-panel');

  navItems.forEach((item) => {
    item.addEventListener('click', () => {
      navItems.forEach((i) => i.classList.remove('active'));
      panels.forEach((p) => p.classList.remove('active'));

      item.classList.add('active');
      document.getElementById('panel-' + item.dataset.panel).classList.add('active');

      if (item.dataset.panel === 'dados') {
        renderArchivedChats();
      }
    });
  });

  /* ---------- Conversas arquivadas ---------- */
  const archivedChatsList = document.getElementById('archived-chats-list');

  function escapeHtmlSettings(str) {
    const div = document.createElement('div');
    div.textContent = str || '';
    return div.innerHTML;
  }

  async function renderArchivedChats() {
    archivedChatsList.innerHTML = `<div class="chat-list-empty">Carregando…</div>`;
    try {
      const res = await fetch(`${API()}/chats/?scope=archived`);
      if (!res.ok) throw new Error('Falha ao buscar conversas arquivadas');
      const archived = await res.json();

      archivedChatsList.innerHTML = '';
      if (archived.length === 0) {
        archivedChatsList.innerHTML = `<div class="chat-list-empty">Nenhuma conversa arquivada</div>`;
        return;
      }

      archived.forEach((chat) => {
        const row = document.createElement('div');
        row.className = 'settings-row';
        row.innerHTML = `
          <div>
            <div class="settings-row-title">${escapeHtmlSettings(chat.title)}</div>
          </div>
          <div style="display:flex; gap:8px;">
            <button class="ghost-btn archived-open-btn" style="padding:6px 12px; font-size:13px;">Abrir</button>
            <button class="ghost-btn archived-unarchive-btn" style="padding:6px 12px; font-size:13px;">Desarquivar</button>
          </div>
        `;

        row.querySelector('.archived-open-btn').addEventListener('click', () => {
          if (window.HermesChats) {
            window.HermesChats.loadChat(chat);
            window.HermesChats.showView('chat');
            closeSettings();
          }
        });

        row.querySelector('.archived-unarchive-btn').addEventListener('click', async () => {
          try {
            const patchRes = await fetch(`${API()}/chats/${chat.id}`, {
              method: 'PATCH',
              headers: { 'Content-Type': 'application/json' },
              body: JSON.stringify({ archived: false }),
            });
            if (!patchRes.ok) throw new Error('Falha ao desarquivar');
            if (window.HermesChats) window.HermesChats.renderSidebar();
            renderArchivedChats();
          } catch (err) {
            console.error('[Hermes] Erro ao desarquivar conversa:', err);
          }
        });

        archivedChatsList.appendChild(row);
      });
    } catch (err) {
      console.error('[Hermes] Erro ao carregar conversas arquivadas:', err);
      archivedChatsList.innerHTML = `<div class="chat-list-empty">Erro ao carregar conversas arquivadas</div>`;
    }
  }

  // Atualiza a lista de arquivadas sempre que um chat é arquivado/desarquivado
  // em outro lugar do app (ex. menu de contexto na sidebar).
  document.addEventListener('hermes:chats-changed', () => {
    if (document.getElementById('panel-dados').classList.contains('active')) {
      renderArchivedChats();
    }
  });

  /* ---------- Aparência (claro / escuro / sistema) ---------- */
  const appearanceChips = document.querySelectorAll('#appearance-chips .settings-chip');

  function applyAppearance(choice) {
    // Delega para o módulo compartilhado (ui.js), que também cuida do
    // ícone do botão rápido de tema no topo, mantendo os dois em sincronia.
    if (window.HermesTheme) {
      window.HermesTheme.apply(choice);
    } else if (choice === 'system') {
      const prefersDark = window.matchMedia('(prefers-color-scheme: dark)').matches;
      document.body.setAttribute('data-theme', prefersDark ? 'dark' : 'light');
    } else {
      document.body.setAttribute('data-theme', choice);
    }
  }

  appearanceChips.forEach((chip) => {
    chip.addEventListener('click', () => {
      appearanceChips.forEach((c) => c.classList.remove('active'));
      chip.classList.add('active');
      const choice = chip.dataset.themeChoice;
      applyAppearance(choice);
      patchProfile({ theme: choice });
    });
  });

  /* ---------- Idioma ---------- */
  const languageSelect = document.getElementById('language-select');
  languageSelect.addEventListener('change', () => {
    patchProfile({ language: languageSelect.value });
  });

  /* ---------- Carregar perfil ao abrir o modal (aparência, idioma, push, RAM) ---------- */
  async function loadProfileIntoSettings() {
    try {
      const res = await fetch(`${API()}/profile/`);
      if (!res.ok) throw new Error('Falha ao carregar perfil');
      const profile = await res.json();

      // Aparência
      appearanceChips.forEach((chip) => {
        chip.classList.toggle('active', chip.dataset.themeChoice === profile.theme);
      });
      applyAppearance(profile.theme);

      // Idioma
      languageSelect.value = profile.language || 'pt-br';

      // Notificações push
      pushToggle.checked = !!profile.push_on_response_done;
      window.HermesNotifications.setEnabled(pushToggle.checked);

      // Armazenamento (RAM)
      memorySlider.value = profile.ram_limit_gb;
      memoryValue.textContent = profile.ram_limit_gb + ' GB';

      // Modo engenheiro
      engineerModeToggle.checked = !!profile.engineer_mode_enabled;
      applyEngineerModeVisibility(!!profile.engineer_mode_enabled);

      // Carregar campos do modelo engenheiro
      if (profile.engineer_model_path !== undefined) {
        document.getElementById('engineer-model-path').value = profile.engineer_model_path || '';
      }
      if (profile.engineer_model_url !== undefined) {
        document.getElementById('engineer-model-url').value = profile.engineer_model_url || '';
      }
    } catch (err) {
      console.error('[Hermes] Erro ao carregar perfil nas configurações:', err);
    }
  }

  /* ---------- Helper genérico de PATCH /profile ---------- */
  function patchProfile(fields) {
    return fetch(`${API()}/profile/`, {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(fields),
    }).catch((err) => {
      console.error('[Hermes] Erro ao salvar configuração:', err);
    });
  }

  /* ---------- Notificações push ---------- */
  const pushToggle = document.getElementById('push-toggle');

  pushToggle.addEventListener('change', async () => {
    const enabled = pushToggle.checked;

    if (enabled && 'Notification' in window && Notification.permission === 'default') {
      // Primeira ativação: pede permissão ao navegador.
      try {
        await Notification.requestPermission();
      } catch (err) {
        console.error('[Hermes] Erro ao pedir permissão de notificação:', err);
      }
    }

    window.HermesNotifications.setEnabled(enabled);
    patchProfile({ push_on_response_done: enabled });
  });

  /* ---------- Controle de dados (ações destrutivas) ---------- */
  document.querySelectorAll('[data-action]').forEach((btn) => {
    btn.addEventListener('click', async () => {
      const action = btn.dataset.action;
      const messages = {
        'delete-all-chats': 'Apagar TODOS os chats? Essa ação não pode ser desfeita.',
        'delete-non-project-chats': 'Apagar todos os chats fora de projetos?',
        'delete-all-projects': 'Apagar TODOS os projetos e seus conteúdos?',
      };

      if (!confirm(messages[action])) return;

      try {
        let res;
        if (action === 'delete-all-chats') {
          res = await fetch(`${API()}/chats/?scope=all`, { method: 'DELETE' });
          if (res.ok) notifyChatsChanged();
        } else if (action === 'delete-non-project-chats') {
          res = await fetch(`${API()}/chats/?scope=non_project`, { method: 'DELETE' });
          if (res.ok) notifyChatsChanged();
        } else if (action === 'delete-all-projects') {
          res = await fetch(`${API()}/projects/?scope=all`, { method: 'DELETE' });
          if (res.ok) notifyProjectsChanged();
        }
        if (res && !res.ok) {
          console.error('[Hermes] Falha ao executar ação destrutiva:', action, res.status);
        }
      } catch (err) {
        console.error('[Hermes] Erro ao executar ação destrutiva:', action, err);
      }
    });
  });

  function notifyChatsChanged() {
    // Limpar o chat/projeto ativo, já que podem ter sido apagados.
    window.HermesState.currentChatId = null;

    if (window.HermesChats && typeof window.HermesChats.renderSidebar === 'function') {
      window.HermesChats.renderSidebar();
    }
    document.dispatchEvent(new CustomEvent('hermes:chats-changed'));
  }

  function notifyProjectsChanged() {
    window.HermesState.activeProjectId = null;

    // Re-renderiza a lista de projetos só se a view estiver aberta.
    const viewProjects = document.getElementById('view-projects');
    if (viewProjects && viewProjects.classList.contains('active') && window.HermesProjects) {
      window.HermesProjects.renderProjectsList();
    }
    document.dispatchEvent(new CustomEvent('hermes:projects-changed'));
  }

  /* ---------- Armazenamento (limite de memória / RAM) ---------- */
  const memorySlider = document.getElementById('memory-slider');
  const memoryValue = document.getElementById('memory-value');

  let ramSaveTimer = null;
  memorySlider.addEventListener('input', () => {
    memoryValue.textContent = memorySlider.value + ' GB';

    if (ramSaveTimer) clearTimeout(ramSaveTimer);
    const value = parseInt(memorySlider.value, 10);
    ramSaveTimer = setTimeout(() => {
      patchProfile({ ram_limit_gb: value });
    }, 500);
  });

  /* ---------- Modo engenheiro (avançado) ---------- */
  const engineerModeToggle = document.getElementById('engineer-mode-toggle');
  const engineerModeDetails = document.getElementById('engineer-mode-details');
  const engineerDownloadLink = document.getElementById('engineer-download-link');
  const engineerInstallDir = document.getElementById('engineer-install-dir');
  const engineerChip = document.getElementById('mode-engineer');

  let engineerInfoLoaded = false;
  async function loadEngineerInfo() {
    if (engineerInfoLoaded) return;
    try {
      const res = await fetch(`${API()}/system/engineer-info`);
      if (!res.ok) throw new Error('Falha ao consultar engineer-info');
      const info = await res.json();
      engineerDownloadLink.textContent = info.download_url;
      engineerDownloadLink.href = info.download_url;
      engineerInstallDir.textContent = info.install_dir;
      engineerInfoLoaded = true;
    } catch (err) {
      console.error('[Hermes] Erro ao carregar informações do modo engenheiro:', err);
      engineerDownloadLink.textContent = 'indisponível no momento';
    }
  }

  function applyEngineerModeVisibility(enabled) {
    engineerChip.style.display = enabled ? '' : 'none';
    engineerModeDetails.classList.toggle('hidden', !enabled);
    if (enabled) loadEngineerInfo();
    // Se o usuário desligar com o chip ativo selecionado, volta pro padrão.
    if (!enabled && engineerChip.classList.contains('active')) {
      engineerChip.classList.remove('active');
    }
  }

  engineerModeToggle.addEventListener('change', () => {
    const enabled = engineerModeToggle.checked;
    applyEngineerModeVisibility(enabled);
    patchProfile({ engineer_mode_enabled: enabled });
  });

  // Aplica a visibilidade do chip assim que o app carrega, sem esperar o
  // usuário abrir o modal de configurações.
  (async () => {
    try {
      const res = await fetch(`${API()}/profile/`);
      if (!res.ok) return;
      const profile = await res.json();
      engineerModeToggle.checked = !!profile.engineer_mode_enabled;
      applyEngineerModeVisibility(!!profile.engineer_mode_enabled);
    } catch (err) {
      console.error('[Hermes] Erro ao pré-carregar estado do modo engenheiro:', err);
    }
  })();

  /* ---------- Medidor de RAM/CPU em tempo real ---------- */
  const RESOURCE_POLL_INTERVAL_MS = 5000;
  const resourceMeterFill = document.getElementById('resource-meter-fill');
  const resourceMeterRamLabel = document.getElementById('resource-meter-ram-label');
  const resourceMeterCpuLabel = document.getElementById('resource-meter-cpu-label');
  const resourceMeterStatus = document.getElementById('resource-meter-status');

  let resourcePollTimer = null;

  async function fetchAndRenderResourceStatus() {
    try {
      const res = await fetch(`${API()}/system/status`);
      if (!res.ok) throw new Error('Falha ao consultar /system/status');
      const status = await res.json();
      renderResourceStatus(status);
    } catch (err) {
      console.error('[Hermes] Erro ao consultar status de recursos:', err);
      resourceMeterStatus.textContent = 'Indicador indisponível';
    }
  }

  function renderResourceStatus(status) {
    const percent = Math.max(0, Math.min(100, status.ram_percent));
    resourceMeterFill.style.width = percent + '%';
    resourceMeterFill.classList.remove('warn', 'danger');
    if (status.under_pressure) {
      resourceMeterFill.classList.add('danger');
    } else if (percent >= 60) {
      resourceMeterFill.classList.add('warn');
    }

    resourceMeterRamLabel.textContent = `${status.ram_used_gb} / ${status.ram_limit_gb} GB`;
    resourceMeterCpuLabel.textContent = `CPU: ${status.cpu_percent}%`;

    resourceMeterStatus.classList.toggle('danger', !!status.under_pressure);
    resourceMeterStatus.textContent = status.under_pressure
      ? `Recursos escassos (${status.process_count} processo(s) ativo(s))`
      : `Normal (${status.process_count} processo(s) ativo(s))`;
  }

  function startResourceMeterPolling() {
    if (resourcePollTimer) return;
    fetchAndRenderResourceStatus();
    resourcePollTimer = setInterval(fetchAndRenderResourceStatus, RESOURCE_POLL_INTERVAL_MS);
  }

  function stopResourceMeterPolling() {
    if (resourcePollTimer) {
      clearInterval(resourcePollTimer);
      resourcePollTimer = null;
    }
  }

  /* ---------- Painel Modelos ---------- */
  const engineerPathInput = document.getElementById('engineer-model-path');
  const engineerUrlInput = document.getElementById('engineer-model-url');
  const testEngineerBtn = document.getElementById('test-engineer-btn');
  const engineerTestResult = document.getElementById('engineer-test-result');

  // Salvar ao blur
  engineerPathInput.addEventListener('blur', () => {
    patchProfile({ engineer_model_path: engineerPathInput.value || null });
  });
  engineerUrlInput.addEventListener('blur', () => {
    patchProfile({ engineer_model_url: engineerUrlInput.value || null });
  });

  testEngineerBtn.addEventListener('click', async () => {
    engineerTestResult.textContent = 'Testando...';
    try {
      const res = await fetch(`${API()}/system/test-engineer`);
      const data = await res.json();
      if (data.status === 'ok') {
        engineerTestResult.textContent = '✅ Conexão OK';
      } else {
        engineerTestResult.textContent = '❌ ' + (data.message || 'Falha no teste');
      }
    } catch (err) {
      engineerTestResult.textContent = '❌ Erro ao testar: ' + err.message;
    }
  });
})();
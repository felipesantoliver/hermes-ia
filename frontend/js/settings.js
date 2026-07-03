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
    });
  });

  /* ---------- Aparência (claro / escuro / sistema) ---------- */
  const appearanceChips = document.querySelectorAll('#appearance-chips .settings-chip');

  function applyAppearance(choice) {
    if (choice === 'system') {
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
})();
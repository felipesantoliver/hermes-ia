/* ===================== MODAL DE CONFIGURAÇÕES ===================== */
/* Responsabilidade: abrir/fechar o modal, trocar entre painéis da
   sidebar interna, aparência, notificações, controle de dados
   e limite de armazenamento (memória). */

(function () {
  const overlay = document.getElementById('settings-overlay');
  const openBtn = document.getElementById('settings-btn');
  const closeBtn = document.getElementById('settings-close');

  /* ---------- Abrir / fechar modal ---------- */
  function openSettings() {
    overlay.classList.add('open');
  }
  function closeSettings() {
    overlay.classList.remove('open');
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
      applyAppearance(chip.dataset.themeChoice);
    });
  });

  /* ---------- Controle de dados ---------- */
  document.querySelectorAll('[data-action]').forEach((btn) => {
    btn.addEventListener('click', () => {
      const action = btn.dataset.action;
      const messages = {
        'delete-all-chats': 'Apagar TODOS os chats? Essa ação não pode ser desfeita.',
        'delete-non-project-chats': 'Apagar todos os chats fora de projetos?',
        'delete-all-projects': 'Apagar TODOS os projetos e seus conteúdos?',
      };

      if (confirm(messages[action])) {
        // TODO: integrar com o backend para de fato apagar os dados.
        console.log('[Hermes] Ação de controle de dados confirmada:', action);
      }
    });
  });

  /* ---------- Armazenamento (limite de memória) ---------- */
  const memorySlider = document.getElementById('memory-slider');
  const memoryValue = document.getElementById('memory-value');

  memorySlider.addEventListener('input', () => {
    memoryValue.textContent = memorySlider.value + ' GB';
    // TODO: enviar esse valor ao backend (ex: MAX_CONTEXT / limite de RAM do modelo).
  });
})();
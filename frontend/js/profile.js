/* ===================== MODAL DE PERFIL ===================== */
/* Responsabilidade: abrir/fechar o modal de perfil, carregar o perfil
   salvo (GET /profile), popular todos os campos, e persistir qualquer
   mudança via PATCH /profile — sem botão "Salvar" explícito (auto-save):
   blur para textareas/inputs de texto, change imediato para
   chips/scale-btn/toggle. */

(function () {
  const API = () => window.HermesState.API_BASE;

  const overlay = document.getElementById('profile-overlay');
  const openBtn = document.getElementById('profile-btn');
  const closeBtn = document.getElementById('profile-close');

  const els = {
    name: document.getElementById('user-name'),
    about: document.getElementById('user-about'),
    nickname: document.getElementById('hermes-nickname'),
    personalityChips: document.querySelectorAll('#personality-chips .settings-chip'),
    personalityCustom: document.getElementById('personality-custom'),
    filterScale: document.getElementById('filter-scale'),
    filterCustom: document.getElementById('filter-custom'),
    warmthScale: document.getElementById('warmth-scale'),
    enthusiasmScale: document.getElementById('enthusiasm-scale'),
    emojiScale: document.getElementById('emoji-scale'),
    memoryToggle: document.getElementById('memory-toggle'),
    showThinkingToggle: document.getElementById('show-thinking-toggle'),
  };

  let profileLoaded = false;

  /* ---------- Abrir / fechar modal ---------- */
  function openProfile() {
    overlay.classList.add('open');
    if (!profileLoaded) loadProfile();
  }
  function closeProfile() {
    overlay.classList.remove('open');
  }

  openBtn.addEventListener('click', openProfile);
  closeBtn.addEventListener('click', closeProfile);

  overlay.addEventListener('click', (e) => {
    if (e.target === overlay) closeProfile();
  });

  document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape' && overlay.classList.contains('open')) closeProfile();
  });

  /* ---------- Carregar perfil e popular campos ---------- */
  async function loadProfile() {
    try {
      const res = await fetch(`${API()}/profile/`);
      if (!res.ok) throw new Error('Falha ao carregar perfil');
      const profile = await res.json();
      populateFields(profile);
      profileLoaded = true;
    } catch (err) {
      console.error('[Hermes] Erro ao carregar perfil:', err);
    }
  }

  function populateFields(profile) {
    els.name.value = profile.display_name || '';
    els.about.value = profile.about || '';
    els.nickname.value = profile.hermes_nickname || '';

    // Personalidade
    els.personalityChips.forEach((chip) => {
      const isActive = chip.dataset.personality === profile.personality;
      chip.classList.toggle('active', isActive);
    });
    els.personalityCustom.value = profile.personality_custom || '';
    els.personalityCustom.classList.toggle('hidden', profile.personality !== 'personalizado');

    // Filtro de conteúdo (1-4 ou -1 = custom)
    const filterValue = profile.content_filter_level === -1 ? 'custom' : String(profile.content_filter_level);
    setScaleActive(els.filterScale, filterValue);
    els.filterCustom.value = profile.content_filter_custom || '';
    els.filterCustom.classList.toggle('hidden', filterValue !== 'custom');

    // Acolhimento / entusiasmo / emojis (1-3)
    setScaleActive(els.warmthScale, String(profile.warmth_level));
    setScaleActive(els.enthusiasmScale, String(profile.enthusiasm_level));
    setScaleActive(els.emojiScale, String(profile.emoji_level));

    // Memória
    els.memoryToggle.checked = !!profile.use_saved_memory;

    // Pensamento visível
    els.showThinkingToggle.checked = !!profile.show_thinking;
  }

  function setScaleActive(container, value) {
    container.querySelectorAll('.scale-btn').forEach((btn) => {
      btn.classList.toggle('active', btn.dataset.value === value);
    });
  }

  /* ---------- Auto-save: debounce (500ms) acumulando campos pendentes ---------- */
  let pendingFields = {};
  let saveTimer = null;

  function flushSave() {
    if (saveTimer) {
      clearTimeout(saveTimer);
      saveTimer = null;
    }
    if (Object.keys(pendingFields).length === 0) return;

    const fields = pendingFields;
    pendingFields = {};

    fetch(`${API()}/profile/`, {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(fields),
    }).catch((err) => {
      console.error('[Hermes] Erro ao salvar perfil:', err);
    });
  }

  // Usado por textareas/inputs de texto: acumula e espera 500ms de inatividade.
  function queueSave(fields) {
    Object.assign(pendingFields, fields);
    if (saveTimer) clearTimeout(saveTimer);
    saveTimer = setTimeout(flushSave, 500);
  }

  // Usado por chips/scale-btn/toggle: salva imediatamente (sem esperar debounce).
  function saveNow(fields) {
    Object.assign(pendingFields, fields);
    flushSave();
  }

  /* ---------- Campos de texto: salvam no blur ---------- */
  els.name.addEventListener('blur', () => queueSave({ display_name: els.name.value }));
  els.about.addEventListener('blur', () => queueSave({ about: els.about.value || null }));
  els.nickname.addEventListener('blur', () => queueSave({ hermes_nickname: els.nickname.value || null }));
  els.personalityCustom.addEventListener('blur', () => queueSave({ personality_custom: els.personalityCustom.value || null }));
  els.filterCustom.addEventListener('blur', () => queueSave({ content_filter_custom: els.filterCustom.value || null }));

  /* ---------- Personalidade (chips) ---------- */
  els.personalityChips.forEach((chip) => {
    chip.addEventListener('click', () => {
      els.personalityChips.forEach((c) => c.classList.remove('active'));
      chip.classList.add('active');

      const value = chip.dataset.personality;
      const isCustom = value === 'personalizado';
      els.personalityCustom.classList.toggle('hidden', !isCustom);

      saveNow({ personality: value });
    });
  });

  /* ---------- Escalas genéricas (filtro, acolhimento, entusiasmo, emojis) ---------- */
  function setupScale(container, onValue) {
    const buttons = container.querySelectorAll('.scale-btn');
    buttons.forEach((btn) => {
      btn.addEventListener('click', () => {
        buttons.forEach((b) => b.classList.remove('active'));
        btn.classList.add('active');
        onValue(btn.dataset.value);
      });
    });
  }

  // Filtro de conteúdo: "custom" no front vira -1 no backend; mostra/esconde textarea.
  setupScale(els.filterScale, (value) => {
    els.filterCustom.classList.toggle('hidden', value !== 'custom');
    const level = value === 'custom' ? -1 : parseInt(value, 10);
    saveNow({ content_filter_level: level });
  });

  setupScale(els.warmthScale, (value) => saveNow({ warmth_level: parseInt(value, 10) }));
  setupScale(els.enthusiasmScale, (value) => saveNow({ enthusiasm_level: parseInt(value, 10) }));
  setupScale(els.emojiScale, (value) => saveNow({ emoji_level: parseInt(value, 10) }));

  /* ---------- Toggle de memória ---------- */
  els.memoryToggle.addEventListener('change', () => {
    saveNow({ use_saved_memory: els.memoryToggle.checked });
  });

  /* ---------- Toggle de pensamento visível (sincroniza com o chip do chat) ---------- */
  els.showThinkingToggle.addEventListener('change', () => {
    if (window.HermesSetShowThinking) {
      window.HermesSetShowThinking(els.showThinkingToggle.checked); // já persiste via PATCH
    } else {
      saveNow({ show_thinking: els.showThinkingToggle.checked });
    }
  });

  // Salva qualquer campo pendente se o usuário fechar o modal antes dos 500ms.
  overlay.addEventListener('click', (e) => {
    if (e.target === overlay) flushSave();
  });
  closeBtn.addEventListener('click', flushSave);
  document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape') flushSave();
  });
  window.addEventListener('beforeunload', flushSave);
})();
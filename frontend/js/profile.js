/* ===================== MODAL DE PERFIL ===================== */
/* Responsabilidade: abrir/fechar o modal de perfil e controlar
   personalidade, filtro de conteúdo, acolhimento, entusiasmo,
   emojis e referência a memórias salvas. */

(function () {
  const overlay = document.getElementById('profile-overlay');
  const openBtn = document.getElementById('profile-btn');
  const closeBtn = document.getElementById('profile-close');

  /* ---------- Abrir / fechar modal ---------- */
  function openProfile() {
    overlay.classList.add('open');
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

  /* ---------- Personalidade (com opção de personalizar) ---------- */
  const personalityChips = document.querySelectorAll('#personality-chips .settings-chip');
  const personalityCustom = document.getElementById('personality-custom');

  personalityChips.forEach((chip) => {
    chip.addEventListener('click', () => {
      personalityChips.forEach((c) => c.classList.remove('active'));
      chip.classList.add('active');

      const isCustom = chip.dataset.personality === 'personalizado';
      personalityCustom.classList.toggle('hidden', !isCustom);
    });
  });

  /* ---------- Escalas genéricas (filtro, acolhimento, entusiasmo, emojis) ---------- */
  function setupScale(containerId, onChange) {
    const container = document.getElementById(containerId);
    const buttons = container.querySelectorAll('.scale-btn');

    buttons.forEach((btn) => {
      btn.addEventListener('click', () => {
        buttons.forEach((b) => b.classList.remove('active'));
        btn.classList.add('active');
        if (onChange) onChange(btn.dataset.value);
      });
    });
  }

  // Filtro de conteúdo tem um campo extra de texto quando "Personalizado" é escolhido
  const filterCustom = document.getElementById('filter-custom');
  setupScale('filter-scale', (value) => {
    filterCustom.classList.toggle('hidden', value !== 'custom');
  });

  setupScale('warmth-scale');
  setupScale('enthusiasm-scale');
  setupScale('emoji-scale');

  /* ---------- Persistência simples (TODO: enviar ao backend) ---------- */
  // Por enquanto os valores só ficam salvos na interface durante a sessão.
  // Quando o backend do perfil existir, capturar todos os campos aqui
  // (nome, sobre você, apelido, personalidade, filtro, acolhimento,
  // entusiasmo, emojis e memória) e enviar via fetch para /profile.
})();
/* ===================== GALERIA DE ARQUIVOS ===================== */
/* Responsabilidade: listar todos os arquivos (enviados pelo usuário e
   gerados pelo Hermes) em grid de cards, com filtros por origem, busca
   por nome, download e exclusão. Consome GET /files/all-sources. */

(function () {
  const API = () => window.HermesState.API_BASE;
  const view = document.getElementById('view-gallery');

  const IMAGE_TYPES = new Set(['png', 'jpg', 'jpeg', 'gif', 'webp', 'svg', 'bmp']);

  let allItems = [];
  let activeFilter = 'all'; // 'all' | 'uploaded' | 'generated'
  let searchTerm = '';
  let semanticSearchActive = false; // <-- NOVO: indica se a busca semântica foi ativada

  /* ---------- Navegação para a view de galeria ---------- */
  document.getElementById('gallery-nav-btn').addEventListener('click', () => {
    window.HermesChats.showView('gallery');
    renderGallery();
  });

  /* ---------- Sair da galeria ao clicar em outro item da sidebar ----------
     Usa fase de captura para rodar ANTES do listener próprio de cada item
     (novo chat, buscar, projetos, configurações, um chat fixado/recente
     etc.), garantindo que a troca de view aconteça independentemente da
     ordem em que os outros scripts registraram seus handlers. Só age
     quando a galeria está de fato aberta; o próprio botão da galeria é
     ignorado para não causar um "pisca" desnecessário. */
  const sidebarEl = document.getElementById('sidebar');
  sidebarEl.addEventListener('click', (e) => {
    if (!view.classList.contains('active')) return; // não está na galeria
    const target = e.target.closest('.side-item, .chat-item, .pinned-item');
    if (!target || target.id === 'gallery-nav-btn') return;
    window.HermesChats.showView('chat');
  }, true);

  /* ---------- Shell da view (renderizado uma vez, atualizado depois) ---------- */
  function renderShell() {
    view.innerHTML = `
      <div class="gallery-header">
        <h1>Galeria</h1>
      </div>
      <div class="gallery-toolbar">
        <div class="gallery-chips">
          <button class="gallery-chip active" data-filter="all">Todos</button>
          <button class="gallery-chip" data-filter="uploaded">Enviados</button>
          <button class="gallery-chip" data-filter="generated">Gerados</button>
        </div>
        <div style="display:flex; gap:8px; flex:1; max-width:420px;">
          <input type="text" id="gallery-search" class="gallery-search" placeholder="Buscar por nome ou conteúdo...">
          <button id="gallery-semantic-search-btn" class="primary-btn" style="padding:8px 14px; font-size:13px;">🔍 Inteligente</button>
        </div>
      </div>
      <div id="gallery-grid" class="gallery-grid"></div>
    `;

    view.querySelectorAll('.gallery-chip').forEach((chip) => {
      chip.addEventListener('click', () => {
        view.querySelectorAll('.gallery-chip').forEach((c) => c.classList.remove('active'));
        chip.classList.add('active');
        activeFilter = chip.dataset.filter;
        renderGrid();
      });
    });

    const searchInput = document.getElementById('gallery-search');
    searchInput.addEventListener('input', () => {
      searchTerm = searchInput.value.trim().toLowerCase();
      semanticSearchActive = false; // busca por nome cancela a semântica
      renderGrid();
    });

    // Botão de busca semântica
    document.getElementById('gallery-semantic-search-btn').addEventListener('click', () => {
      const query = document.getElementById('gallery-search').value.trim();
      if (!query) {
        alert('Digite uma consulta para a busca inteligente.');
        return;
      }
      semanticSearchActive = true;
      renderGrid();
    });
  }

  /* ---------- Carregamento dos dados ---------- */
  async function renderGallery() {
    renderShell();
    const grid = document.getElementById('gallery-grid');
    grid.innerHTML = `<div class="chat-list-empty">Carregando arquivos...</div>`;

    try {
      // Carrega todos os itens (sem filtro de busca semântica)
      const res = await fetch(`${API()}/files/all-sources`);
      if (!res.ok) throw new Error('Falha ao carregar arquivos');
      allItems = await res.json();
      renderGrid();
    } catch (err) {
      console.error('[Hermes] Erro ao carregar galeria:', err);
      grid.innerHTML = `<div class="chat-list-empty">Erro ao carregar arquivos.</div>`;
    }
  }

  function matchesFilter(item) {
    if (activeFilter === 'all') return true;
    if (activeFilter === 'generated') return item.origin === 'generated';
    // 'uploaded': tanto loose upload quanto arquivo de projeto (sempre upload)
    return item.origin === 'upload' || item.source === 'project';
  }

  function matchesSearch(item) {
    if (!searchTerm) return true;
    return item.filename.toLowerCase().includes(searchTerm);
  }

  /* ---------- Grid de cards ---------- */
  async function renderGrid() {
    const grid = document.getElementById('gallery-grid');
    if (!grid) return;

    let filtered = allItems.filter((i) => matchesFilter(i));

    // Se busca semântica estiver ativa, consulta o backend com parâmetro search
    if (semanticSearchActive && searchTerm) {
      try {
        const res = await fetch(`${API()}/files/all-sources?search=${encodeURIComponent(searchTerm)}`);
        if (!res.ok) throw new Error('Falha na busca semântica');
        const semanticItems = await res.json();
        // Substitui a lista filtrada pelos itens semânticos (já filtrados pelo backend)
        filtered = semanticItems;
      } catch (err) {
        console.error('[Hermes] Erro na busca semântica:', err);
        alert('Erro na busca inteligente. Tente novamente.');
        semanticSearchActive = false;
        filtered = allItems.filter((i) => matchesFilter(i) && matchesSearch(i));
      }
    } else {
      // Filtro por nome normal
      filtered = filtered.filter(matchesSearch);
    }

    if (allItems.length === 0) {
      grid.innerHTML = `
        <div class="gallery-empty">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6"><rect x="3" y="3" width="18" height="18" rx="2"/><circle cx="8.5" cy="8.5" r="1.5"/><path d="M21 15l-5-5L5 21"/></svg>
          <p>Nenhum arquivo por aqui ainda.</p>
          <span>Arquivos que você enviar ou que o Hermes gerar vão aparecer nesta galeria.</span>
        </div>
      `;
      return;
    }

    if (filtered.length === 0) {
      grid.innerHTML = `<div class="chat-list-empty">Nenhum arquivo corresponde ao filtro/busca.</div>`;
      return;
    }

    grid.innerHTML = '';
    for (const item of filtered) {
      grid.appendChild(buildCard(item));
    }
  }

  function buildCard(item) {
    const card = document.createElement('div');
    card.className = 'gallery-card';

    const isImage = IMAGE_TYPES.has((item.file_type || '').toLowerCase());
    const badgeText = item.origin === 'generated' ? 'Gerado pelo Hermes' : 'Enviado por você';
    const badgeClass = item.origin === 'generated' ? 'generated' : 'uploaded';
    const originLabel = item.project_id
      ? 'Projeto'
      : (item.chat_id ? 'Chat' : '—');

    card.innerHTML = `
      <div class="gallery-card-preview">
        ${isImage
          ? `<img src="${API()}/files/${item.id}/download" alt="${escapeHtml(item.filename)}" loading="lazy">`
          : fileIconSvg(item.file_type)}
      </div>
      <div class="gallery-card-body">
        <div class="gallery-card-name" title="${escapeHtml(item.filename)}">${escapeHtml(item.filename)}</div>
        <div class="gallery-card-meta">
          <span>${formatSize(item.size_bytes)}</span>
          <span>&middot;</span>
          <span>${formatDate(item.created_at)}</span>
        </div>
        <div class="gallery-card-meta">
          <span class="gallery-badge ${badgeClass}">${badgeText}</span>
          <span class="gallery-origin">${originLabel}</span>
        </div>
      </div>
      <div class="gallery-card-actions">
        <button class="ghost-btn gallery-download-btn">Baixar</button>
        <button class="ghost-btn gallery-delete-btn">Apagar</button>
      </div>
    `;

    card.querySelector('.gallery-download-btn').addEventListener('click', () => downloadFile(item));
    card.querySelector('.gallery-delete-btn').addEventListener('click', () => deleteFile(item));

    return card;
  }

  /* ---------- Ações ---------- */
  function downloadFile(item) {
    const a = document.createElement('a');
    a.href = `${API()}/files/${item.id}/download`;
    a.download = item.filename;
    document.body.appendChild(a);
    a.click();
    a.remove();
  }

  async function deleteFile(item) {
    if (!confirm(`Apagar "${item.filename}"? Essa ação não pode ser desfeita.`)) return;
    try {
      const res = await fetch(`${API()}/files/${item.id}`, { method: 'DELETE' });
      if (!res.ok && res.status !== 204) throw new Error('Falha ao apagar arquivo');
      allItems = allItems.filter((i) => i.id !== item.id);
      renderGrid();
    } catch (err) {
      console.error('[Hermes] Erro ao apagar arquivo:', err);
      alert('Não foi possível apagar o arquivo.');
    }
  }

  /* ---------- Helpers ---------- */
  function formatSize(bytes) {
    if (bytes < 1024) return `${bytes} B`;
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
    return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
  }

  function formatDate(iso) {
    try {
      const d = new Date(iso);
      return d.toLocaleDateString('pt-BR', { day: '2-digit', month: '2-digit', year: 'numeric' });
    } catch (_) {
      return iso;
    }
  }

  function fileIconSvg(fileType) {
    return `
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6">
        <path d="M14 2H6a2 2 0 00-2 2v16a2 2 0 002 2h12a2 2 0 002-2V8z"/>
        <path d="M14 2v6h6"/>
      </svg>
      <span class="gallery-file-ext">${escapeHtml((fileType || '').toUpperCase())}</span>
    `;
  }

  function escapeHtml(str) {
    const div = document.createElement('div');
    div.textContent = str || '';
    return div.innerHTML;
  }

  window.HermesGallery = { renderGallery };
})();
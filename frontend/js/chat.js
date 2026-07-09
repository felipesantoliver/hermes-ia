/* ===================== LÓGICA DO CHAT ===================== */
/* Responsabilidade: gerenciar envio de mensagens, integração com backend,
   indicador de "digitando", upload de arquivos, preview, e renderização
   de plano multi‑step (V2.2). */

const msgCol = document.getElementById('msg-col');
const messagesEl = document.getElementById('messages');
// Nome distinto de propósito: ui.js já declara um `const input` no escopo
// global (scripts clássicos compartilham o mesmo escopo de topo), então usar
// o mesmo nome aqui causava "Identifier 'input' has already been declared"
// ao carregar chat.js — um SyntaxError que impedia o arquivo INTEIRO de
// rodar (nenhuma função definida, nenhum listener de envio/Enter registrado).
// Por isso enviar mensagem não fazia nada e Enter só quebrava linha.
const msgInput = document.getElementById('msg-input');
const sendBtn = document.getElementById('send-btn');

let typingIndicator = null;
let planCard = null; // referência ao card do plano ativo

/* ---------- Iniciais do usuário no avatar (em vez de "FS" fixo) ---------- */
// Antes o avatar do usuário mostrava sempre o texto fixo "FS", ignorando o
// nome salvo no perfil. Agora buscamos o display_name salvo e calculamos as
// iniciais dinamicamente, com um valor neutro de fallback enquanto carrega
// ou caso o nome ainda não tenha sido preenchido.
let cachedUserInitials = '👤';

// ---------- Preferência de "Mostrar pensamento" ----------
// O toggle em Configurações (show-thinking-toggle) persistia corretamente
// no backend via PATCH /profile, mas o chat nunca lia esse valor de volta:
// o payload enviado ao backend usava "show_thinking: mode === 'analyst'",
// um valor fixo que ignorava por completo a preferência do usuário — por
// isso o toggle não tinha efeito nenhum fora do modo analista. Além disso,
// profile.js chamava "window.HermesSetShowThinking(...)", uma função que
// nunca existia em lugar nenhum do código (só o fallback via saveNow()
// direto rodava, que persiste no banco mas não atualiza o chat ao vivo).
let cachedShowThinkingEnabled = false;

function computeInitials(name) {
  const trimmed = (name || '').trim();
  if (!trimmed) return '👤';
  const parts = trimmed.split(/\s+/).filter(Boolean);
  if (parts.length === 1) return parts[0].slice(0, 2).toUpperCase();
  return (parts[0][0] + parts[parts.length - 1][0]).toUpperCase();
}

async function refreshCachedProfilePrefs() {
  try {
    const res = await fetch(`${window.HermesState.API_BASE}/profile/`);
    if (!res.ok) throw new Error('Falha ao carregar perfil');
    const profile = await res.json();
    cachedUserInitials = computeInitials(profile.display_name);
    cachedShowThinkingEnabled = !!profile.show_thinking;
    // Atualiza avatares já renderizados na tela (ex.: se o nome mudou
    // enquanto o usuário já tinha mensagens no histórico).
    document.querySelectorAll('.avatar.user').forEach((el) => {
      el.textContent = cachedUserInitials;
    });
  } catch (err) {
    console.error('[Hermes] Erro ao carregar preferências do perfil:', err);
  }
}
refreshCachedProfilePrefs();
// Permite que profile.js peça atualização imediata após salvar o nome.
window.HermesRefreshUserInitials = refreshCachedProfilePrefs;
// Chamado pelo toggle "Mostrar pensamento" em Configurações assim que o
// usuário muda a opção — atualiza o valor usado nas PRÓXIMAS mensagens
// imediatamente, sem esperar um novo carregamento da página.
window.HermesSetShowThinking = function (enabled) {
  cachedShowThinkingEnabled = !!enabled;
};

/**
 * Adiciona uma mensagem na conversa.

 * @param {'user'|'hermes'} role
 * @param {string} text
 * @param {string} [messageId] - id da mensagem no backend (permite editar depois)
 * @returns {HTMLElement} o elemento .msg criado
 */
function addMessage(role, text, messageId) {
  const emptyState = document.getElementById('empty-state');
  if (emptyState) emptyState.remove();

  const msg = document.createElement('div');
  msg.className = 'msg ' + role;
  msg.dataset.messageId = messageId || '';

  const avatar = document.createElement('div');
  avatar.className = 'avatar ' + (role === 'user' ? 'user' : 'hermes');
  if (role === 'user') avatar.textContent = cachedUserInitials;

  const bubbleWrap = document.createElement('div');
  if (role !== 'user') {
    const meta = document.createElement('div');
    meta.className = 'msg-meta';
    meta.textContent = 'Hermes';
    bubbleWrap.appendChild(meta);
  }

  const bubble = document.createElement('div');
  bubble.className = 'bubble';
  if (role === 'user') {
    bubble.textContent = text;
  } else {
    bubble.innerHTML = renderMarkdown(text);
    // Botão de copiar só nos blocos de código markdown (ex.: ```js ... ```).
    // Texto normal é copiado via seleção com o mouse, como em qualquer
    // editor — sem ícone extra sobre a mensagem.
    addCopyButtonsToCodeBlocks(bubble);
  }
  bubbleWrap.appendChild(bubble);

  // Mensagens do usuário podem ser editadas (edição reenvia e "ramifica"
  // a conversa, cortando tudo que veio depois — ver startEditingMessage).
  if (role === 'user') {
    const editBtn = document.createElement('button');
    editBtn.className = 'msg-edit-btn';
    editBtn.type = 'button';
    editBtn.title = 'Editar mensagem';
    editBtn.textContent = '✎';
    editBtn.addEventListener('click', () => startEditingMessage(msg, bubble));
    bubbleWrap.appendChild(editBtn);
  }

  msg.appendChild(avatar);
  msg.appendChild(bubbleWrap);
  msgCol.appendChild(msg);

  messagesEl.scrollTop = messagesEl.scrollHeight;

  return msg;
}

/** Remove o indicador de "digitando" se existir */
function removeTypingIndicator() {
  if (typingIndicator) {
    typingIndicator.remove();
    typingIndicator = null;
  }
}

/** Mostra "Hermes está pensando..." */
function showTypingIndicator() {
  removeTypingIndicator();
  const msg = document.createElement('div');
  msg.className = 'msg hermes';
  const avatar = document.createElement('div');
  avatar.className = 'avatar hermes';
  const bubbleWrap = document.createElement('div');
  const meta = document.createElement('div');
  meta.className = 'msg-meta';
  meta.textContent = 'Hermes';
  const bubble = document.createElement('div');
  bubble.className = 'bubble';
  bubble.textContent = '⏳ Pensando...';
  bubbleWrap.appendChild(meta);
  bubbleWrap.appendChild(bubble);
  msg.appendChild(avatar);
  msg.appendChild(bubbleWrap);
  msgCol.appendChild(msg);
  typingIndicator = msg;
  messagesEl.scrollTop = messagesEl.scrollHeight;
}

/** Mostra "Hermes está analisando profundamente..." com barra indeterminada */
function showAnalystIndicator() {
  removeTypingIndicator();
  const msg = document.createElement('div');
  msg.className = 'msg hermes';
  const avatar = document.createElement('div');
  avatar.className = 'avatar hermes';
  const bubbleWrap = document.createElement('div');
  const meta = document.createElement('div');
  meta.className = 'msg-meta';
  meta.textContent = 'Hermes';
  const bubble = document.createElement('div');
  bubble.className = 'bubble analyst-indicator';
  bubble.innerHTML = `
    <div class="analyst-indicator-label">🔬 Hermes está analisando profundamente…</div>
    <div class="analyst-progress-track"><div class="analyst-progress-bar"></div></div>
  `;
  bubbleWrap.appendChild(meta);
  bubbleWrap.appendChild(bubble);
  msg.appendChild(avatar);
  msg.appendChild(bubbleWrap);
  msgCol.appendChild(msg);
  typingIndicator = msg;
  messagesEl.scrollTop = messagesEl.scrollHeight;
}

/**
 * Cria (se ainda não existir) o bloco <details> de "Pensamento do Hermes"
 * imediatamente ANTES da bolha de resposta passada, e devolve o elemento
 * <pre> interno para atualização incremental do conteúdo.
 */
function createThinkingBlock(bubbleWrap) {
  let details = bubbleWrap.querySelector('.thinking-block');
  if (details) return details.querySelector('pre');

  details = document.createElement('details');
  details.className = 'thinking-block';
  details.open = true;

  const summary = document.createElement('summary');
  summary.textContent = 'Pensamento do Hermes';

  const pre = document.createElement('pre');

  details.appendChild(summary);
  details.appendChild(pre);

  const bubbleEl = bubbleWrap.querySelector('.bubble');
  bubbleWrap.insertBefore(details, bubbleEl);

  return pre;
}

/**
 * Cria (se ainda não existir) a bolha de mensagem do Hermes usada para
 * preencher incrementalmente durante o streaming, e devolve o elemento
 * <div class="bubble"> para atualização de texto.
 */
function createHermesBubble() {
  removeTypingIndicator();
  const emptyState = document.getElementById('empty-state');
  if (emptyState) emptyState.remove();

  const msg = document.createElement('div');
  msg.className = 'msg hermes';

  const avatar = document.createElement('div');
  avatar.className = 'avatar hermes';

  const bubbleWrap = document.createElement('div');
  const meta = document.createElement('div');
  meta.className = 'msg-meta';
  meta.textContent = 'Hermes';
  const bubble = document.createElement('div');
  bubble.className = 'bubble';
  bubbleWrap.appendChild(meta);
  bubbleWrap.appendChild(bubble);

  msg.appendChild(avatar);
  msg.appendChild(bubbleWrap);
  msgCol.appendChild(msg);
  messagesEl.scrollTop = messagesEl.scrollHeight;

  bubble._wrap = bubbleWrap;
  return bubble;
}

/**
 * Renderiza o card do plano (expansível) na conversa.
 * @param {Array} steps - lista de passos { index, description, tool, status }
 */
function renderPlanCard(steps) {
  // Remove card antigo se existir
  if (planCard) {
    planCard.remove();
    planCard = null;
  }

  const msg = document.createElement('div');
  msg.className = 'msg hermes';
  const avatar = document.createElement('div');
  avatar.className = 'avatar hermes';
  const bubbleWrap = document.createElement('div');
  const meta = document.createElement('div');
  meta.className = 'msg-meta';
  meta.textContent = 'Hermes — Plano de ação';
  const bubble = document.createElement('div');
  bubble.className = 'bubble plan-card';
  bubble.style.padding = '12px 16px';
  bubble.style.background = 'var(--bg-elevated)';
  bubble.style.borderRadius = '12px';
  bubble.style.border = '1px solid var(--line)';

  let html = `<div style="font-weight:600; margin-bottom:8px;">📋 Plano de ação</div><ul style="list-style:none; padding:0; margin:0;">`;
  steps.forEach((step, idx) => {
    const statusClass = step.status === 'done' ? 'done' : (step.status === 'in_progress' ? 'in-progress' : 'pending');
    const checked = step.status === 'done' ? 'checked' : '';
    html += `
      <li class="plan-step" data-index="${idx}" style="display:flex; align-items:center; gap:8px; padding:4px 0; border-bottom:1px solid var(--line);">
        <input type="checkbox" class="plan-step-checkbox" ${checked} disabled style="accent-color:var(--purple); width:16px; height:16px; flex-shrink:0;">
        <span class="plan-step-description" style="flex:1; font-size:13px; ${step.status === 'done' ? 'text-decoration:line-through; opacity:0.6;' : ''}">${escapeHtml(step.description)}</span>
        ${step.tool ? `<span style="font-size:10px; background:var(--bg-panel); padding:2px 8px; border-radius:12px; color:var(--text-low);">🔧 ${escapeHtml(step.tool)}</span>` : ''}
        ${step.status === 'in_progress' ? `<span style="font-size:11px; color:var(--purple);">⏳ executando...</span>` : ''}
        ${step.status === 'done' ? `<span style="font-size:11px; color:var(--text-low);">✅ concluído</span>` : ''}
        ${step.status === 'failed' ? `<span style="font-size:11px; color:#e35b5b;">❌ falhou</span>` : ''}
      </li>
    `;
  });
  html += `</ul>`;
  bubble.innerHTML = html;
  bubbleWrap.appendChild(bubble);
  msg.appendChild(avatar);
  msg.appendChild(bubbleWrap);
  msgCol.appendChild(msg);
  planCard = msg;
  messagesEl.scrollTop = messagesEl.scrollHeight;
}

/**
 * Atualiza o status de um passo no card do plano.
 * @param {number} index - índice do passo
 * @param {string} status - 'pending', 'in_progress', 'done', 'failed'
 * @param {string} output - saída opcional para exibir
 */
function updatePlanStep(index, status, output) {
  if (!planCard) return;
  const stepEl = planCard.querySelector(`.plan-step[data-index="${index}"]`);
  if (!stepEl) return;
  const checkbox = stepEl.querySelector('.plan-step-checkbox');
  const desc = stepEl.querySelector('.plan-step-description');
  const statusSpan = stepEl.querySelector('span:last-child');

  // Atualiza checkbox
  if (checkbox) {
    checkbox.checked = (status === 'done');
  }
  // Atualiza estilo da descrição
  if (desc) {
    desc.style.textDecoration = (status === 'done') ? 'line-through' : 'none';
    desc.style.opacity = (status === 'done') ? '0.6' : '1';
  }
  // Atualiza indicador de status
  if (statusSpan && !stepEl.querySelector('.plan-step-checkbox')) {
    // Se houver um span de status, atualiza
    const oldSpan = stepEl.querySelector('span:last-child');
    if (oldSpan) {
      let text = '';
      if (status === 'in_progress') text = '⏳ executando...';
      else if (status === 'done') text = '✅ concluído';
      else if (status === 'failed') text = '❌ falhou';
      else text = '';
      oldSpan.textContent = text;
      oldSpan.style.color = status === 'failed' ? '#e35b5b' : 'var(--text-low)';
    }
  }
  // Se houver saída, mostra como log
  if (output && status === 'done') {
    console.log(`Passo ${index} saída:`, output);
  }
}

function escapeHtml(str) {
  const div = document.createElement('div');
  div.textContent = str || '';
  return div.innerHTML;
}

/**
 * Converte markdown em HTML seguro usando marked.js + DOMPurify (carregados
 * localmente em js/vendor/). Caso as libs não tenham carregado por algum
 * motivo (arquivo ausente, erro de parse, etc.), cai de volta para texto
 * puro escapado — nunca quebra a renderização da conversa.
 * @param {string} text
 * @returns {string} HTML pronto para innerHTML
 */
/**
 * Copia texto para a área de transferência, com fallback para navegadores/
 * contextos sem suporte a navigator.clipboard (ex.: contexto não-seguro).
 * @param {string} text
 * @returns {Promise<boolean>} sucesso
 */
async function copyTextToClipboard(text) {
  try {
    if (navigator.clipboard && window.isSecureContext) {
      await navigator.clipboard.writeText(text);
      return true;
    }
  } catch (err) {
    console.error('[Hermes] navigator.clipboard falhou, tentando fallback:', err);
  }
  try {
    const textarea = document.createElement('textarea');
    textarea.value = text;
    textarea.style.position = 'fixed';
    textarea.style.opacity = '0';
    document.body.appendChild(textarea);
    textarea.focus();
    textarea.select();
    const ok = document.execCommand('copy');
    textarea.remove();
    return ok;
  } catch (err) {
    console.error('[Hermes] Falha ao copiar texto:', err);
    return false;
  }
}

/**
 * Percorre os blocos de código (<pre><code>) já renderizados dentro de uma
 * bolha e adiciona um botão de copiar em cada um, caso ainda não tenha.
 * Chamada sempre que o HTML da bolha é (re)gerado a partir de markdown,
 * inclusive durante o streaming (re-render incremental).
 * @param {HTMLElement} bubble
 */
function addCopyButtonsToCodeBlocks(bubble) {
  if (!bubble) return;
  bubble.querySelectorAll('pre').forEach((pre) => {
    if (pre.querySelector(':scope > .code-copy-btn')) return; // já tem botão
    pre.classList.add('has-copy-btn');
    const btn = document.createElement('button');
    btn.type = 'button';
    btn.className = 'code-copy-btn';
    btn.title = 'Copiar código';
    btn.textContent = 'Copiar';
    btn.addEventListener('click', async (e) => {
      e.stopPropagation();
      const codeEl = pre.querySelector('code') || pre;
      const ok = await copyTextToClipboard(codeEl.textContent || '');
      btn.textContent = ok ? 'Copiado!' : 'Falhou';
      setTimeout(() => { btn.textContent = 'Copiar'; }, 1500);
    });
    pre.appendChild(btn);
  });
}

function renderMarkdown(text) {
  const raw = text || '';
  try {
    if (typeof window.marked === 'undefined' || typeof window.DOMPurify === 'undefined') {
      throw new Error('marked/DOMPurify indisponíveis');
    }
    const dirtyHtml = window.marked.parse(raw, { breaks: true });
    return window.DOMPurify.sanitize(dirtyHtml);
  } catch (err) {
    // Fallback: texto puro escapado (sem formatação, mas nunca quebra)
    return escapeHtml(raw).replace(/\n/g, '<br>');
  }
}

/**
 * Conecta em POST /chat/stream e processa os eventos SSE.
 * Agora suporta eventos "plan", "step_start", "step_progress", "step_done", "step_failed".
 */
// Configuração do reprocessamento de markdown durante o streaming: reparsear
// a cada token seria caro (marked+DOMPurify a cada char) e ainda instável,
// pois tags markdown abertas no meio (ex: "**negri" sem fechar) podem gerar
// HTML inconsistente por 1 frame. Por isso reprocessamos a cada N tokens OU
// após um pequeno debounce de inatividade — o que vier primeiro.
const MARKDOWN_RENDER_EVERY_N_TOKENS = 8;
const MARKDOWN_RENDER_DEBOUNCE_MS = 120;

/**
 * Cria um "agendador" de re-render de markdown para uma bolha específica.
 * Chame `.onToken()` a cada token recebido e `.flush()` ao final do stream
 * para garantir que o conteúdo final sempre reflita o markdown completo.
 */
function createMarkdownRenderScheduler(getBubble, getText) {
  let tokensSinceRender = 0;
  let debounceTimer = null;

  function render() {
    const bubble = getBubble();
    if (!bubble) return;
    bubble.innerHTML = renderMarkdown(getText());
    // innerHTML foi totalmente substituído: os botões de copiar dos blocos
    // de código precisam ser reinseridos a cada re-render.
    addCopyButtonsToCodeBlocks(bubble);
    messagesEl.scrollTop = messagesEl.scrollHeight;
  }

  function clearDebounce() {
    if (debounceTimer) {
      clearTimeout(debounceTimer);
      debounceTimer = null;
    }
  }

  return {
    onToken() {
      tokensSinceRender += 1;
      clearDebounce();
      if (tokensSinceRender >= MARKDOWN_RENDER_EVERY_N_TOKENS) {
        tokensSinceRender = 0;
        render();
      } else {
        debounceTimer = setTimeout(() => {
          tokensSinceRender = 0;
          render();
        }, MARKDOWN_RENDER_DEBOUNCE_MS);
      }
    },
    flush() {
      clearDebounce();
      tokensSinceRender = 0;
      render();
    },
  };
}

async function runStreamingChat(chatPayload) {
  let hermesBubble = null;
  let thinkingPre = null;
  let thinkingText = '';
  let hermesText = '';
  const mdScheduler = createMarkdownRenderScheduler(() => hermesBubble, () => hermesText);

  let streamRes;
  try {
    streamRes = await fetch(`${window.HermesState.API_BASE}/chat/stream`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(chatPayload),
    });
  } catch (networkErr) {
    return null;
  }

  if (!streamRes.ok || !streamRes.body) {
    return null;
  }

  const reader = streamRes.body.getReader();
  const decoder = new TextDecoder('utf-8');
  let sseBuffer = '';

  while (true) {
    const { value, done } = await reader.read();
    if (done) break;
    sseBuffer += decoder.decode(value, { stream: true });

    let sepIndex;
    while ((sepIndex = sseBuffer.indexOf('\n\n')) !== -1) {
      const rawEvent = sseBuffer.slice(0, sepIndex);
      sseBuffer = sseBuffer.slice(sepIndex + 2);

      let eventType = 'message';
      let dataStr = '';
      for (const line of rawEvent.split('\n')) {
        if (line.startsWith('event:')) eventType = line.slice(6).trim();
        else if (line.startsWith('data:')) dataStr += line.slice(5).trim();
      }
      if (!dataStr) continue;

      let data;
      try {
        data = JSON.parse(dataStr);
      } catch (e) {
        continue;
      }

      // --- Eventos do plano multi‑step ---
      if (eventType === 'plan' && data.steps) {
        // Renderiza o card do plano
        renderPlanCard(data.steps);
        continue;
      }
      if (eventType === 'step_start' && data.index !== undefined) {
        // Atualiza passo para "in_progress"
        updatePlanStep(data.index, 'in_progress', null);
        continue;
      }
      if (eventType === 'step_progress' && data.index !== undefined) {
        if (data.status === 'done') {
          updatePlanStep(data.index, 'done', data.output || '');
          // Se houver token, adiciona à mensagem final
          if (data.token) {
            if (!hermesBubble) hermesBubble = createHermesBubble();
            hermesText += data.token;
            mdScheduler.onToken();
          }
        } else if (data.status === 'in_progress' && data.token) {
          // Atualiza progresso com tokens (pode ser usado para streaming dentro do passo)
        }
        continue;
      }
      if (eventType === 'step_failed' && data.index !== undefined) {
        updatePlanStep(data.index, 'failed', data.error || '');
        continue;
      }

      // --- Eventos existentes ---
      if (eventType === 'thinking' && typeof data.token === 'string') {
        if (!hermesBubble) hermesBubble = createHermesBubble();
        if (!thinkingPre) thinkingPre = createThinkingBlock(hermesBubble._wrap);
        thinkingText += (thinkingText ? '\n' : '') + data.token;
        thinkingPre.textContent = thinkingText;
        messagesEl.scrollTop = messagesEl.scrollHeight;
      } else if (eventType === 'token' && typeof data.token === 'string') {
        if (!hermesBubble) hermesBubble = createHermesBubble();
        hermesText += data.token;
        mdScheduler.onToken();
      } else if (eventType === 'system' && typeof data.message === 'string') {
        window.HermesNotifications.notify('Hermes AI', data.message);
      } else if (eventType === 'error') {
        if (!hermesBubble) hermesBubble = createHermesBubble();
        hermesText += `\n❌ ${data.error || 'Falha na comunicação'}`;
        mdScheduler.flush();
      }
      // evento "done" apenas sinaliza o fim
    }
  }

  if (!hermesBubble) {
    return null;
  }

  // Garante que o markdown final (com o texto completo) seja renderizado,
  // independentemente de estarmos no meio de um debounce/contagem de tokens.
  mdScheduler.flush();

  return hermesText;
}

/**
 * Executa a chamada ao agente (streaming com fallback) para um turno de
 * chat já com o chat_id e a mensagem do usuário persistidos. Compartilhada
 * entre o envio normal (sendMessageToBackend) e o reenvio após edição de
 * uma mensagem (resendEditedMessage).
 */
async function runChatTurnAndRenderReply(chatId, userText, mode, projectId, attachmentIds) {
  // O domínio (firmware/android/etc.) não é mais escolhido manualmente pelo
  // usuário: o backend detecta automaticamente o agente ideal a partir da
  // mensagem (ver HybridAgentRouter em orchestrator/router.py).
  const domain = null;

  if (mode === 'analyst') {
    showAnalystIndicator();
  } else {
    showTypingIndicator();
  }
  if (window.HermesSphere) window.HermesSphere.setGenerating(true);

  const supportsStreaming = typeof ReadableStream !== 'undefined' && !!window.fetch;

  try {
    const chatPayload = {
      message: userText,
      mode: mode || null,
      domain: domain || null,
      project_id: projectId || null,
      chat_id: chatId,
      // Pensamento visível: respeita a preferência salva em Configurações,
      // e continua sempre ativado no modo analista (que já narra etapas
      // do processo de decomposição/verificação).
      show_thinking: cachedShowThinkingEnabled || mode === 'analyst',
      web_search: !!window.HermesState.webSearchEnabled,
      // IDs dos arquivos anexados (upload por clique ou drag-and-drop) que
      // devem ser incluídos no contexto desta mensagem pelo backend.
      attachment_ids: (attachmentIds && attachmentIds.length) ? attachmentIds : null,
    };

    let hermesReply = null;

    // 1. Tenta streaming primeiro
    if (supportsStreaming) {
      hermesReply = await runStreamingChat(chatPayload);
    }

    // 2. Fallback: endpoint tradicional (sem streaming), se o stream não
    // produziu nenhum token (navegador sem suporte, erro de conexão, etc.)
    if (hermesReply === null) {
      const chatRes = await fetch(`${window.HermesState.API_BASE}/chat/`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(chatPayload),
      });
      if (!chatRes.ok) {
        const errData = await chatRes.json().catch(() => ({}));
        throw new Error(errData.detail || 'Erro ao processar mensagem');
      }
      const data = await chatRes.json();
      hermesReply = data.reply;
      removeTypingIndicator();
      addMessage('hermes', hermesReply);
    }

    // 3. Remover indicador de digitação (caso ainda esteja visível)
    removeTypingIndicator();

    // 4. Notificar (se o usuário tiver ativado notificações push)
    if (window.HermesNotifications) {
      window.HermesNotifications.notify('Hermes', 'Sua resposta está pronta.');
    }

    // 5. A resposta do Hermes já foi salva pelo backend (tanto na rota
    // tradicional quanto na rota de streaming), não precisamos salvar de novo.

  } catch (error) {
    console.error('[Hermes] Erro no envio:', error);
    removeTypingIndicator();
    // Exibe erro como mensagem do Hermes (sem alert)
    addMessage('hermes', `❌ Ocorreu um erro: ${error.message || 'Falha na comunicação'}. Tente novamente.`);
  } finally {
    if (window.HermesSphere) window.HermesSphere.setGenerating(false);
  }
}

/**
 * Envia a mensagem para o backend e processa a resposta.
 * Tenta primeiro o streaming em tempo real (POST /chat/stream); se o
 * navegador não suportar ReadableStream, ou a conexão falhar antes de
 * qualquer token chegar, cai automaticamente para o endpoint tradicional
 * (POST /chat/), que continua funcionando como antes.
 * @param {string} userText
 * @param {string|null} mode
 * @param {string|null} projectId
 * @param {HTMLElement} [userMsgEl] - elemento .msg otimista já renderizado,
 *        recebe o id real assim que a mensagem é persistida (habilita edição).
 */
async function sendMessageToBackend(userText, mode, projectId, userMsgEl) {
  try {
    // 1. Garantir que existe um chat atual (criar se necessário)
    let chatId = window.HermesState.currentChatId;
    if (!chatId) {
      // Título derivado da primeira mensagem do usuário (em vez de ficar
      // travado em "Nova conversa"). Trunca em ~48 chars para não estourar
      // a sidebar.
      const trimmed = userText.trim();
      const autoTitle = trimmed.slice(0, 48) + (trimmed.length > 48 ? '…' : '');
      const title = autoTitle || (projectId ? 'Nova conversa (projeto)' : 'Nova conversa');
      const createRes = await fetch(`${window.HermesState.API_BASE}/chats/`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ title, project_id: projectId || null }),
      });
      if (!createRes.ok) throw new Error('Falha ao criar chat');
      const chat = await createRes.json();
      chatId = chat.id;
      window.HermesState.currentChatId = chatId;
      // Atualiza sidebar
      if (window.HermesChats) window.HermesChats.renderSidebar();
    }

    // 2. IDs dos arquivos anexados nesta mensagem (upload/drag-and-drop)
    const attachmentIds = attachedFiles.map((f) => f.server_id).filter(Boolean);

    // 3. Salvar a mensagem do usuário no backend
    const msgRes = await fetch(`${window.HermesState.API_BASE}/chats/${chatId}/messages`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ role: 'user', content: userText }),
    });
    if (!msgRes.ok) throw new Error('Falha ao salvar mensagem do usuário');
    const savedMsg = await msgRes.json();
    // Marca a bolha otimista com o id real, habilitando o botão de editar.
    if (userMsgEl) userMsgEl.dataset.messageId = savedMsg.id;

    // 4. Chamar o agente e renderizar a resposta
    await runChatTurnAndRenderReply(chatId, userText, mode, projectId, attachmentIds);

  } catch (error) {
    console.error('[Hermes] Erro no envio:', error);
    removeTypingIndicator();
    addMessage('hermes', `❌ Ocorreu um erro: ${error.message || 'Falha na comunicação'}. Tente novamente.`);
  } finally {
    if (window.HermesSphere) window.HermesSphere.setGenerating(false);
  }
}

/**
 * Reenvia uma mensagem já editada (o conteúdo já foi atualizado via PATCH
 * e as mensagens seguintes já foram removidas/ramificadas no backend).
 * Não persiste uma nova mensagem de usuário — só roda o agente de novo.
 * Anexos não são reaplicados na edição (limitação atual: a mensagem
 * editada não reaproveita os attachment_ids da mensagem original).
 */
async function resendEditedMessage(chatId, userText, mode, projectId) {
  await runChatTurnAndRenderReply(chatId, userText, mode, projectId, []);
}

/**
 * Transforma a bolha de uma mensagem do usuário em um campo editável.
 * Ao salvar: faz PATCH /chats/{chatId}/messages/{messageId}, remove da tela
 * (ramifica) tudo que veio depois dessa mensagem, e reenvia para o agente
 * gerar uma nova resposta a partir do texto editado.
 */
function startEditingMessage(msgEl, bubbleEl) {
  const chatId = window.HermesState.currentChatId;
  const messageId = msgEl.dataset.messageId;
  if (!chatId || !messageId) {
    showToast('Aguarde a mensagem terminar de enviar antes de editar.');
    return;
  }
  if (msgEl.classList.contains('editing')) return; // já está em edição
  msgEl.classList.add('editing');

  const originalText = bubbleEl.textContent;
  bubbleEl.innerHTML = '';

  const textarea = document.createElement('textarea');
  textarea.className = 'edit-msg-textarea';
  textarea.value = originalText;
  bubbleEl.appendChild(textarea);

  const actions = document.createElement('div');
  actions.className = 'edit-msg-actions';
  const saveBtn = document.createElement('button');
  saveBtn.type = 'button';
  saveBtn.className = 'edit-msg-save-btn';
  saveBtn.textContent = 'Salvar e reenviar';
  const cancelBtn = document.createElement('button');
  cancelBtn.type = 'button';
  cancelBtn.className = 'edit-msg-cancel-btn';
  cancelBtn.textContent = 'Cancelar';
  actions.appendChild(saveBtn);
  actions.appendChild(cancelBtn);
  bubbleEl.appendChild(actions);

  textarea.focus();
  textarea.setSelectionRange(textarea.value.length, textarea.value.length);

  function finishEditing(finalText) {
    msgEl.classList.remove('editing');
    bubbleEl.innerHTML = '';
    bubbleEl.textContent = finalText;
  }

  cancelBtn.addEventListener('click', () => finishEditing(originalText));

  saveBtn.addEventListener('click', async () => {
    const newText = textarea.value.trim();
    if (!newText) return;
    saveBtn.disabled = true;
    cancelBtn.disabled = true;
    try {
      const res = await fetch(`${window.HermesState.API_BASE}/chats/${chatId}/messages/${messageId}`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ content: newText }),
      });
      if (!res.ok) {
        const errData = await res.json().catch(() => ({}));
        throw new Error(errData.detail || 'Falha ao editar mensagem');
      }

      // Ramificação: remove da tela tudo que veio depois desta mensagem
      // (o backend já apagou essas mensagens do banco).
      let sibling = msgEl.nextElementSibling;
      while (sibling) {
        const toRemove = sibling;
        sibling = sibling.nextElementSibling;
        toRemove.remove();
      }
      if (planCard) {
        planCard.remove();
        planCard = null;
      }
      removeTypingIndicator();

      finishEditing(newText);

      // Determina o modo ativo atual (mesma lógica do sendMessage) e reenvia
      let mode = null;
      const codeChip = document.getElementById('mode-code');
      const engineerChip = document.getElementById('mode-engineer');
      const analystChip = document.getElementById('mode-analyst');
      if (codeChip.classList.contains('active')) mode = 'code';
      else if (engineerChip.classList.contains('active')) mode = 'engineer';
      else if (analystChip.classList.contains('active')) mode = 'analyst';
      const projectId = window.HermesState.activeProjectId || null;

      await resendEditedMessage(chatId, newText, mode, projectId);
    } catch (err) {
      console.error('[Hermes] Erro ao editar mensagem:', err);
      showToast('Não foi possível editar a mensagem.');
      finishEditing(originalText);
    } finally {
      saveBtn.disabled = false;
      cancelBtn.disabled = false;
    }
  });
}

function sendMessage() {
  const text = msgInput.value.trim();
  if (!text) return;

  // Determinar modo ativo
  let mode = null;
  const codeChip = document.getElementById('mode-code');
  const engineerChip = document.getElementById('mode-engineer');
  const analystChip = document.getElementById('mode-analyst');
  if (codeChip.classList.contains('active')) mode = 'code';
  else if (engineerChip.classList.contains('active')) mode = 'engineer';
  else if (analystChip.classList.contains('active')) mode = 'analyst';

  const projectId = window.HermesState.activeProjectId || null;

  // Adiciona a mensagem do usuário imediatamente (otimista)
  const userMsgEl = addMessage('user', text);
  msgInput.value = '';
  msgInput.style.height = 'auto';

  // Envia para o backend
  sendMessageToBackend(text, mode, projectId, userMsgEl);
}

// Event listeners
sendBtn.addEventListener('click', sendMessage);
msgInput.addEventListener('keydown', (e) => {
  if (e.key === 'Enter' && !e.shiftKey) {
    e.preventDefault();
    sendMessage();
  }
});

// ============ ANEXAR ARQUIVO ============
const fileInput = document.createElement('input');
fileInput.type = 'file';
fileInput.multiple = true;
fileInput.style.display = 'none';
document.body.appendChild(fileInput);

const attachBtn = document.querySelector('.input-icon-btn[title="Anexar"]');
const inputShell = document.getElementById('input-shell');
const textRow = document.getElementById('text-row');

// Container para preview dos arquivos
const filePreviewContainer = document.createElement('div');
filePreviewContainer.id = 'file-preview-container';
filePreviewContainer.style.cssText = 'display:flex; flex-wrap:wrap; gap:6px; margin-bottom:8px;';
inputShell.insertBefore(filePreviewContainer, textRow);

let attachedFiles = []; // array de { name, type, size, file, server_id }

function getFileIcon(file) {
  const type = file.type || '';
  if (type.startsWith('image/')) return '🖼️';
  if (type.startsWith('video/')) return '🎬';
  if (type.startsWith('audio/')) return '🎵';
  if (type.includes('pdf')) return '📄';
  if (type.includes('text')) return '📝';
  return '📎';
}

function renderFilePreviews() {
  filePreviewContainer.innerHTML = '';
  attachedFiles.forEach((f, idx) => {
    const chip = document.createElement('div');
    chip.className = 'mode-chip';
    chip.style.cssText = 'padding:4px 10px; gap:4px;';
    chip.innerHTML = `
      <span>${getFileIcon(f)}</span>
      <span style="max-width:120px; overflow:hidden; text-overflow:ellipsis; white-space:nowrap;">${f.name}</span>
      <span style="font-size:10px; color:var(--text-low);">${(f.size / 1024).toFixed(1)} KB</span>
      <button class="file-remove-btn" data-index="${idx}" style="background:none; border:none; color:var(--text-low); cursor:pointer;">✕</button>
    `;
    filePreviewContainer.appendChild(chip);
  });
  // Anexar eventos de remoção
  filePreviewContainer.querySelectorAll('.file-remove-btn').forEach(btn => {
    btn.addEventListener('click', (e) => {
      const idx = parseInt(e.target.dataset.index, 10);
      attachedFiles.splice(idx, 1);
      renderFilePreviews();
    });
  });
}

attachBtn.addEventListener('click', () => {
  fileInput.click();
});

/** Garante que existe um chat atual, criando um novo se necessário. */
async function ensureCurrentChatId() {
  let chatId = window.HermesState.currentChatId;
  if (chatId) return chatId;

  const projectId = window.HermesState.activeProjectId || null;
  const title = projectId ? 'Nova conversa (projeto)' : 'Nova conversa';
  const res = await fetch(`${window.HermesState.API_BASE}/chats/`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ title, project_id: projectId }),
  });
  if (!res.ok) throw new Error('Falha ao criar chat');
  const chat = await res.json();
  chatId = chat.id;
  window.HermesState.currentChatId = chatId;
  if (window.HermesChats) window.HermesChats.renderSidebar();
  return chatId;
}

/**
 * Faz upload de uma lista de arquivos (FileList ou array) para o chat atual
 * e adiciona cada um à lista de anexos pendentes (preview + attachment_ids
 * enviados na próxima mensagem). Usada tanto pelo input de clique quanto
 * pelo drag-and-drop.
 */
async function uploadFilesToChat(fileList) {
  const files = Array.from(fileList || []);
  if (files.length === 0) return;

  let chatId;
  try {
    chatId = await ensureCurrentChatId();
  } catch (err) {
    console.error('[Hermes] Erro ao criar chat para upload:', err);
    showToast('Não foi possível iniciar o upload.');
    return;
  }

  for (const file of files) {
    try {
      const formData = new FormData();
      formData.append('file', file);
      const res = await fetch(`${window.HermesState.API_BASE}/files/upload?chat_id=${chatId}`, {
        method: 'POST',
        body: formData,
      });
      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        console.error('Erro no upload:', err.detail || 'Falha no upload');
        showToast(`Falha ao enviar "${file.name}"`);
        continue;
      }
      const data = await res.json();
      // Adicionar à lista local de anexos para preview
      attachedFiles.push({
        name: file.name,
        size: file.size,
        type: file.type,
        file: file,
        server_id: data.id,
      });
    } catch (err) {
      console.error('Erro no upload:', err);
      showToast(`Falha ao enviar "${file.name}"`);
    }
  }
  renderFilePreviews();
}

fileInput.addEventListener('change', () => {
  uploadFilesToChat(fileInput.files);
  fileInput.value = ''; // limpa para permitir re-seleção
});

// ============ DRAG AND DROP ============
// Cobre toda a área do chat (mensagens + input). Usa um contador de
// dragenter/dragleave porque esses eventos disparam também para elementos
// filhos (senão a classe de overlay pisca ao arrastar sobre uma mensagem).
const dropZone = document.getElementById('view-chat');
let dragCounter = 0;

if (dropZone) {
  dropZone.addEventListener('dragenter', (e) => {
    e.preventDefault();
    if (!e.dataTransfer || !e.dataTransfer.types || !e.dataTransfer.types.includes('Files')) return;
    dragCounter++;
    dropZone.classList.add('hermes-drag-over');
  });
  dropZone.addEventListener('dragover', (e) => {
    // preventDefault é obrigatório aqui, senão o navegador nunca dispara "drop"
    e.preventDefault();
  });
  dropZone.addEventListener('dragleave', (e) => {
    e.preventDefault();
    dragCounter = Math.max(0, dragCounter - 1);
    if (dragCounter === 0) dropZone.classList.remove('hermes-drag-over');
  });
  dropZone.addEventListener('drop', (e) => {
    e.preventDefault();
    dragCounter = 0;
    dropZone.classList.remove('hermes-drag-over');
    if (e.dataTransfer && e.dataTransfer.files && e.dataTransfer.files.length) {
      uploadFilesToChat(e.dataTransfer.files);
    }
  });
}

// Limpar preview ao enviar mensagem (após envio bem-sucedido)
// Sobrescrevemos sendMessageToBackend para limpar preview no sucesso
const originalSendToBackend = sendMessageToBackend;
sendMessageToBackend = async function(userText, mode, projectId, userMsgEl) {
  try {
    await originalSendToBackend(userText, mode, projectId, userMsgEl);
    // Se chegou aqui, sucesso: limpar preview
    attachedFiles = [];
    renderFilePreviews();
  } catch (err) {
    // erro já tratado no original
    // Não limpamos preview em caso de erro
  }
};

// Microfone: toast simples e não-bloqueante (substitui alert())
let hermesToastStylesInjected = false;
function ensureToastStyles() {
  if (hermesToastStylesInjected) return;
  const style = document.createElement('style');
  style.textContent = `
    .hermes-toast {
      position: fixed;
      z-index: 9999;
      max-width: 260px;
      background: var(--bg-elevated);
      color: var(--text-hi);
      border: 1px solid var(--line);
      border-radius: 10px;
      padding: 10px 14px;
      font-size: 13px;
      font-family: var(--font-body);
      box-shadow: 0 8px 24px rgba(0,0,0,0.25);
      opacity: 0;
      transform: translateY(6px);
      transition: opacity 0.2s ease, transform 0.2s ease;
      pointer-events: none;
    }
    .hermes-toast.hermes-toast-show {
      opacity: 1;
      transform: translateY(0);
    }
  `;
  document.head.appendChild(style);
  hermesToastStylesInjected = true;
}

/**
 * Exibe um toast simples e temporário próximo a um elemento âncora
 * (ou no canto inferior direito da tela, se nenhum for passado).
 * @param {string} text
 * @param {HTMLElement} [anchorEl]
 */
function showToast(text, anchorEl) {
  ensureToastStyles();

  const toast = document.createElement('div');
  toast.className = 'hermes-toast';
  toast.textContent = text;
  document.body.appendChild(toast);

  if (anchorEl) {
    const rect = anchorEl.getBoundingClientRect();
    toast.style.left = Math.max(8, rect.left) + 'px';
    toast.style.top = Math.max(8, rect.top - 44) + 'px';
  } else {
    toast.style.right = '20px';
    toast.style.bottom = '20px';
  }

  // Força o navegador a computar o estado inicial antes de animar
  requestAnimationFrame(() => toast.classList.add('hermes-toast-show'));

  setTimeout(() => {
    toast.classList.remove('hermes-toast-show');
    setTimeout(() => toast.remove(), 250);
  }, 2500);
}

const micBtn = document.querySelector('.input-icon-btn[title="Microfone"]');
micBtn.addEventListener('click', () => {
  showToast('Ditado por voz ainda não disponível', micBtn);
});

// Estilos para edição inline de mensagens e overlay de drag-and-drop
let hermesChatExtraStylesInjected = false;
function ensureChatExtraStyles() {
  if (hermesChatExtraStylesInjected) return;
  const style = document.createElement('style');
  style.textContent = `
    .msg.user .msg-edit-btn {
      opacity: 0;
      transition: opacity 0.15s ease;
      background: none;
      border: none;
      color: var(--text-low);
      cursor: pointer;
      font-size: 13px;
      padding: 2px 4px;
      align-self: flex-end;
    }
    .msg.user:hover .msg-edit-btn,
    .msg.user.editing .msg-edit-btn {
      opacity: 1;
    }
    .msg.user .msg-edit-btn:hover {
      color: var(--text-hi);
    }
    .edit-msg-textarea {
      width: 100%;
      min-height: 60px;
      resize: vertical;
      background: var(--bg-panel);
      color: var(--text-hi);
      border: 1px solid var(--line);
      border-radius: 8px;
      padding: 8px 10px;
      font-family: var(--font-body);
      font-size: 14px;
      box-sizing: border-box;
    }
    .edit-msg-actions {
      display: flex;
      gap: 8px;
      margin-top: 6px;
      justify-content: flex-end;
    }
    .edit-msg-save-btn, .edit-msg-cancel-btn {
      font-size: 12px;
      padding: 5px 12px;
      border-radius: 8px;
      border: 1px solid var(--line);
      cursor: pointer;
      background: none;
    }
    .edit-msg-save-btn {
      background: var(--purple, #7c5cff);
      color: #fff;
      border-color: transparent;
    }
    .edit-msg-cancel-btn {
      color: var(--text-low);
    }
    #view-chat.hermes-drag-over {
      position: relative;
      outline: 2px dashed var(--purple, #7c5cff);
      outline-offset: -8px;
      background: rgba(124, 92, 255, 0.05);
    }
    #view-chat.hermes-drag-over::after {
      content: 'Solte os arquivos para anexar à conversa';
      position: absolute;
      left: 50%;
      top: 50%;
      transform: translate(-50%, -50%);
      background: var(--bg-elevated);
      color: var(--text-hi);
      padding: 10px 18px;
      border-radius: 10px;
      border: 1px solid var(--line);
      font-size: 13px;
      pointer-events: none;
      z-index: 20;
    }
  `;
  document.head.appendChild(style);
  hermesChatExtraStylesInjected = true;
}
ensureChatExtraStyles();

// Expor sendMessage globalmente para uso em outros módulos (ex: projetos)
window.sendMessage = sendMessage;
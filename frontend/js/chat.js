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

/**
 * Adiciona uma mensagem na conversa.
 * @param {'user'|'hermes'} role
 * @param {string} text
 */
function addMessage(role, text) {
  const emptyState = document.getElementById('empty-state');
  if (emptyState) emptyState.remove();

  const msg = document.createElement('div');
  msg.className = 'msg ' + role;

  const avatar = document.createElement('div');
  avatar.className = 'avatar ' + (role === 'user' ? 'user' : 'hermes');
  if (role === 'user') avatar.textContent = 'FS';

  const bubbleWrap = document.createElement('div');
  if (role !== 'user') {
    const meta = document.createElement('div');
    meta.className = 'msg-meta';
    meta.textContent = 'Hermes';
    bubbleWrap.appendChild(meta);
  }

  const bubble = document.createElement('div');
  bubble.className = 'bubble';
  bubble.textContent = text;
  bubbleWrap.appendChild(bubble);

  msg.appendChild(avatar);
  msg.appendChild(bubbleWrap);
  msgCol.appendChild(msg);

  messagesEl.scrollTop = messagesEl.scrollHeight;
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
 * Conecta em POST /chat/stream e processa os eventos SSE.
 * Agora suporta eventos "plan", "step_start", "step_progress", "step_done", "step_failed".
 */
async function runStreamingChat(chatPayload) {
  let hermesBubble = null;
  let thinkingPre = null;
  let thinkingText = '';
  let hermesText = '';

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
            hermesBubble.textContent = hermesText;
            messagesEl.scrollTop = messagesEl.scrollHeight;
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
        hermesBubble.textContent = hermesText;
        messagesEl.scrollTop = messagesEl.scrollHeight;
      } else if (eventType === 'system' && typeof data.message === 'string') {
        window.HermesNotifications.notify('Hermes AI', data.message);
      } else if (eventType === 'error') {
        if (!hermesBubble) hermesBubble = createHermesBubble();
        hermesText += `\n❌ ${data.error || 'Falha na comunicação'}`;
        hermesBubble.textContent = hermesText;
      }
      // evento "done" apenas sinaliza o fim
    }
  }

  if (!hermesBubble) {
    return null;
  }

  return hermesText;
}

/**
 * Envia a mensagem para o backend e processa a resposta.
 * Tenta primeiro o streaming em tempo real (POST /chat/stream); se o
 * navegador não suportar ReadableStream, ou a conexão falhar antes de
 * qualquer token chegar, cai automaticamente para o endpoint tradicional
 * (POST /chat/), que continua funcionando como antes.
 */
async function sendMessageToBackend(userText, mode, projectId) {
  // Obtém o domínio ativo (se disponível)
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

    // 2. Salvar a mensagem do usuário no backend
    const msgRes = await fetch(`${window.HermesState.API_BASE}/chats/${chatId}/messages`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ role: 'user', content: userText }),
    });
    if (!msgRes.ok) throw new Error('Falha ao salvar mensagem do usuário');

    // 3. Chamar o endpoint de chat (que executa o agente)
    const chatPayload = {
      message: userText,
      mode: mode || null,
      domain: domain || null,           // <-- NOVO CAMPO
      project_id: projectId || null,
      chat_id: chatId,
      // Pensamento visível: ativado apenas no modo analista
      show_thinking: mode === 'analyst',
      web_search: !!window.HermesState.webSearchEnabled,
    };

    let hermesReply = null;

    // 3a. Tenta streaming primeiro
    if (supportsStreaming) {
      hermesReply = await runStreamingChat(chatPayload);
    }

    // 3b. Fallback: endpoint tradicional (sem streaming), se o stream não
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

    // 4. Remover indicador de digitação (caso ainda esteja visível)
    removeTypingIndicator();

    // 5. Notificar (se o usuário tiver ativado notificações push)
    if (window.HermesNotifications) {
      window.HermesNotifications.notify('Hermes', 'Sua resposta está pronta.');
    }

    // 6. A resposta do Hermes já foi salva pelo backend (tanto na rota
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
  addMessage('user', text);
  msgInput.value = '';
  msgInput.style.height = 'auto';

  // Envia para o backend
  sendMessageToBackend(text, mode, projectId);
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

fileInput.addEventListener('change', async () => {
  const files = Array.from(fileInput.files);
  if (files.length === 0) return;

  // Garantir que existe um chat (criar se necessário)
  let chatId = window.HermesState.currentChatId;
  if (!chatId) {
    const projectId = window.HermesState.activeProjectId || null;
    const title = projectId ? 'Nova conversa (projeto)' : 'Nova conversa';
    try {
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
    } catch (err) {
      console.error('[Hermes] Erro ao criar chat para upload:', err);
      return;
    }
  }

  // Upload de cada arquivo
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
    }
  }
  renderFilePreviews();
  fileInput.value = ''; // limpa para permitir re-seleção
});

// Limpar preview ao enviar mensagem (após envio bem-sucedido)
// Sobrescrevemos sendMessageToBackend para limpar preview no sucesso
const originalSendToBackend = sendMessageToBackend;
sendMessageToBackend = async function(userText, mode, projectId) {
  try {
    await originalSendToBackend(userText, mode, projectId);
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

// Expor sendMessage globalmente para uso em outros módulos (ex: projetos)
window.sendMessage = sendMessage;

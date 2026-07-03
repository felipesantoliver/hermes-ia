/* ===================== LÓGICA DO CHAT ===================== */
/* Responsabilidade: gerenciar envio de mensagens, integração com backend,
   indicador de "digitando", upload de arquivos e preview. */

const msgCol = document.getElementById('msg-col');
const messagesEl = document.getElementById('messages');
const input = document.getElementById('msg-input');
const sendBtn = document.getElementById('send-btn');

let typingIndicator = null;

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

/** Mostra "Hermes está analisando profundamente..." com barra indeterminada,
 * usado quando o modo analista está ativo. Reaproveita o mesmo slot do
 * indicador de digitação (typingIndicator), pois é removido do mesmo jeito. */
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

  // Insere antes da bolha de resposta (bubbleWrap contém meta + bubble).
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

  bubble._wrap = bubbleWrap; // usado por createThinkingBlock para inserir o bloco antes da bolha
  return bubble;
}

/**
 * Conecta em POST /chat/stream e vai preenchendo a bolha do Hermes
 * incrementalmente, token a token, conforme os eventos SSE chegam.
 *
 * Retorna o texto final completo em caso de sucesso, ou `null` se a
 * conexão falhou ANTES de qualquer token ser recebido (nesse caso o
 * chamador pode tentar o endpoint tradicional /chat/ como fallback, sem
 * duplicar mensagens na tela).
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
    // Falha de rede antes de qualquer token: permite fallback silencioso
    return null;
  }

  if (!streamRes.ok || !streamRes.body) {
    return null; // permite fallback para o endpoint tradicional
  }

  const reader = streamRes.body.getReader();
  const decoder = new TextDecoder('utf-8');
  let sseBuffer = '';

  while (true) {
    const { value, done } = await reader.read();
    if (done) break;
    sseBuffer += decoder.decode(value, { stream: true });

    // Eventos SSE são separados por uma linha em branco ("\n\n")
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
        // Aviso do sistema (ex: recursos sob pressão). Nunca entra no
        // texto da resposta do Hermes — só dispara notificação nativa.
        window.HermesNotifications.notify('Hermes AI', data.message);
      } else if (eventType === 'error') {
        if (!hermesBubble) hermesBubble = createHermesBubble();
        hermesText += `\n❌ ${data.error || 'Falha na comunicação'}`;
        hermesBubble.textContent = hermesText;
      }
      // evento "done" apenas sinaliza o fim do stream; nada a fazer aqui
    }
  }

  if (!hermesBubble) {
    // Stream terminou sem produzir nenhum token: permite fallback
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
      const title = projectId ? 'Nova conversa (projeto)' : 'Nova conversa';
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
      project_id: projectId || null,
      chat_id: chatId,
      // Pensamento visível: ativado apenas no modo analista (ou se o usuário quiser, mas removemos o toggle)
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
  const text = input.value.trim();
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
  input.value = '';
  input.style.height = 'auto';

  // Envia para o backend
  sendMessageToBackend(text, mode, projectId);
}

// Event listeners
sendBtn.addEventListener('click', sendMessage);
input.addEventListener('keydown', (e) => {
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

// Microfone: toast simples
const micBtn = document.querySelector('.input-icon-btn[title="Microfone"]');
micBtn.addEventListener('click', () => {
  alert('Ditado por voz ainda não disponível');
});

// Expor sendMessage globalmente para uso em outros módulos (ex: projetos)
window.sendMessage = sendMessage;
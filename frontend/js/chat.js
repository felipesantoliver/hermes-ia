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
 * Envia a mensagem para o backend e processa a resposta.
 */
async function sendMessageToBackend(userText, mode, projectId) {
  if (mode === 'analyst') {
    showAnalystIndicator();
  } else {
    showTypingIndicator();
  }
  if (window.HermesSphere) window.HermesSphere.setGenerating(true);

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
    };
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
    const hermesReply = data.reply;

    // 4. Remover indicador e adicionar resposta do Hermes
    removeTypingIndicator();
    addMessage('hermes', hermesReply);

    // 5. Notificar (se o usuário tiver ativado notificações push)
    if (window.HermesNotifications) {
      window.HermesNotifications.notify('Hermes', 'Sua resposta está pronta.');
    }

    // 6. Salvar a resposta do Hermes no backend (opcional, pois o backend já salva, mas faremos por segurança)
    // O backend já salva, então não precisamos chamar novamente.

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
  const thinkChip = document.getElementById('mode-think');
  const analystChip = document.getElementById('mode-analyst');
  if (codeChip.classList.contains('active')) mode = 'code';
  else if (thinkChip.classList.contains('active')) mode = 'think';
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
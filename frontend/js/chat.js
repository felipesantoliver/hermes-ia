/* ===================== LÓGICA DO CHAT ===================== */
/* Responsabilidade: renderizar mensagens, capturar o envio (clique/Enter)
   e falar com o backend. Ponto único de integração com a API do Hermes. */

const msgCol = document.getElementById('msg-col');
const messagesEl = document.getElementById('messages');
const input = document.getElementById('msg-input');

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

/**
 * TODO: substituir pela chamada real ao backend (FastAPI) quando o
 * loop do agente (MVP) estiver pronto. Hoje apenas simula uma resposta.
 */
function requestHermesResponse(userText) {
  setTimeout(() => {
    addMessage('hermes', 'Estou processando isso — em breve trago uma resposta completa.');
  }, 700);
}

function sendMessage() {
  const text = input.value.trim();
  if (!text) return;

  addMessage('user', text);
  input.value = '';
  input.style.height = 'auto';

  requestHermesResponse(text);
}

document.getElementById('send-btn').addEventListener('click', sendMessage);
input.addEventListener('keydown', (e) => {
  if (e.key === 'Enter' && !e.shiftKey) {
    e.preventDefault();
    sendMessage();
  }
});
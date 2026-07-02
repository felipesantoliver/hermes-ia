/* ===================== NOTIFICAÇÕES PUSH ===================== */
/* Responsabilidade: encapsular o uso da Notification API do navegador.
   Habilitado/desabilitado pelo toggle #push-toggle em settings.js;
   disparado por chat.js quando uma resposta do Hermes é concluída. */

window.HermesNotifications = {
  enabled: false,

  setEnabled(value) {
    this.enabled = !!value;
  },

  notify(title, body) {
    if (!this.enabled) return;
    if (!('Notification' in window)) return;
    if (Notification.permission !== 'granted') return;

    try {
      new Notification(title, { body });
    } catch (err) {
      console.error('[Hermes] Erro ao disparar notificação:', err);
    }
  },
};
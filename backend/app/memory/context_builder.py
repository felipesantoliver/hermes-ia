# ===================== CONTEXT BUILDER =====================
# Responsabilidade: decidir QUAL memória entra no prompt do LLM, respeitando
# o memory_scope do projeto, o disjuntor use_saved_memory do perfil, e o
# limite de tokens (proporcional a MAX_CONTEXT_TOKENS).
#
# Prioridade de inclusão (quando o orçamento de tokens aperta):
#   1. architectural_memory  (decisões arquiteturais)
#   2. conversation_memory   (resumo conversacional)
#   3. code_memory           (memória de código)

from typing import Optional, List
from ..config import settings
from . import store

# Fração do MAX_CONTEXT_TOKENS reservada para memória injetada.
# O restante fica para system prompt base, histórico de mensagens e resposta.
MEMORY_BUDGET_RATIO = 0.25

VALID_SCOPES = {"isolated", "isolated_read_external", "none"}


def _approx_tokens(text: str) -> int:
    """Aproximação simples: ~4 caracteres por token."""
    return max(1, len(text) // 4)


def _memory_budget() -> int:
    return max(1, int(settings.MAX_CONTEXT_TOKENS * MEMORY_BUDGET_RATIO))


def _format_architectural(items: List[dict]) -> List[str]:
    return [f"- [Decisão arquitetural] {i['title']}: {i['content']}" for i in items]


def _format_conversation(items: List[dict]) -> List[str]:
    return [f"- [Resumo de conversa anterior] {i['summary']}" for i in items]


def _format_code(items: List[dict]) -> List[str]:
    out = []
    for i in items:
        ref = f" ({i['file_ref']})" if i.get("file_ref") else ""
        out.append(f"- [Memória de código]{ref} {i['title']}: {i['content']}")
    return out


def _fetch_layers(project_id: Optional[str], chat_id: Optional[str], scope: Optional[str]):
    """
    Retorna (architectural_lines, conversation_lines, code_lines) já formatados,
    de acordo com o memory_scope resolvido.
    """
    if project_id is None:
        # Chat solto: sempre memória geral (project_id IS NULL).
        arch = store.list_architectural(None)
        conv = store.list_conversation_memory(None)
        code = store.list_code_memory(None)
        return _format_architectural(arch), _format_conversation(conv), _format_code(code)

    if scope == "isolated":
        arch = store.list_architectural(project_id, include_external=False)
        conv = store.list_conversation_memory(project_id, include_external=False)
        code = store.list_code_memory(project_id, include_external=False)

    elif scope == "isolated_read_external":
        arch = store.list_architectural(project_id, include_external=True)
        conv = store.list_conversation_memory(project_id, include_external=True)
        code = store.list_code_memory(project_id, include_external=True)

    else:
        # "none": sem isolamento por projeto — tratamento geral por chat.
        # Usa memória geral (project_id IS NULL) e, se houver chat_id,
        # também os resumos conversacionais amarrados a esse chat
        # especificamente (mesmo que tenham sido gravados com project_id).
        arch = store.list_architectural(None)
        code = store.list_code_memory(None)
        conv = store.list_conversation_memory(None)
        if chat_id:
            from ..db import db_cursor
            with db_cursor() as cur:
                cur.execute(
                    "SELECT * FROM conversation_memory WHERE chat_id = ? ORDER BY updated_at DESC",
                    (chat_id,),
                )
                extra = [store._row_to_conversation(r) for r in cur.fetchall()]
            seen_ids = {c["id"] for c in conv}
            conv = conv + [c for c in extra if c["id"] not in seen_ids]

    return _format_architectural(arch), _format_conversation(conv), _format_code(code)


def build_memory_context(project_id: Optional[str] = None, chat_id: Optional[str] = None) -> str:
    """
    Monta o bloco de texto de memória a ser injetado no system prompt.
    Retorna string vazia se:
      - use_saved_memory=false no perfil (disjuntor geral, sobrepõe tudo), ou
      - não houver nenhuma memória relevante.
    """
    if not store.get_use_saved_memory():
        return ""

    scope = None
    if project_id:
        scope = store.get_project_memory_scope(project_id)
        if scope not in VALID_SCOPES:
            scope = "isolated"

    arch_lines, conv_lines, code_lines = _fetch_layers(project_id, chat_id, scope)

    if not arch_lines and not conv_lines and not code_lines:
        return ""

    budget = _memory_budget()
    used = 0
    included: List[str] = []

    # Prioridade: arquitetural > conversacional > código
    for group in (arch_lines, conv_lines, code_lines):
        for line in group:
            cost = _approx_tokens(line)
            if used + cost > budget:
                continue
            included.append(line)
            used += cost

    if not included:
        return ""

    header = "Memória relevante (prioridade: decisões arquiteturais > resumo conversacional > memória de código):"
    return header + "\n" + "\n".join(included)
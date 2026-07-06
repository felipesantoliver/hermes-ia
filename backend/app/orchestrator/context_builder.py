# ===================== CONTEXT BUILDER =====================
# Responsabilidade: decidir QUAL memória entra no prompt do LLM, respeitando
# o memory_scope do projeto, o disjuntor use_saved_memory do perfil, e o
# limite de tokens (proporcional a MAX_CONTEXT_TOKENS).
#
# Prioridade de inclusão (quando o orçamento de tokens aperta):
#   1. architectural_memory  (decisões arquiteturais)
#   2. code_rag              (trechos relevantes do projeto)
#   3. conversation_memory   (resumo conversacional)
#   4. code_memory           (memória de código)
#   5. file_rag              (trechos de documentos da galeria)  <-- NOVO

from typing import Optional, List
from pathlib import Path
from ..config import settings
from ..memory import store
from ..memory.code_rag import retrieve  # import existente
from ..memory.file_rag import search_documents, extract_text   # <-- NOVO: extract_text
from .. import files as files_module   # <-- NOVO: resolve attachment por ID (loose OU projeto)
import logging

logger = logging.getLogger(__name__)

# Limites para não estourar o orçamento de contexto com anexos grandes.
ATTACHMENT_MAX_CHARS_PER_FILE = 6000
ATTACHMENT_MAX_TOTAL_CHARS = 16000

# Fração do MAX_CONTEXT_TOKENS reservada para memória injetada.
# O restante fica para system prompt base, histórico de mensagens e resposta.
MEMORY_BUDGET_RATIO = 0.25

VALID_SCOPES = {"isolated", "isolated_read_external", "none"}

# Heurística para ativar RAG: palavras-chave técnicas (existente)
RAG_TRIGGER_WORDS = {
    "def", "class", "import", "from", "return", "if", "else", "for", "while",
    "try", "except", "raise", "with", "as", "lambda", "yield",
    "function", "método", "classe", "código", "função", "bug", "refatorar",
    "refatoração", "otimizar", "performance", "error", "exceção", "teste",
    "unitário", "integração", "arquivo", ".py", ".js", ".ts", ".c", ".h",
    ".cpp", ".java", ".go", ".rs", ".rb", ".php",
    # Palavras que indicam referência a documentos
    "documento", "pdf", "manual", "especificação", "datasheet", "guia",
}


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


def _format_rag(results: List[dict]) -> List[str]:
    """Formata os trechos retornados pelo RAG de código."""
    lines = []
    for r in results:
        file = r.get("file", "desconhecido")
        line = r.get("line", 0)
        code = r.get("code", "").strip()
        if code:
            lines.append(f"- [Trecho de código] {file}:{line}\n```\n{code[:500]}\n```")
    return lines


def _format_file_rag(results: List[dict]) -> List[str]:
    """Formata os trechos retornados pelo RAG de documentos (galeria)."""
    lines = []
    for r in results:
        file_path = r.get("file_path", "desconhecido")
        chunk = r.get("chunk_text", "").strip()
        if chunk:
            lines.append(f"- [Trecho de documento] {file_path}:\n> {chunk[:500]}")
    return lines


def _should_use_rag(user_message: str) -> bool:
    """Heurística para decidir se a mensagem é técnica e merece RAG (código ou documentos)."""
    if not user_message:
        return False
    text = user_message.lower()
    for word in RAG_TRIGGER_WORDS:
        if word in text:
            return True
    return False


def _fetch_layers(project_id: Optional[str], chat_id: Optional[str], scope: Optional[str]):
    """Retorna (architectural_lines, conversation_lines, code_lines) já formatados,
    de acordo com o memory_scope resolvido."""
    if project_id is None:
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

    else:  # "none"
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


def build_memory_context(
    project_id: Optional[str] = None,
    chat_id: Optional[str] = None,
    user_message: Optional[str] = None,
    mode: Optional[str] = None,   # <-- NOVO parâmetro para detectar modo analista
) -> str:
    """
    Monta o bloco de texto de memória a ser injetado no system prompt.
    Retorna string vazia se:
      - use_saved_memory=false no perfil (disjuntor geral, sobrepõe tudo), ou
      - não houver nenhuma memória relevante.
    Inclui RAG de código (existente) e RAG de documentos (novo) se a mensagem for técnica
    ou se o modo for 'analyst'.
    """
    if not store.get_use_saved_memory():
        return ""

    scope = None
    if project_id:
        scope = store.get_project_memory_scope(project_id)
        if scope not in VALID_SCOPES:
            scope = "isolated"

    arch_lines, conv_lines, code_lines = _fetch_layers(project_id, chat_id, scope)
    rag_lines = []
    file_rag_lines = []

    # RAG de código: se houver mensagem do usuário e projeto, e a heurística ativar
    if project_id and user_message and _should_use_rag(user_message):
        try:
            results = retrieve(project_id, user_message, top_k=4)
            if results:
                rag_lines = _format_rag(results)
                logger.info(f"RAG (código): {len(rag_lines)} trechos recuperados para projeto {project_id}")
        except Exception as e:
            logger.warning(f"Falha no RAG de código para projeto {project_id}: {e}")

    # RAG de documentos: sempre no modo analista, ou se a heurística ativar
    use_file_rag = (mode == "analyst") or (user_message and _should_use_rag(user_message))
    if use_file_rag:
        try:
            # Busca documentos do projeto e também loose files (se não houver projeto)
            file_results = search_documents(
                query=user_message or "",
                project_id=project_id,
                include_loose=(project_id is None),
                top_k=3
            )
            if file_results:
                file_rag_lines = _format_file_rag(file_results)
                logger.info(f"RAG (documentos): {len(file_rag_lines)} trechos recuperados")
        except Exception as e:
            logger.warning(f"Falha no RAG de documentos: {e}")

    # Agrupar por prioridade: arch, code_rag, file_rag, conv, code
    groups = [
        ("Decisões arquiteturais", arch_lines),
        ("Código relevante do projeto", rag_lines),
        ("Trechos de documentos", file_rag_lines),
        ("Resumo conversacional", conv_lines),
        ("Memória de código", code_lines),
    ]

    budget = _memory_budget()
    used = 0
    included: List[str] = []

    for header, lines in groups:
        if not lines:
            continue
        included.append(f"\n{header}:")
        for line in lines:
            cost = _approx_tokens(line)
            if used + cost > budget:
                break
            included.append(line)
            used += cost

    if len(included) <= 1:
        return ""

    return "\n".join(included)


def build_attachments_block(attachment_ids: Optional[List[str]]) -> str:
    """
    Resolve uma lista de attachment_ids (vindos do drag-and-drop/upload do
    frontend) em texto pronto para ser anexado à mensagem do usuário.

    Busca cada arquivo tanto em `loose_files` quanto em `project_files`
    (ver files.get_file_record) — antes, buscas desse tipo olhavam só
    `loose_files` e "perdiam" qualquer arquivo anexado a partir de um
    projeto. Extensões sem extração de texto suportada (imagens, docx,
    binários em geral) entram no bloco apenas com o nome do arquivo, para
    o modelo saber que o anexo existe mesmo sem poder ler o conteúdo.
    """
    if not attachment_ids:
        return ""

    lines: List[str] = ["Arquivos anexados a esta mensagem pelo usuário:"]
    total_chars = 0

    for file_id in attachment_ids:
        record = files_module.get_file_record(file_id)
        if record is None:
            logger.warning(f"attachment_id {file_id} não encontrado (nem em loose_files, nem em project_files)")
            continue

        filename = record["filename"]
        path = Path(record["stored_path"])

        if not path.exists():
            lines.append(f"\n- {filename}: (arquivo não encontrado em disco)")
            continue

        text = ""
        try:
            text = extract_text(path)
        except Exception as e:
            logger.warning(f"Falha ao extrair texto do anexo {filename} ({file_id}): {e}")

        if not text:
            lines.append(f"\n- {filename}: (anexo binário ou formato sem extração automática de texto; "
                          f"apenas o nome do arquivo está disponível no contexto)")
            continue

        remaining_budget = ATTACHMENT_MAX_TOTAL_CHARS - total_chars
        if remaining_budget <= 0:
            lines.append(f"\n- {filename}: (conteúdo omitido — orçamento de contexto para anexos esgotado)")
            continue

        snippet = text[:min(ATTACHMENT_MAX_CHARS_PER_FILE, remaining_budget)]
        truncated = len(text) > len(snippet)
        lines.append(f"\n- {filename}:\n```\n{snippet}{' [...]' if truncated else ''}\n```")
        total_chars += len(snippet)

    if len(lines) <= 1:
        return ""

    return "\n".join(lines)
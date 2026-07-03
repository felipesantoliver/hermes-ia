# ===================== ROTEADOR DE AGENTE (HÍBRIDO) =====================
# Responsabilidade: decidir qual agente lógico deve tratar a mensagem do
# usuário (Desenvolvedor, Arquiteto, Firmware, Revisor).
#
# Estratégia híbrida:
#   1. Similaridade de embeddings locais (SentenceTransformer all-MiniLM-L6-v2)
#      contra um banco de exemplos rotulados por agente. Se a similaridade
#      máxima >= EMBEDDING_SIMILARITY_THRESHOLD, usa o agente correspondente.
#   2. Caso contrário (ou se o modelo de embeddings não estiver disponível),
#      cai para a heurística de palavras-chave original.
#
# O modelo de embeddings é opcional em tempo de execução: se
# sentence-transformers não estiver instalado ou o download falhar (sem
# internet, hardware sem espaço etc.), o roteador funciona só com a
# heurística de palavras-chave, sem quebrar o resto do sistema.

import json
import logging
import threading
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

from ..db import DATA_DIR

logger = logging.getLogger(__name__)

EMBEDDING_MODEL_NAME = "all-MiniLM-L6-v2"
EMBEDDING_SIMILARITY_THRESHOLD = 0.7

MODELS_DIR = DATA_DIR / "models"
FEEDBACK_PATH = DATA_DIR / "agent_examples_feedback.jsonl"

VALID_AGENTS = ("developer", "architect", "firmware", "reviewer")

# ---------------------------------------------------------------------------
# Banco de exemplos rotulados (>= 20 por agente).
# Usado para o classificador de embeddings. Frases curtas, representativas
# do tipo de pedido que cada agente deve resolver.
# ---------------------------------------------------------------------------
AGENT_EXAMPLES: Dict[str, List[str]] = {
    "developer": [
        "implemente uma função que valida CPF",
        "corrija esse bug no endpoint de login",
        "refatore essa classe para ficar mais legível",
        "escreva os testes unitários para esse módulo",
        "por que essa exceção está sendo lançada aqui?",
        "adicione um try/except nessa chamada de rede",
        "crie um endpoint POST para cadastrar usuários",
        "converta essa função síncrona para assíncrona",
        "otimize esse loop que está lento",
        "esse código não compila, me ajuda a achar o erro",
        "implemente paginação nessa listagem",
        "escreva um script que renomeia arquivos em lote",
        "crie uma classe para representar um pedido no sistema",
        "adicione validação de entrada nesse formulário",
        "por que esse teste está falhando intermitentemente?",
        "implemente cache em memória para essa consulta",
        "escreva a query SQL para buscar os últimos pedidos",
        "faça o parsing desse JSON e trate campos ausentes",
        "corrija o vazamento de memória nesse serviço",
        "implemente retry com backoff exponencial nessa chamada",
        "crie um decorator para logar tempo de execução",
        "escreva a integração com essa API externa",
        "esse regex não está capturando o grupo certo, ajuda",
        "implemente o CRUD completo dessa entidade",
    ],
    "architect": [
        "como devo estruturar as camadas desse sistema?",
        "qual a melhor forma de organizar os módulos do projeto?",
        "esse desenho de arquitetura escala bem para mais usuários?",
        "devo usar microsserviços ou monolito nesse caso?",
        "como planejar a migração dessa base de dados sem downtime?",
        "qual padrão de projeto se encaixa melhor aqui?",
        "como desacoplar esses dois módulos que estão muito acoplados?",
        "planeje a arquitetura de filas para esse fluxo assíncrono",
        "qual estratégia de cache faz sentido para esse sistema?",
        "como estruturar o versionamento dessa API pública?",
        "vale a pena introduzir um event bus nesse projeto?",
        "como distribuir responsabilidades entre esses serviços?",
        "qual a melhor forma de lidar com consistência eventual aqui?",
        "desenhe o fluxo de dados entre frontend, backend e banco",
        "como planejar a escalabilidade horizontal desse componente?",
        "esse acoplamento entre camadas está certo ou é um cheiro de código?",
        "como organizar as pastas desse monorepo?",
        "qual abordagem de autenticação faz mais sentido em escala?",
        "como planejar failover para esse serviço crítico?",
        "vale a pena separar esse módulo em um pacote próprio?",
        "vamos discutir os trade-offs entre SQL e NoSQL aqui",
        "como desenhar essa API para evoluir sem quebrar clientes?",
    ],
    "firmware": [
        "como configurar essa interrupção no microcontrolador?",
        "implemente a leitura desse sensor via I2C",
        "esse firmware está estourando o watchdog, como resolver?",
        "como ajustar o clock desse periférico via registrador?",
        "implemente o driver UART para esse chip",
        "como reduzir o consumo de energia desse dispositivo embarcado?",
        "esse código bare-metal não está inicializando o ADC direito",
        "como fazer debounce de botão em firmware sem usar delay?",
        "implemente a comunicação SPI com esse display",
        "como configurar o bootloader para esse microcontrolador?",
        "esse firmware está com stack overflow, como investigar?",
        "implemente PWM para controlar esse motor",
        "como lidar com timing crítico nessa rotina de interrupção?",
        "esse sensor está retornando leituras erradas via I2C, ajuda",
        "como implementar um protocolo de comunicação serial customizado?",
        "configure o RTC para manter a hora mesmo sem energia",
        "como otimizar esse firmware para caber na flash disponível?",
        "implemente a máquina de estados do firmware desse dispositivo",
        "como fazer atualização OTA nesse firmware?",
        "esse registrador não está setando o bit que eu esperava",
        "como calibrar esse sensor analógico no firmware?",
        "implemente comunicação CAN bus para esse módulo",
    ],
    "reviewer": [
        "revise esse código antes de eu mandar pro time",
        "essa solução tem algum problema de segurança?",
        "faça uma revisão crítica dessa implementação",
        "esse código está pronto para produção? o que falta?",
        "aponte os riscos dessa abordagem antes de eu seguir",
        "revise esse pull request e aponte melhorias",
        "esse tratamento de erro está completo ou tem lacunas?",
        "avalie se esse código cobre os casos de borda",
        "essa solução tem algum problema de performance escondido?",
        "faça uma checklist de qualidade para essa entrega",
        "revise a cobertura de testes desse módulo",
        "essa implementação segue as boas práticas do projeto?",
        "aponte inconsistências entre esse código e a especificação",
        "esse código tem vulnerabilidade de injeção em algum ponto?",
        "revise se esse código trata concorrência corretamente",
        "faça uma auditoria rápida desse trecho antes do deploy",
        "esse diff introduz alguma regressão perceptível?",
        "avalie criticamente essa solução antes da entrega final",
        "confirme se esse código está de acordo com o checklist de segurança",
        "revise a legibilidade e manutenibilidade desse código",
        "essa solução resolve o problema original por completo?",
    ],
}


class HybridAgentRouter:
    """Classificador híbrido de agente: embeddings locais com fallback para
    heurística de palavras-chave.

    Instanciar é relativamente caro (carrega/baixa o modelo de embeddings),
    então use get_router() para obter o singleton do processo.
    """

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._model = None
        self._model_load_attempted = False
        self._np = None

        # agente -> lista de (texto, embedding)
        self._examples: Dict[str, List[Tuple[str, Any]]] = {
            agent: [] for agent in VALID_AGENTS
        }

        self._load_builtin_examples()
        self._load_persisted_feedback()

    # ------------------------------------------------------------------
    # Carregamento preguiçoso do modelo de embeddings
    # ------------------------------------------------------------------
    def _ensure_model(self) -> bool:
        """Tenta carregar o SentenceTransformer sob demanda. Retorna True se
        disponível, False se não (o roteador deve então usar só a heurística).
        """
        if self._model is not None:
            return True
        if self._model_load_attempted:
            return False

        with self._lock:
            if self._model is not None:
                return True
            if self._model_load_attempted:
                return False
            self._model_load_attempted = True
            try:
                import numpy as np  # type: ignore
                from sentence_transformers import SentenceTransformer  # type: ignore

                MODELS_DIR.mkdir(parents=True, exist_ok=True)
                logger.info(
                    f"Carregando modelo de embeddings '{EMBEDDING_MODEL_NAME}' "
                    f"(cache em {MODELS_DIR})..."
                )
                self._model = SentenceTransformer(
                    EMBEDDING_MODEL_NAME, cache_folder=str(MODELS_DIR)
                )
                self._np = np
                logger.info("Modelo de embeddings carregado com sucesso.")
                return True
            except Exception as e:
                logger.warning(
                    "Não foi possível carregar o modelo de embeddings "
                    f"('{EMBEDDING_MODEL_NAME}'): {e}. "
                    "O roteador vai usar apenas a heurística de palavras-chave."
                )
                self._model = None
                return False

    def _encode(self, texts: List[str]):
        assert self._model is not None
        return self._model.encode(
            texts, normalize_embeddings=True, show_progress_bar=False
        )

    # ------------------------------------------------------------------
    # Construção do banco de exemplos
    # ------------------------------------------------------------------
    def _load_builtin_examples(self) -> None:
        if not self._ensure_model():
            # Sem modelo, ainda guardamos os textos (para caso o modelo
            # fique disponível depois via _ensure_model em nova tentativa
            # manual), mas sem embedding calculado.
            for agent, texts in AGENT_EXAMPLES.items():
                self._examples[agent] = [(t, None) for t in texts]
            return

        for agent, texts in AGENT_EXAMPLES.items():
            embeddings = self._encode(texts)
            self._examples[agent] = list(zip(texts, list(embeddings)))

    def _load_persisted_feedback(self) -> None:
        """Carrega exemplos adicionados via feedback do usuário (schema
        preparado para a feature futura de correção de agente no chat)."""
        if not FEEDBACK_PATH.exists():
            return
        try:
            lines = FEEDBACK_PATH.read_text(encoding="utf-8").splitlines()
        except Exception as e:
            logger.warning(f"Falha ao ler banco de feedback de exemplos: {e}")
            return

        pending_texts: Dict[str, List[str]] = {agent: [] for agent in VALID_AGENTS}
        for line in lines:
            line = line.strip()
            if not line:
                continue
            try:
                entry = json.loads(line)
                agent = entry.get("agent")
                text = entry.get("text")
                if agent in VALID_AGENTS and text:
                    pending_texts[agent].append(text)
            except json.JSONDecodeError:
                continue

        model_ok = self._model is not None
        for agent, texts in pending_texts.items():
            if not texts:
                continue
            if model_ok:
                embeddings = self._encode(texts)
                self._examples[agent].extend(zip(texts, list(embeddings)))
            else:
                self._examples[agent].extend((t, None) for t in texts)

    def add_example(self, agent: str, text: str) -> bool:
        """Persiste um novo exemplo rotulado (ex: usuário corrigiu a escolha
        de agente no chat) e o incorpora ao banco em memória.

        Preparado para a feature futura de feedback; hoje não é chamado por
        nenhuma rota da API, mas o schema do arquivo já é estável:
          {"timestamp": ISO8601, "agent": "developer|architect|firmware|reviewer", "text": "..."}
        """
        agent = agent.strip().lower()
        text = text.strip()
        if agent not in VALID_AGENTS or not text:
            return False

        entry = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "agent": agent,
            "text": text,
        }
        try:
            DATA_DIR.mkdir(parents=True, exist_ok=True)
            with open(FEEDBACK_PATH, "a", encoding="utf-8") as f:
                f.write(json.dumps(entry, ensure_ascii=False) + "\n")
        except Exception as e:
            logger.warning(f"Falha ao persistir exemplo de feedback: {e}")
            return False

        if self._ensure_model():
            embedding = self._encode([text])[0]
            self._examples[agent].append((text, embedding))
        else:
            self._examples[agent].append((text, None))
        return True

    # ------------------------------------------------------------------
    # Classificação
    # ------------------------------------------------------------------
    def _classify_by_embedding(self, text: str) -> Tuple[Optional[str], float]:
        if not self._ensure_model():
            return None, 0.0

        np = self._np
        query_emb = self._encode([text])[0]

        best_agent: Optional[str] = None
        best_score = -1.0
        for agent, examples in self._examples.items():
            for _, emb in examples:
                if emb is None:
                    continue
                score = float(np.dot(emb, query_emb))
                if score > best_score:
                    best_score = score
                    best_agent = agent

        if best_agent is None:
            return None, 0.0
        return best_agent, best_score

    @staticmethod
    def _classify_by_keywords(user_message: str) -> str:
        """Heurística original de palavras-chave, mantida como fallback."""
        architecture_keywords = [
            "arquitetura", "design", "estrutura", "planejamento",
            "como organizar", "melhor forma", "escalabilidade",
        ]
        firmware_keywords = [
            "firmware", "microcontrolador", "embarcado", "bare-metal",
            "i2c", "spi", "uart", "watchdog", "registrador", "pwm",
            "interrupção", "bootloader", "can bus",
        ]
        reviewer_keywords = [
            "revise", "revisão", "aponte os riscos", "está pronto para produção",
            "auditoria", "checklist de qualidade", "pull request",
        ]
        dev_keywords = [
            "código", "implementar", "função", "classe", "bug",
            "corrigir", "refatorar", "teste", "compilar",
        ]

        text = user_message.lower()
        if any(kw in text for kw in firmware_keywords):
            return "firmware"
        if any(kw in text for kw in reviewer_keywords):
            return "reviewer"
        if any(kw in text for kw in architecture_keywords):
            return "architect"
        if any(kw in text for kw in dev_keywords):
            return "developer"
        return "developer"

    def classify(self, mode: Optional[str], user_message: str) -> Dict[str, Any]:
        """Retorna um dict com o resultado completo da classificação:
        {"agent": str, "agents": List[str], "score": Optional[float], "method": str}
        """
        if mode == "code":
            return {"agent": "developer", "agents": ["developer"], "score": None, "method": "mode_override"}
        if mode == "think":
            return {"agent": "architect", "agents": ["architect"], "score": None, "method": "mode_override"}

        agent, score = self._classify_by_embedding(user_message)
        if agent is not None and score >= EMBEDDING_SIMILARITY_THRESHOLD:
            method = "embedding"
        else:
            agent = self._classify_by_keywords(user_message)
            method = "keyword_heuristic"

        agents = [agent]
        # Modo analista: força o Revisor como parte do loop, mas mantém a
        # seleção de Desenvolvedor/Arquiteto (ou Firmware) para a execução.
        if mode == "analyst" and "reviewer" not in agents:
            agents.append("reviewer")

        return {"agent": agent, "agents": agents, "score": score, "method": method}


_router_singleton: Optional[HybridAgentRouter] = None
_router_lock = threading.Lock()


def get_router() -> HybridAgentRouter:
    global _router_singleton
    if _router_singleton is None:
        with _router_lock:
            if _router_singleton is None:
                _router_singleton = HybridAgentRouter()
    return _router_singleton


def select_agent(mode: Optional[str], user_message: str) -> str:
    """Mantém a assinatura/retorno original (nome do agente principal) para
    compatibilidade com quem já chama select_agent(mode, message).
    """
    return get_router().classify(mode, user_message)["agent"]


def get_active_agents(mode: Optional[str], user_message: str) -> List[str]:
    """Retorna todos os agentes ativos para a mensagem, incluindo o Revisor
    quando o modo analista está ativo."""
    return get_router().classify(mode, user_message)["agents"]
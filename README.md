# 🧠 Hermes AI

**Assistente pessoal de IA local-first focado em gestão de projetos, engenharia de software e desenvolvimento técnico multi-domínio.**  
O Hermes não é um chatbot: é um **sistema operacional de desenvolvimento assistido por IA**, onde você constrói software, firmware e sistemas com o suporte contínuo de um agente inteligente local.

> **Status:** ✅ MVP concluído | ✅ V1 concluída | 🟡 V2 em desenvolvimento (Modo Engenheiro implementado, RAG avançado, pesquisa web)

---

## 📚 Sumário

- [Visão Geral](#visão-geral)
- [Arquitetura](#arquitetura)
- [Componentes Principais](#componentes-principais)
- [Estrutura do Projeto](#estrutura-do-projeto)
- [Como Executar Localmente](#como-executar-localmente)
- [Funcionalidades](#funcionalidades)
- [Roadmap](#roadmap)
- [Princípios Fundamentais](#princípios-fundamentais)
- [Hardware Alvo](#hardware-alvo)
- [Privacidade](#privacidade)
- [Licença](#licença)

---

## Visão Geral

O Hermes é um ambiente onde **projetos são entidades vivas**, decisões arquiteturais são lembradas, o código é iterado com ferramentas reais e a IA atua como parte do time de engenharia.

- **LLM local** (Qwen 7B–8B quantizado)
- **Ferramentas executáveis** em sandbox (Python, shell, compilação, análise estática…)
- **Memória estruturada** por projeto (3 camadas + RAG semântico para código)
- **Agentes lógicos** configuráveis (Desenvolvedor, Arquiteto, Firmware, Revisor)
- **Modo Analista** – verificação rigorosa multi-etapa com o mesmo modelo
- **Modo Engenheiro** – segundo modelo local maior, opcional, para raciocínio mais profundo
- **Streaming SSE** e **Pensamento Visível** para total transparência
- **Pesquisa web** integrada (via SearXNG local)
- **RAG avançado** para código (busca semântica em funções/classes do projeto)

> O objetivo não é gerar respostas – é **resolver problemas de engenharia de forma contínua e incremental**.

---

## Arquitetura
Usuário
↓
Frontend (SPA vanilla + Three.js)
↓
Backend (FastAPI) – /chat, /projects, /chats, /profile, /files, /system
↓
Orquestrador (AgentLoop) – gerencia o ciclo de raciocínio
↓
Classificador híbrido (embeddings + heurística) – escolhe o agente
↓
LLM Core (Qwen 7B/8B) – ou modelo Engenheiro opcional
↓
Tools (sandbox) – Python, Shell, arquivos, busca, indexação, firmware…
↓
Memória (3 camadas + RAG com FAISS para código)
↓
Resposta final (streaming SSE + pensamento visível opcional)

text

### Backend (FastAPI)
- Rotas organizadas por domínio (chat, projetos, perfil, arquivos, sistema)
- SQLite com migrações automáticas
- Cliente LLM compatível com API OpenAI (llama.cpp) e suporte a carregamento embarcado via `llama-cpp-python`
- Agent Loop com suporte a tools e iterações múltiplas
- Monitor de recursos em background (RAM/CPU)
- Log de auditoria de todas as execuções de ferramentas
- **RAG para código**: busca semântica em funções/classes indexadas via FAISS, ativada automaticamente para perguntas técnicas

### Frontend (SPA vanilla)
- HTML/CSS/JS puro, sem frameworks; Three.js para visualizações 3D
- Views: Chat, Projetos, Galeria
- Sidebar com chats fixados, recentes, navegação e mini-esfera 3D reativa
- Consumo de eventos SSE (`token`, `thinking`, `system`, `error`, `done`)
- Estado global compartilhado (`HermesState`) e modais auto-save
- **Chip "Web"** para ativar/desativar a pesquisa web na conversa atual

### LLM Core (Qwen 7B–8B)
- Modelo local quantizado (Q4–Q5) executado via llama.cpp
- Responsável por interpretação, planejamento, geração de código e decisão de ferramentas
- **Modo Engenheiro** opcional: segundo modelo maior (ex: Qwen 14B ou 32B), ativável pelo usuário, com fallback automático

---

## Componentes Principais

### Orquestrador e Agent Loop
O `AgentLoop` (arquivo `loop.py`):
1. Prepara o prompt (sistema + tools + memória + RAG)
2. Chama o LLM (streaming ou não)
3. Se a resposta for uma chamada de ferramenta (JSON), executa e realimenta o resultado
4. Itera até obter resposta final ou atingir o limite
5. No **Modo Analista**, delega para o `AnalystOrchestrator`
6. No **Modo Engenheiro**, usa o modelo maior com menos iterações (4)

### Agentes Lógicos
Configurações de comportamento definidas por system prompt, ferramentas e recorte de contexto.  
Selecionados por um classificador híbrido (embeddings + heurística).

| Agente        | Responsabilidade |
|---------------|------------------|
| Desenvolvedor | Implementa, refatora e depura código |
| Arquiteto     | Estrutura sistemas, planeja arquitetura |
| Firmware      | Microcontroladores, registradores, periféricos (ESP32, STM32…) |
| Revisor       | Qualidade, segurança e conformidade |
| Analista*     | Loop rigoroso com múltiplos candidatos, juiz e checklists |
| Engenheiro*   | Usa modelo maior opcional para raciocínio profundo |

*Modos especiais, não agentes fixos.

### Ferramentas (Tools)
Executadas em sandbox com restrições rigorosas:

- **RunPythonTool**: sem rede, limite de 128 MB RAM, timeout configurável
- **RunShellTool**: allowlist de comandos seguros, bloqueio de metacaracteres
- **ReadFileTool**: leitura segura dentro do projeto, prevenção de path traversal
- **WebSearchTool**: integração com SearXNG local (ativável via chip "Web")
- **CodebaseIndexTool**: indexação FAISS de funções/classes (preparação RAG)
- **FirmwareTool**: detecção e compilação de projetos C/C++ com PlatformIO
- **BanditTool / ShellCheckTool**: análise estática de segurança
- **Log de auditoria**: todas as execuções registradas (`tool_audit.jsonl`)

### Memória e RAG
Organizada em 4 camadas com prioridade de inclusão no contexto:
1. **Arquitetural** – decisões de design, padrões
2. **RAG (Código relevante)** – trechos de código do projeto recuperados por similaridade semântica
3. **Conversacional** – resumos compactos de conversas anteriores
4. **Código** – notas sobre arquivos e trechos (menos prioritário)

O RAG é ativado automaticamente quando a mensagem do usuário contém termos técnicos (`def`, `class`, `import`, nomes de arquivo, etc.) e o projeto possui um índice FAISS. Se o índice não existir, ele é gerado sob demanda na primeira consulta.

Escopos configuráveis por projeto: `isolated`, `isolated_read_external` ou `none`.  
O usuário pode desabilitar a memória globalmente.

### Modo Analista
Ativado manualmente ou automaticamente para contextos de alto rigor. Processo:
1. Decomposição da tarefa em subtarefas independentes
2. Para cada subtarefa: 3 candidatos, auto-crítica, juiz, verificação obrigatória com ferramentas, refinamento
3. Integração global com debate interno (Arquiteto vs. Revisor) e checklists de domínio
4. Resposta final com resumo, solução e evidências

### Modo Engenheiro (V2.1)
- **Segundo modelo local maior** (ex: Qwen 14B, 32B), quantizado, opcional.
- **Configuração**: via painel "Modelos" nas configurações – defina o caminho do arquivo `.gguf` ou a URL de um servidor llama.cpp dedicado.
- **Ativação**: chip "Engenheiro" na barra de mensagens.
- **Comportamento**: usa o modelo maior diretamente, com no máximo 4 iterações, mantendo a verificação por tools e memória.
- **Integração com o Analista**: se disponível, o modo Analista utiliza o modelo engenheiro para gerar candidatos e atuar como juiz, aumentando a qualidade sem custo extra de iterações.
- **Fallback**: se o modelo engenheiro não estiver configurado ou falhar, o sistema volta automaticamente ao modelo padrão, com log.

### Pensamento Visível
Quando o modo Analista está ativo, o backend emite eventos `thinking` (SSE) com a narrativa do raciocínio. O frontend exibe isso em um bloco expansível acima da resposta final.  
*(O antigo chip "Pensamento" foi removido; a funcionalidade foi incorporada ao Modo Analista.)*

### Streaming SSE
Endpoint `/chat/stream` emite eventos: `token`, `thinking`, `system`, `error`, `done`.  
O frontend renderiza a resposta em tempo real e destaca avisos do sistema.

### Monitor de Recursos
Thread em background que mede RAM/CPU a cada 5s.  
Quando o uso de RAM ultrapassa 80% do limite configurado, o sistema entra em `under_pressure` e pausa ferramentas pesadas automaticamente.

### Perfil e Configurações
- **Perfil**: nome, apelido do Hermes, personalidade, filtro de conteúdo, memória, etc.
- **Configurações**: tema, idioma, notificações, limite de RAM, modo engenheiro (com campos para path/URL e teste), ações destrutivas.

---

## Estrutura do Projeto
hermes-ai/
├── backend/
│ ├── app/
│ │ ├── main.py
│ │ ├── config.py
│ │ ├── db.py
│ │ ├── llm.py
│ │ ├── monitor.py
│ │ ├── chat.py
│ │ ├── chats.py
│ │ ├── projects.py
│ │ ├── files.py
│ │ ├── profile.py
│ │ ├── profile_prompt.py
│ │ ├── system.py
│ │ ├── orchestrator/
│ │ │ ├── loop.py
│ │ │ ├── analyst.py
│ │ │ ├── router.py
│ │ │ └── context_builder.py
│ │ ├── memory/
│ │ │ ├── store.py
│ │ │ ├── code_rag.py # NOVO: RAG para código
│ │ │ └── init.py
│ │ ├── tools/
│ │ │ ├── base.py
│ │ │ ├── registry.py
│ │ │ ├── read_file.py
│ │ │ ├── run_python.py
│ │ │ ├── run_shell.py
│ │ │ ├── web_search.py
│ │ │ ├── codebase_index.py
│ │ │ ├── firmware.py
│ │ │ ├── security_static.py
│ │ │ ├── audit.py
│ │ │ └── indexer.py
│ │ ├── prompts/
│ │ └── knowledge/checklists/
│ ├── data/
│ ├── scripts/
│ │ ├── test_analyst_mode.py
│ │ ├── test_engineer_mode.py
│ │ ├── test_llm.py
│ │ ├── test_loop.py
│ │ ├── test_memory_scope.py
│ │ ├── test_profile.py
│ │ ├── test_streaming.py
│ │ ├── test_stress_memory.py
│ │ ├── test_thinking_visible.py
│ │ └── test_code_rag.py # NOVO
│ ├── requirements.txt
│ └── README.md
├── frontend/
│ ├── index.html
│ ├── css/
│ │ ├── theme.css
│ │ ├── layout.css
│ │ ├── chat.css
│ │ ├── projects.css
│ │ ├── gallery.css
│ │ ├── settings.css
│ │ └── profile.css
│ └── js/
│ ├── state.js
│ ├── ui.js
│ ├── chat.js
│ ├── chats.js
│ ├── projects.js
│ ├── gallery.js
│ ├── settings.js
│ ├── profile.js
│ ├── notifications.js
│ └── spheres.js
├── .gitignore
└── README.md

text

---

## Como Executar Localmente

### Pré-requisitos
- **Python 3.10+** com pip
- **Servidor llama.cpp** rodando localmente (ou compatível com API OpenAI)
- **Node.js** (opcional, para desenvolvimento do frontend – a SPA é estática)
- **SearXNG** (opcional, para busca web)
- **PlatformIO** (opcional, para compilação de firmware)
- **Bandit / ShellCheck** (opcionais, para análise estática)
- **llama-cpp-python** (opcional, para carregamento embarcado do modelo engenheiro)

### Passos

1. **Clone o repositório**
   ```bash
   git clone https://github.com/felipesantoliver/hermes-ai.git
   cd hermes-ai
Configure o backend

bash
cd backend
python -m venv venv
source venv/bin/activate   # Linux/Mac
# .\venv\Scripts\activate no Windows
pip install -r requirements.txt
Configure o LLM

Baixe um modelo Qwen 7B/8B quantizado (ex: Qwen2.5-7B-Instruct-Q4_K_M.gguf)

Coloque em backend/models/hermes-core.gguf ou ajuste o caminho em config.py

Inicie o servidor llama.cpp:

bash
llama-server -m models/hermes-core.gguf --host 0.0.0.0 --port 8080
Inicie o backend

bash
uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
Sirva o frontend

bash
cd frontend
python -m http.server 3000
Acesse http://localhost:3000 no navegador.

Configuração do Modo Engenheiro (opcional)
Baixe um modelo maior (ex: Qwen 14B ou 32B) e coloque em backend/models/engineer/ ou outro diretório.

No frontend, acesse Configurações > Modelos.

Preencha o caminho do arquivo .gguf ou a URL do servidor llama.cpp dedicado.

Clique em "Testar conexão" para verificar.

Ative o chip "Engenheiro" na barra de mensagens para usar o modelo maior.

Funcionalidades
Funcionalidade	Descrição
💬 Chat	Envio de mensagens com streaming SSE, fallback para resposta completa e anexos.
📁 Projetos	CRUD completo; cada projeto possui instruções, persona, arquivos, escopo de memória e chats associados.
🗂 Sidebar	Chats fixados, recentes, busca, menu de contexto (fixar, renomear, mover, arquivar, excluir).
🖼 Galeria	Visualização em grid de todos os arquivos (usuário e sistema) com download/exclusão.
👤 Perfil	Personalização do tom do Hermes (personalidade, entusiasmo, emojis, memória, etc.).
⚙️ Configurações	Tema, idioma, notificações, limite de RAM, modo engenheiro (configuração e teste), ações destrutivas.
🔍 Modo Analista	Verificação rigorosa com decomposição, múltiplos candidatos, juiz, ferramentas e checklists.
🧠 Pensamento Visível	Exibição do raciocínio interno em tempo real (bloco expansível) – ativo no Modo Analista.
🚀 Modo Engenheiro	Modelo local maior opcional para tarefas complexas, com integração ao modo Analista.
🔧 Ferramentas	Execução segura de Python, shell, leitura de arquivos, busca, indexação, análise estática, compilação.
🌐 Pesquisa Web	Ativação por chip "Web" – usa SearXNG local para enriquecer respostas com informações da internet.
📊 Monitor	Medição contínua de RAM/CPU com pausa automática de ferramentas pesadas.
📝 Logs	Auditoria de todas as execuções de tools, logs de conversa e do modo analista (JSONL).
Roadmap
✅ MVP (concluído) – Backend FastAPI, SQLite, SPA vanilla, integração com LLM local, Agent Loop básico, memória em 3 camadas, classificador heurístico.

✅ V1 (concluída) – Modo Analista completo, streaming SSE, Pensamento Visível, classificador híbrido, monitor de recursos, notificações push, sandbox reforçado, testes automatizados.

🟡 V2 (em desenvolvimento) – Modo Engenheiro (implementado), RAG avançado (implementado), pesquisa web (implementada), planejamento multi-step, especialização por domínio (Android, BLE…), empacotamento (.exe, pacote Linux), interface por voz (STT/TTS).

Princípios Fundamentais
Local-first – Nada depende de nuvem; dados e processamento permanecem na máquina do usuário.

Ferramentas > LLM – O modelo nunca executa lógica crítica; tudo é delegado a ferramentas determinísticas.

Contexto mínimo necessário – Memória compactada e priorizada para respeitar o orçamento de tokens.

Iteração contínua – O agente refina a resposta com base em feedback real das ferramentas.

Sistema testável – Componentes isolados e cobertos por testes.

Latência como moeda – No modo Analista, qualidade é priorizada sobre velocidade.

Hardware Alvo
Componente	Especificação
CPU	AMD Ryzen 5 5500
GPU	AMD RX 580 8GB (Vulkan)
RAM	16 GB DDR4
Funciona em configurações mais modestas, ajustando o limite de RAM e o tamanho do modelo.

Privacidade
100% local – Nenhuma informação é enviada à internet, exceto se o usuário ativar explicitamente a busca web (via SearXNG local).

Controle total – Chats, projetos e memórias podem ser apagados a qualquer momento.

Logs anônimos – Registros de auditoria não contêm identificadores pessoais.

Licença
MIT – veja o arquivo LICENSE para detalhes.

Desenvolvido por Felipe Sant'Oliver – um assistente de IA para engenheiros, feito por um engenheiro.
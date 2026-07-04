🧠 Hermes AI

**Assistente pessoal de IA local-first focado em gestão de projetos, engenharia de software e desenvolvimento técnico multi-domínio.**  
O Hermes não é um chatbot: é um **sistema operacional de desenvolvimento assistido por IA**, onde você constrói software, firmware e sistemas com o suporte contínuo de um agente inteligente local.

> **Status:** ✅ MVP concluído | ✅ V1 concluída | ✅ V2 concluído | ✅ V2.4 (instalador gráfico Windows) concluído.

---

## 📚 Sumário

- [Visão Geral](#visão-geral)
- [Arquitetura](#arquitetura)
- [Componentes Principais](#componentes-principais)
- [Estrutura do Projeto](#estrutura-do-projeto)
- [Como Executar](#como-executar)
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
- **Agentes lógicos** configuráveis (Desenvolvedor, Arquiteto, Firmware, Revisor, **Android**)
- **Modo Analista** – verificação rigorosa multi-etapa com o mesmo modelo
- **Modo Engenheiro** – segundo modelo local maior, opcional, para raciocínio mais profundo
- **Streaming SSE** e **Pensamento Visível** para total transparência
- **Pesquisa web** integrada (via SearXNG local)
- **RAG avançado** para código (busca semântica em funções/classes do projeto)
- **Planejamento multi‑step explícito** (V2.2) – o Hermes gera um plano de ação antes de executar tarefas complexas, exibindo os passos e progresso em tempo real
- **Especialização por domínio** (V2.3) – chips Firmware e Android, com ferramentas dedicadas (BLE, Gradle, validação de layouts)
- **Instalador gráfico para Windows** (V2.4) – assistente "next, next, finish" que detecta a placa de vídeo, baixa o modelo certo e cria os atalhos, sem precisar de linha de comando

> O objetivo não é gerar respostas – é **resolver problemas de engenharia de forma contínua e incremental**.

---

## Arquitetura
```
Usuário
↓
Frontend (SPA vanilla + Three.js)
↓
Backend (FastAPI) – /chat, /projects, /chats, /profile, /files, /system
↓
Orquestrador (AgentLoop) – gerencia o ciclo de raciocínio
↓
Classificador híbrido (embeddings + heurística + domínio) – escolhe o agente
↓
LLM Core (Qwen 7B/8B) – ou modelo Engenheiro opcional
↓
Planejador multi‑step (V2.2) – gera planos de ação para tarefas complexas
↓
Tools (sandbox) – Python, Shell, arquivos, busca, indexação, firmware, BLE, Gradle, layout
↓
Memória (3 camadas + RAG com FAISS para código)
↓
Resposta final (streaming SSE + pensamento visível opcional + plano)
```

### Backend (FastAPI)
- Rotas organizadas por domínio (chat, projetos, perfil, arquivos, sistema)
- SQLite com migrações automáticas
- Cliente LLM compatível com API OpenAI (llama.cpp) e suporte a carregamento embarcado via `llama-cpp-python`
- Agent Loop com suporte a tools e iterações múltiplas
- Monitor de recursos em background (RAM/CPU)
- Log de auditoria de todas as execuções de ferramentas
- **RAG para código**: busca semântica em funções/classes indexadas via FAISS, ativada automaticamente para perguntas técnicas
- **Planejador multi‑step**: gera planos de ação estruturados (passos com dependências) para tarefas complexas, com suporte a replanejamento em caso de falha
- **Especialização por domínio**: agentes Firmware e Android com prompts e ferramentas dedicadas

### Frontend (SPA vanilla)
- HTML/CSS/JS puro, sem frameworks; Three.js para visualizações 3D
- Views: Chat, Projetos, Galeria
- Sidebar com chats fixados, recentes, navegação e mini-esfera 3D reativa
- Consumo de eventos SSE (`token`, `thinking`, `system`, `error`, `done`, `plan`, `step_progress`, etc.)
- Estado global compartilhado (`HermesState`) e modais auto-save
- **Chip "Web"** para ativar/desativar a pesquisa web na conversa atual
- **Card de plano expansível** com checkboxes e indicadores de progresso (V2.2)
- **Chips de domínio**: Firmware e Android, que podem ser combinados com os modos existentes

### LLM Core (Qwen 7B–8B)
- Modelo local quantizado (Q4–Q5) executado via llama.cpp
- Responsável por interpretação, planejamento, geração de código e decisão de ferramentas
- **Modo Engenheiro** opcional: segundo modelo maior (ex: Qwen 14B ou 32B), ativável pelo usuário, com fallback automático

---

## Componentes Principais

### Orquestrador e Agent Loop
O `AgentLoop` (arquivo `loop.py`):
1. Prepara o prompt (sistema + tools + memória + RAG + prompt específico do agente)
2. Se a tarefa for complexa, invoca o `Planner` para gerar um plano multi‑step
3. Chama o LLM (streaming ou não)
4. Se a resposta for uma chamada de ferramenta (JSON), executa e realimenta o resultado
5. Itera até obter resposta final ou atingir o limite
6. No **Modo Analista**, delega para o `AnalystOrchestrator` (que pode usar o plano como base)
7. No **Modo Engenheiro**, usa o modelo maior com menos iterações (4)

### Planejador Multi‑step (V2.2)
- Detecta tarefas complexas por heurística (tamanho ou palavras‑chave)
- Gera um plano estruturado (lista de passos com descrição, ferramenta, parâmetros e dependências) usando o LLM
- O plano é exibido ao usuário como um card expansível com checkboxes
- O orquestrador executa os passos sequencialmente, emitindo eventos SSE para atualizar o progresso
- Suporta replanejamento automático se um passo falhar

### Agentes Lógicos
Configurações de comportamento definidas por system prompt, ferramentas e recorte de contexto.  
Selecionados por um classificador híbrido (embeddings + heurística + domínio explícito).

| Agente        | Responsabilidade |
|---------------|------------------|
| Desenvolvedor | Implementa, refatora e depura código |
| Arquiteto     | Estrutura sistemas, planeja arquitetura |
| Firmware      | Microcontroladores, registradores, periféricos (ESP32, STM32…), BLE |
| Android       | Desenvolvimento Android (Kotlin/Java, Gradle, layouts) |
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
- **BLEConfigTool**: geração de código BLE a partir de JSON (ESP32, genérico)
- **GradleBuildTool**: execução de tarefas Gradle em projetos Android
- **LayoutValidatorTool**: validação de layouts XML Android
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
1. Decomposição da tarefa em subtarefas independentes (ou uso de plano pré‑gerado)
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

### Especialização por Domínio (V2.3)
- **FirmwareAgent**: especializado em C/C++ para microcontroladores, BLE, registradores. Tools: FirmwareTool, BLEConfigTool.
- **AndroidAgent**: especializado em desenvolvimento Android (Kotlin/Java). Tools: GradleBuildTool, LayoutValidatorTool.
- Ativação via chips de domínio no frontend, que podem ser combinados com os modos existentes (code, engineer, analyst).
- O agente é selecionado automaticamente se o domínio for detectado pela heurística (classificador híbrido) ou forçado pelo usuário.

### Instalador Gráfico Windows (V2.4)
- Feito em **Inno Setup** (Pascal Script), 100% em português do Brasil.
- Fluxo "next, next, finish": boas-vindas, licença MIT, pasta de instalação, seleção da placa de vídeo, download do modelo, atalhos.
- **Detecção de GPU**: tenta identificar automaticamente a placa de vídeo (via `wmic`/PowerShell) e pré-seleciona a opção correta; o usuário sempre pode confirmar ou trocar manualmente, inclusive com uma opção "Não sei".
- **Download do modelo com retomada**: usa o BITS (Background Intelligent Transfer Service, nativo do Windows) para baixar o `.gguf` certo direto do Hugging Face, com barra de progresso e retomada automática se a conexão cair. Pode ser pulado se a internet estiver lenta.
- **Verificações automáticas**: espaço em disco disponível e presença do Microsoft Edge WebView2 Runtime (necessário para o pywebview), oferecendo baixar e instalar se estiver faltando.
- Não exige privilégios de administrador, a menos que o usuário escolha instalar em `C:\Program Files`.
- Código-fonte versionado em `installer/` (veja [Como Executar](#como-executar), Opção A).

### Pensamento Visível
Quando o modo Analista está ativo, o backend emite eventos `thinking` (SSE) com a narrativa do raciocínio. O frontend exibe isso em um bloco expansível acima da resposta final.

### Streaming SSE
Endpoint `/chat/stream` emite eventos: `token`, `thinking`, `system`, `error`, `done`, e agora também `plan`, `step_start`, `step_progress`, `step_done`, `step_failed` (V2.2).  
O frontend renderiza a resposta em tempo real e destaca avisos do sistema, além de exibir o plano e seu progresso.

### Monitor de Recursos
Thread em background que mede RAM/CPU a cada 5s.  
Quando o uso de RAM ultrapassa 80% do limite configurado, o sistema entra em `under_pressure` e pausa ferramentas pesadas automaticamente.

### Perfil e Configurações
- **Perfil**: nome, apelido do Hermes, personalidade, filtro de conteúdo, memória, etc.
- **Configurações**: tema, idioma, notificações, limite de RAM, modo engenheiro (com campos para path/URL e teste), ações destrutivas.

---

## Estrutura do Projeto
```
hermes-ai/
├── installer/
│ ├── HermesSetup.iss         # script do instalador gráfico (Inno Setup)
│ └── scripts/
│   └── DownloadFile.ps1      # download do modelo via BITS, com retomada
├── backend/
│ ├── backend_main.py
│ ├── app/
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
│ │ │ ├── planner.py
│ │ │ ├── router.py
│ │ │ └── context_builder.py
│ │ ├── memory/
│ │ │ ├── store.py
│ │ │ ├── code_rag.py
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
│ │ │ ├── ble_config.py       # NOVO V2.3
│ │ │ ├── gradle_build.py     # NOVO V2.3
│ │ │ ├── layout_validator.py # NOVO V2.3
│ │ │ ├── audit.py
│ │ │ └── indexer.py
│ │ ├── prompts/
│ │ │ ├── analyst_system.txt
│ │ │ ├── firmware_agent.txt  # NOVO V2.3
│ │ │ └── android_agent.txt   # NOVO V2.3
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
│ │ ├── test_code_rag.py
│ │ ├── test_planner.py
│ │ ├── test_firmware_agent.py # NOVO V2.3
│ │ └── test_android_agent.py  # NOVO V2.3
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
│   ├── state.js
│   ├── ui.js
│   ├── chat.js
│   ├── chats.js
│   ├── projects.js
│   ├── gallery.js
│   ├── settings.js
│   ├── profile.js
│   ├── notifications.js
│   └── spheres.js
├── .gitignore
└── README.md
```

---

## Como Executar

O Hermes tem quatro jeitos de rodar, do mais simples ao mais avançado.

### Opção A — Instalador gráfico do Windows (recomendado para o público geral)

A forma mais simples, pensada para quem nunca mexeu com terminal:

1. Baixe o `Hermes-ia-Setup.exe` (gerado a partir de `installer/HermesSetup.iss`).
2. Dê duplo clique e siga o assistente: boas-vindas → licença → pasta de instalação → placa de vídeo → download do modelo → atalhos.
3. O instalador detecta (ou pergunta) qual placa de vídeo você tem e já baixa a versão certa do modelo Qwen automaticamente, com barra de progresso.
4. Ao final, é só marcar "Executar o Hermes AI agora" — pronto, sem terminal, sem configuração manual.

Não precisa ser administrador, a menos que você escolha instalar em `C:\Program Files` (aí o Windows pede elevação automaticamente).

**Para gerar esse instalador** (só quem for distribuir o Hermes precisa fazer isso):
```bash
# 1. Gere o executável (veja Opção C abaixo)
python build.py

# 2. Compile o instalador com o Inno Setup 6 (https://jrsoftware.org/isinfo.php)
ISCC.exe installer\HermesSetup.iss
```
O `.exe` final sai em `installer_output\Hermes-ia-Setup-<versão>.exe`.

### Opção B — Usar o Hermes-ia.exe manualmente (Windows 10/11)

Se você já tem uma pasta de distribuição (`Hermes-ia.exe`, `models/`, etc.) e prefere não usar o instalador:

1. Coloque o modelo `.gguf` em `models/hermes-core.gguf` (baixe um Qwen 7B–8B quantizado, ex.:
   `Qwen2.5-7B-Instruct-Q4_K_M.gguf`).
2. Dê duplo clique em `Hermes-ia.exe`.
3. A splash screen aparece enquanto o backend sobe (mínimo de 3s, timeout de 15s); quando tudo
   estiver pronto, a janela principal abre sozinha — sem terminal, sem navegador.
4. Para fechar, feche a janela normalmente: o backend e o `llama-server` (se o Hermes o iniciou)
   são encerrados junto.

**Atalhos (opcional):** rode `install.ps1` (botão direito → "Executar com PowerShell") para copiar
o app para `C:\Program Files\Hermes-ia\` e criar atalhos na Área de Trabalho e no Menu Iniciar. Ou,
mais simples: botão direito no `.exe` → "Criar atalho" e mova para onde quiser.

### Opção C — Buildar o .exe você mesmo

Pré-requisitos: **Windows 10/11**, **Python 3.10+**.

```bash
git clone https://github.com/felipesantoliver/hermes-ai.git
cd hermes-ai
pip install -r backend/requirements.txt
python build.py
```

`build.py` instala `pywebview`/`pyinstaller`/`pillow` (via `requirements-windows.txt`), gera
`icon.ico` automaticamente se não existir (`make_icon.py`), roda o PyInstaller com `--onefile
--windowed` e deixa o executável em `dist/Hermes-ia.exe`. Depois:

1. Copie `models/` (com o `.gguf`) para dentro de `dist/`.
2. Rode `dist/Hermes-ia.exe` e confirme que abre sem terminal.
3. Distribua a pasta `dist/` inteira, rode `install.ps1` de dentro dela, ou use o instalador gráfico (Opção A).

**Estrutura final de distribuição:**
```
Hermes-ia/
├── Hermes-ia.exe        (backend + frontend embutidos)
├── models/
│   └── hermes-core.gguf
├── data/                (criado automaticamente no 1º uso)
│   ├── hermes.db
│   ├── projects/
│   ├── loose/
│   └── logs/
└── README.md
```
`models/` fica fora do `.exe` de propósito — assim dá para trocar de modelo sem rebuildar.

### Opção D — Modo dev (backend + frontend soltos, qualquer SO)

1. **Configure o backend**
```bash
   cd backend
   python -m venv venv
   source venv/bin/activate   # Linux/Mac
   # .\venv\Scripts\activate no Windows
   pip install -r requirements.txt
```
2. **Configure o LLM** — baixe um Qwen 7B/8B quantizado, coloque em
   `backend/models/hermes-core.gguf` (ou ajuste `MODEL_PATH` em `config.py`), e suba o servidor:
```bash
   llama-server -m models/hermes-core.gguf --host 0.0.0.0 --port 8080
```
3. **Inicie o backend** (agora já serve o frontend embutido em `/`, não precisa de servidor
   HTTP separado para os arquivos estáticos):
```bash
   uvicorn main:app --host 127.0.0.1 --port 8000 --reload
```
4. Acesse `http://localhost:8000` no navegador.

### Configuração do Modo Engenheiro (opcional)

1. Baixe um modelo maior (ex.: Qwen 14B ou 32B) e coloque em `models/engineer/` (ou outro
   diretório de sua escolha).
2. No app, acesse **Configurações → Armazenamento**.
3. Preencha o caminho do arquivo `.gguf` ou a URL do servidor `llama.cpp` dedicado.
4. Clique em "Testar conexão" para verificar.
5. Ative o chip "Engineer" na barra de mensagens para usar o modelo maior.

---

## Troubleshooting (Windows)

| Problema | Solução |
|---|---|
| **"Windows protegeu seu computador" (SmartScreen)** | O executável (e o instalador) não são assinados digitalmente (assinatura de código paga). Clique em "Mais informações" → "Executar assim mesmo". Isso é esperado para apps não-assinados e não indica malware — mas só rode builds em que você confia na origem. |
| **Falta o Edge WebView2 Runtime** | O instalador gráfico detecta e oferece instalar automaticamente. Se estiver usando o `.exe` manualmente, baixe em https://developer.microsoft.com/microsoft-edge/webview2/ (Evergreen Bootstrapper). |
| **Download do modelo falhou no instalador** | Confira o log em `<pasta de instalação>\data\logs\installer_download.log`. Você pode rodar o instalador de novo (o BITS retoma sozinho) ou baixar o `.gguf` manualmente e colocá-lo em `models\hermes-core.gguf`. |
| **Porta 8000 ocupada** | Feche outro processo usando a porta (`netstat -ano \| findstr :8000` no cmd, depois `taskkill /PID <pid> /F`) ou feche outra instância do Hermes já aberta. |
| **"Modelo não encontrado"** | Confirme que o arquivo `.gguf` está exatamente em `models/hermes-core.gguf`, ao lado do `Hermes-ia.exe` (não dentro de uma subpasta extra). |
| **Janela abre em branco / erro de conexão** | O backend pode não ter subido a tempo (modelo muito grande carregando). Feche e abra de novo; se persistir, confira `data/logs/`. |
| **Quero ver logs/erros do backend** | Rode via `python main.py` num terminal (modo dev) em vez do `.exe` — aí os logs aparecem no próprio terminal. |

---

## Funcionalidades

| Funcionalidade | Descrição |
|---|---|
| 💬 Chat | Envio de mensagens com streaming SSE, fallback para resposta completa e anexos. |
| 📁 Projetos | CRUD completo; cada projeto possui instruções, persona, arquivos, escopo de memória e chats associados. |
| 🗂 Sidebar | Chats fixados, recentes, busca, menu de contexto (fixar, renomear, mover, arquivar, excluir). |
| 🖼 Galeria | Visualização em grid de todos os arquivos (usuário e sistema) com download/exclusão. |
| 👤 Perfil | Personalização do tom do Hermes (personalidade, entusiasmo, emojis, memória, etc.). |
| ⚙️ Configurações | Tema, idioma, notificações, limite de RAM, modo engenheiro (configuração e teste), ações destrutivas. |
| 🔍 Modo Analista | Verificação rigorosa com decomposição, múltiplos candidatos, juiz, ferramentas e checklists. |
| 🧠 Pensamento Visível | Exibição do raciocínio interno em tempo real (bloco expansível). |
| 🚀 Modo Engenheiro | Modelo local maior opcional para tarefas complexas, com integração ao modo Analista. |
| 📋 Planejamento multi-step | Geração automática de planos de ação para tarefas complexas, com progresso e replanejamento em caso de falha. |
| 🔧 Ferramentas | Execução segura de Python, shell, leitura de arquivos, busca, indexação, análise estática, compilação. |
| 🌐 Pesquisa Web | Ativação por chip "Web" — usa SearXNG local para enriquecer respostas com informações da internet. |
| 📊 Monitor | Medição contínua de RAM/CPU com pausa automática de ferramentas pesadas. |
| 📝 Logs | Auditoria de todas as execuções de tools, logs de conversa e do modo analista (JSONL). |
| 🛠️ Domínio Firmware | Agente especializado com ferramentas BLE e compilação PlatformIO. |
| 📱 Domínio Android | Agente especializado com ferramentas Gradle e validação de layouts. |
| 🖥️ App Windows nativo | `Hermes-ia.exe` — janela própria via pywebview/WebView2, sem terminal, com splash screen inteligente. |
| 🧙 Instalador gráfico | `Hermes-ia-Setup.exe` — detecção de GPU, download do modelo com progresso/retomada, atalhos automáticos, tudo em português. |

## Roadmap

✅ **MVP** — Backend FastAPI, SQLite, SPA vanilla, integração com LLM local, Agent Loop básico, memória em 3 camadas, classificador heurístico.

✅ **V1** — Modo Analista completo, streaming SSE, Pensamento Visível, classificador híbrido, monitor de recursos, notificações push, sandbox reforçado, testes automatizados.

✅ **V2** — Modo Engenheiro, RAG avançado, pesquisa web, planejamento multi-step, especialização por domínio, **empacotamento Windows (.exe)**.

✅ **V2.4** — Instalador gráfico para Windows via Inno Setup: detecção de GPU, seleção automática do modelo Qwen ideal, download com barra de progresso e retomada (BITS), verificação de espaço em disco e do WebView2 Runtime, atalhos automáticos — tudo em português do Brasil e sem exigir privilégios de administrador.

🔜 **Próximo** — pacote Linux, interface por voz (STT/TTS), assinatura de código para o `.exe` e para o instalador.

## Princípios Fundamentais

- **Local-first** — Nada depende de nuvem; dados e processamento permanecem na máquina do usuário.
- **Ferramentas > LLM** — O modelo nunca executa lógica crítica; tudo é delegado a ferramentas determinísticas.
- **Contexto mínimo necessário** — Memória compactada e priorizada para respeitar o orçamento de tokens.
- **Iteração contínua** — O agente refina a resposta com base em feedback real das ferramentas.
- **Sistema testável** — Componentes isolados e cobertos por testes.
- **Latência como moeda** — No modo Analista, qualidade é priorizada sobre velocidade.

## Hardware Alvo

| Componente | Especificação |
|---|---|
| CPU | AMD Ryzen 5 5500 |
| GPU | AMD RX 580 8GB (Vulkan) |
| RAM | 16 GB DDR4 |

Funciona em configurações mais modestas, ajustando o limite de RAM e o tamanho do modelo.

## Privacidade

- **100% local em uso** — Depois de instalado, nenhuma informação é enviada à internet, exceto se o usuário ativar explicitamente a busca web (via SearXNG local).
- **Internet só na instalação** — O instalador gráfico acessa a internet apenas para baixar o modelo de IA (Hugging Face) e, se necessário, o Microsoft Edge WebView2 Runtime. O `Hermes-ia.exe` em si já vem embutido no instalador, sem download adicional.
- **Controle total** — Chats, projetos e memórias podem ser apagados a qualquer momento.
- **Logs anônimos** — Registros de auditoria não contêm identificadores pessoais.

## Licença

MIT — veja o arquivo `LICENSE` para detalhes.

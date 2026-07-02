# Hermes AI

> **Versão atual:** v0.2.0-dev — *Hermes Core (Local Edition)*
> **Status:** 🚧 MVP concluído | 🟡 V1 em desenvolvimento | 🔵 V2 planejada

Assistente pessoal de IA **local-first**, focado em **gestão de projetos, engenharia de software e desenvolvimento técnico multi-domínio**.

O Hermes não é um chatbot — é um **sistema operacional de desenvolvimento assistido por IA**, onde o usuário constrói software, firmware e sistemas com suporte contínuo de um agente inteligente local.

---

## Sumário

1. [Visão geral do sistema](#1-visão-geral-do-sistema)
2. [Núcleo de Inteligência (LLM Core)](#2-núcleo-de-inteligência-llm-core)
3. [Arquitetura geral](#3-arquitetura-geral)
4. [Agent Loop (ciclo principal)](#4-agent-loop-ciclo-principal)
5. [Agentes lógicos](#5-agentes-lógicos-não-instâncias-de-llm)
6. [Sistema de Tools](#6-sistema-de-tools-execução-externa)
7. [Gestão de contexto e memória](#7-gestão-de-contexto-e-memória)
8. [Modo Analista](#8-modo-analista)
9. [Pensamento Visível](#9-pensamento-visível)
10. [Princípios fundamentais](#10-princípios-fundamentais)
11. [Hardware alvo](#11-hardware-alvo)
12. [Funcionalidades](#12-funcionalidades)
13. [Roadmap](#13-roadmap)
14. [Objetivo final](#14-objetivo-final)
15. [Privacidade](#15-privacidade)
16. [Hermes vs sistemas tradicionais](#16-hermes-vs-sistemas-tradicionais)

---

## 1. Visão geral do sistema

O Hermes é um ambiente de desenvolvimento onde:

- projetos são entidades vivas
- decisões são armazenadas
- código é iterado continuamente
- a IA atua como parte do time de engenharia

Ele combina:

- LLM local (núcleo de raciocínio)
- ferramentas executáveis (tools)
- memória estruturada por projeto
- agentes lógicos baseados em contexto

> O objetivo não é gerar respostas — é **resolver problemas de engenharia de forma contínua e incremental**.

---

## 2. Núcleo de Inteligência (LLM Core)

O Hermes utiliza um único modelo local da família **Qwen 7B–8B (quantizado)** como núcleo de inteligência.

### 🎯 Função do núcleo

O LLM **não** executa ações diretamente. Ele é responsável por:

- interpretação de intenção
- decomposição de problemas
- planejamento de execução
- geração de código
- decisão de uso de ferramentas
- coordenação de agentes lógicos

> O LLM é o "cérebro de decisão", não o executor.

### ⚙️ Características do modelo

| Característica | Valor |
|---|---|
| Classe | 7B–8B parâmetros |
| Execução | Local (llama.cpp / Vulkan) |
| Quantização | Q4–Q5 (Q6/Q8 opcional no modo analista) |
| Otimização | Instruções e tool use |
| Foco | Engenharia + código + raciocínio geral |

### 🧩 Limitações assumidas

O sistema assume explicitamente que o núcleo tem limitações:

- capacidade limitada em raciocínio profundo multi-etapas
- inconsistência em projetos muito longos
- necessidade de validação externa via tools
- não confiabilidade em execução direta de lógica

Essas limitações são corrigidas por arquitetura.

---

## 3. Arquitetura geral

O Hermes segue uma arquitetura baseada em separação de responsabilidades:
Usuário
↓
Interface (texto/voz)
↓
Orquestrador
↓
Classificador de intenção (híbrido: embeddings + heurística)
↓
Seleção de agente lógico
↓
LLM Core (Qwen 7B/8B) ← ou modelo engenheiro opcional
↓
Tools (execução real, sandbox)
↓
Memória em 3 camadas + RAG
↓
Resposta final (com streaming e pensamento visível opcionais)

text

---

## 4. Agent Loop (ciclo principal)

O sistema opera em ciclos iterativos:

1. Interpretar entrada
2. Planejar ação
3. Executar (LLM ou tool)
4. Observar resultado
5. Corrigir ou finalizar

### 🔥 Propriedades do loop

- pode iterar múltiplas vezes
- valida resultados com tools
- reduz alucinação via feedback real
- transforma o LLM em sistema "testável"
- no modo analista, o loop é intensificado (até 12 iterações, múltiplos candidatos, auto-crítica, juiz, checklists)

---

## 5. Agentes lógicos (não instâncias de LLM)

Os agentes são **configurações de comportamento**, não modelos separados.

Cada agente é definido por:

- system prompt especializado
- conjunto de tools disponíveis
- recorte de contexto
- regras de atuação

### 📌 Exemplos de agentes

| Agente | Responsabilidade |
|---|---|
| Orquestrador | Coordena decisões e fluxo geral |
| Arquiteto | Estrutura sistemas e módulos |
| Desenvolvedor | Implementa e refatora código |
| Firmware | Baixo nível, registradores, BLE |
| Revisor | Valida qualidade e segurança |
| Analista (modo) | Loop rigoroso de verificação multi-etapa |
| Engenheiro (modo) | Usa modelo maior opcional com menos iterações |
| Android | Desenvolvimento Android (Kotlin/Java) |

### 🔄 Troca de agente

- não recarrega modelo
- não reinicializa contexto global
- apenas altera prompt + tools

> Isso garante fluidez e baixo custo computacional.

---

## 6. Sistema de Tools (execução externa)

O Hermes delega execução real para ferramentas locais.

### 📌 Princípio central

> O LLM nunca deve ser fonte de verdade computacional.

### 🧰 Tools principais

- execução de código (sandbox Python / C / shell, 128MB, sem rede, timeout)
- leitura de arquivos e projetos
- parsing de PDFs (datasheets)
- busca web (SearXNG local)
- compilação de firmware (PlatformIO)
- análise de logs
- cálculo simbólico (SymPy)
- verificação de segurança (Bandit, ShellCheck)
- indexação de código (FAISS + embeddings)
- WebSearchTool (SearXNG local)

### 📤 Contrato de tools

Toda tool deve:

- retornar dados estruturados (JSON ou Markdown limpo)
- nunca retornar texto ambíguo
- sempre incluir erros explicitamente
- ser determinística sempre que possível

---

## 7. Gestão de contexto e memória

O contexto é tratado como **recurso crítico e limitado**.

### 🧩 Estrutura de memória

**1. Memória arquitetural** (alta prioridade)
- decisões de design
- padrões adotados
- escolhas técnicas

**2. Memória de código**
- indexação por arquivo/função
- rastreabilidade de mudanças
- RAG semântico com embeddings (FAISS)

**3. Memória conversacional**
- resumida continuamente
- não preserva histórico bruto

### 🔄 Estratégia de compressão

- resumos incrementais automáticos
- eliminação de redundância
- preservação de decisões críticas

### 🔎 Recuperação

- baseada em contexto ativo
- busca semântica (RAG) para código e documentos
- priorização por relevância técnica
- reranking cross-encoder

---

## 8. Modo Analista

O **Modo Analista** é a principal inovação da V1. Ele troca latência por qualidade, aplicando um processo rigoroso de verificação antes de entregar qualquer resposta, usando **o mesmo modelo Qwen 7B-8B**, sem depender de hardware extra.

### Estratégias combinadas

- **Decomposição de tarefa**: quebra o problema em subtarefas independentes
- **Self-consistency (voto)**: gera 3 candidatos com temperatura alta e escolhe o melhor
- **Self-refine (crítica)**: cada candidato é atacado pelo próprio modelo
- **Debate interno**: simulação Arquiteto vs Revisor
- **Verificação obrigatória por tools**: código só é aceito se passar em execução real
- **Checklists de domínio**: biblioteca de padrões (segurança, arquitetura, firmware)
- **Orçamento de raciocínio**: mais iterações e scratchpad interno ilimitado

### Ativação

- Chip "Analista" na interface
- Automático para perfis de alto rigor (personalidade "técnico", filtro de conteúdo 3+)

---

## 9. Pensamento Visível

Na V1, o usuário pode ativar a exibição do raciocínio interno do Hermes diretamente no chat, no estilo DeepSeek/Claude.

- Bloco expansível acima da resposta final
- Preenchido em tempo real via streaming SSE
- Mostra decomposição, geração de candidatos, críticas, decisão do juiz, resultados de tools
- Controlado por toggle na interface e salvo no perfil

---

## 10. Princípios fundamentais

- **Local-first** — nada depende de nuvem
- **Determinístico sempre que possível**
- **Ferramentas > raciocínio do LLM**
- **Contexto mínimo necessário**
- **Iteração contínua**
- **Sistema testável, não "mágico"**
- **Latência como moeda de troca por qualidade (modo analista)**
- **Modelo maior é opcional, nunca obrigatório**

---

## 11. Hardware alvo

| Componente | Especificação |
|---|---|
| CPU | AMD Ryzen 5 5500 |
| GPU | AMD RX 580 8GB (Vulkan) |
| RAM | 16GB DDR4 |

> O sistema foi projetado sob restrição real de hardware, não como arquitetura teórica ilimitada.

---

## 12. Funcionalidades

### 🎙️ Interface por voz
- comandos por voz
- respostas faladas (streaming)
- interação contínua

### 📁 Projetos com contexto
- projetos isolados
- histórico técnico persistente
- evolução incremental

### 💻 Desenvolvimento assistido
- geração de código
- refatoração
- debugging com execução real
- modo analista para qualidade máxima

### 🧠 Memória local
- decisões armazenadas
- padrões aprendidos
- recuperação contextual
- RAG semântico para código e documentos

### 🔎 Modo pesquisa
- busca web sob demanda (SearXNG local)
- integração com contexto local

### 📚 Base de conhecimento
- documentos
- notas técnicas
- referências externas

### 🧪 Modo Analista
- múltiplos candidatos, auto-crítica, juiz
- verificação obrigatória por tools
- checklists de qualidade por domínio
- pensamento visível opcional

### ⚙️ Modo Engenheiro (V2, opcional)
- segundo modelo local maior (configurável)
- fallback automático para o padrão se indisponível

### 🌐 Domínios especializados (V2)
- Firmware (BLE, registradores, PlatformIO)
- Android (Kotlin/Java, Gradle)

### 📊 Streaming e pensamento visível (V1)
- resposta token a token via SSE
- raciocínio interno exibido em tempo real

---

## 13. Roadmap

### ✅ MVP (fundação do sistema)
- [x] backend FastAPI
- [x] agent loop funcional
- [x] sistema de tools confiável
- [x] orquestração simples (heurística)
- [x] contexto mínimo funcional
- [x] integração com ambiente local
- [x] SQLite + schemas (projetos, chats, mensagens, perfil, arquivos)
- [x] Navegação SPA (chat, projetos, sidebar, busca)
- [x] Chat funcional (LLM real, anexos, tools, agent loop)
- [x] Memória em 3 camadas + Galeria de arquivos
- [x] Perfil completo com persistência e aplicação no LLM
- [x] Configurações (ações destrutivas, notificações, RAM, esfera reativa)

### 🟡 V1 (sistema utilizável — em desenvolvimento)
- [ ] Modo Analista (agente revisor obrigatório, self-consistency, checklists)
- [ ] Classificador híbrido de intenção (embeddings + heurística)
- [ ] Streaming SSE (resposta em tempo real)
- [ ] Pensamento visível no chat (transparent reasoning)
- [ ] Melhoria de tools e sandbox seguro (WebSearch, indexação, segurança)
- [ ] Controle de recursos (RAM/CPU) e notificações de sistema

### 🔵 V2 (sistema avançado — planejada)
- [ ] Modo Engenheiro (modelo maior opcional)
- [ ] RAG avançado para código (FAISS + embeddings)
- [ ] Planejamento multi-step explícito
- [ ] Especialização por domínio (BLE, firmware, Android)
- [ ] Galeria integrada com RAG

### 📦 Empacotamento
- [ ] instalador local (.exe / Linux package)
- [ ] backend + frontend integrados
- [ ] setup automatizado

---

## 14. Objetivo final

O Hermes não é um assistente de perguntas.

É um sistema onde:

> Você constrói software junto com uma IA local, contínua e operacional.

---

## 15. Privacidade

- execução 100% local por padrão
- nenhum envio obrigatório de dados
- controle total de memória e contexto

---

## 16. Hermes vs sistemas tradicionais

| Característica | Hermes | Assistentes comuns |
|---|---|---|
| Execução | Local | Cloud |
| Memória | Estruturada por projeto | Limitada |
| Ferramentas | Profundas e locais | Limitadas |
| Foco | Engenharia contínua | Respostas |
| Controle | Total | Parcial |
| Modo Analista | Sim (qualidade por iteração) | Não |
| Pensamento visível | Sim (opcional) | Limitado |
| Streaming | Sim (SSE) | Sim |
| Modelo engenheiro | Opcional, local | N/A (cloud) |

---

## 👨‍💻 Autor

**Felipe Sant'Oliver**

---

## 📄 Licença

MIT

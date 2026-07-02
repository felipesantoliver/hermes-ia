# Hermes AI

> **Versão atual:** `v0.1.0` — *Hermes Core (Local Edition)*
> **Status:** 🧪 Planejamento inicial (MVP ainda não iniciado)

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
8. [Princípios fundamentais](#8-princípios-fundamentais)
9. [Hardware alvo](#9-hardware-alvo)
10. [Funcionalidades](#10-funcionalidades)
11. [Roadmap](#11-roadmap)
12. [Objetivo final](#12-objetivo-final)
13. [Privacidade](#13-privacidade)
14. [Hermes vs sistemas tradicionais](#14-hermes-vs-sistemas-tradicionais)

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
| Quantização | Q4–Q5 |
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

```
Usuário
  ↓
Interface (texto/voz)
  ↓
Orquestrador
  ↓
Classificador de intenção
  ↓
Seleção de agente lógico
  ↓
LLM Core (Qwen 7B/8B)
  ↓
Tools (execução real)
  ↓
Memória + contexto
  ↓
Resposta final
```

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

- execução de código (sandbox Python / C / shell)
- leitura de arquivos e projetos
- parsing de PDFs (datasheets)
- busca web (SearXNG local)
- compilação de firmware
- análise de logs
- cálculo simbólico (SymPy)

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

**3. Memória conversacional**
- resumida continuamente
- não preserva histórico bruto

### 🔄 Estratégia de compressão

- resumos incrementais automáticos
- eliminação de redundância
- preservação de decisões críticas

### 🔎 Recuperação

- baseada em contexto ativo
- busca semântica (RAG futuro)
- priorização por relevância técnica

---

## 8. Princípios fundamentais

- **Local-first** — nada depende de nuvem
- **Determinístico sempre que possível**
- **Ferramentas > raciocínio do LLM**
- **Contexto mínimo necessário**
- **Iteração contínua**
- **Sistema testável, não "mágico"**

---

## 9. Hardware alvo

| Componente | Especificação |
|---|---|
| CPU | AMD Ryzen 5 5500 |
| GPU | AMD RX 580 8GB (Vulkan) |
| RAM | 16GB DDR4 |

> O sistema foi projetado sob restrição real de hardware, não como arquitetura teórica ilimitada.

---

## 10. Funcionalidades

### 🎙️ Interface por voz
- comandos por voz
- respostas faladas
- interação contínua

### 📁 Projetos com contexto
- projetos isolados
- histórico técnico persistente
- evolução incremental

### 💻 Desenvolvimento assistido
- geração de código
- refatoração
- debugging com execução real

### 🧠 Memória local
- decisões armazenadas
- padrões aprendidos
- recuperação contextual

### 🔎 Modo pesquisa
- busca web sob demanda
- integração com contexto local

### 📚 Base de conhecimento
- documentos
- notas técnicas
- referências externas

---

## 11. Roadmap

### 🚧 MVP (fundação do sistema)
- [ ] backend FastAPI
- [ ] agent loop funcional
- [ ] sistema de tools confiável
- [ ] orquestração simples (heurística)
- [ ] contexto mínimo funcional
- [ ] integração com ambiente local

### 🟡 V1 (sistema utilizável)
- [ ] classificador híbrido de intenção
- [ ] memória em camadas
- [ ] agente revisor obrigatório
- [ ] controle de recursos (RAM/CPU)
- [ ] feedback em tempo real
- [ ] melhoria de tools

### 🔵 V2 (sistema avançado)
- [ ] modo engenheiro (modelo maior opcional)
- [ ] RAG avançado para código
- [ ] planejamento multi-step explícito
- [ ] especialização por domínio (BLE, firmware, Android)

### 📦 Empacotamento
- [ ] instalador local (.exe / Linux package)
- [ ] backend + frontend integrados
- [ ] setup automatizado

---

## 12. Objetivo final

O Hermes não é um assistente de perguntas.

É um sistema onde:

> Você constrói software junto com uma IA local, contínua e operacional.

---

## 13. Privacidade

- execução 100% local por padrão
- nenhum envio obrigatório de dados
- controle total de memória e contexto

---

## 14. Hermes vs sistemas tradicionais

| Característica | Hermes | Assistentes comuns |
|---|---|---|
| Execução | Local | Cloud |
| Memória | Estruturada por projeto | Limitada |
| Ferramentas | Profundas e locais | Limitadas |
| Foco | Engenharia contínua | Respostas |
| Controle | Total | Parcial |

---

## 👨‍💻 Autor

**Felipe Sant'Oliver**

---

## 📄 Licença

MIT

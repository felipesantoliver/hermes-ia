# Hermes AI

> **Versão atual:** `v0.1.0` — *Hermes Core (Local Edition)*
> **Status:** 🧪 Planejamento inicial (MVP ainda não iniciado)

Assistente pessoal de IA **local-first**, focado em **gestão de projetos, tarefas e programação multi-linguagem**.
Leve, direto e pensado para acompanhar o fluxo real de desenvolvimento — com suporte a **comandos de voz** e interação natural.

---

## 🧠 Visão geral

Hermes é um ambiente onde você **organiza, constrói e evolui projetos com ajuda de IA**, tudo rodando localmente.
A proposta não é ser só um chat inteligente — é ser uma ferramenta de trabalho contínuo.

Por trás da interface simples, Hermes funciona como um **time de agentes especializados** (arquiteto, desenvolvedor, revisor) atuando sobre um único modelo local — sem multiplicar o custo computacional a cada nova capacidade.

> Cada projeto funciona como um contexto vivo: com tarefas, decisões, código e aprendizado acumulado.

---

## ⚙️ Princípios

* **Local-first** — seus dados ficam com você
* **Leve** — sem overhead desnecessário, pensado para hardware doméstico
* **Contextual** — entende o estado do projeto
* **Prático** — feito para uso real no dia a dia
* **Natural** — interação por texto e voz

---

## 🖥️ Hardware alvo

Hermes é desenvolvido e testado para rodar de forma fluida em hardware de entrada:

* **CPU:** AMD Ryzen 5 5500 (6 núcleos / 12 threads)
* **GPU:** AMD Radeon RX 580 8GB (Vulkan, sem ROCm)
* **RAM:** 16GB DDR4

Toda decisão técnica do projeto respeita essa restrição — dependências pesadas e uso de memória são tratados como recurso escasso, não como commodity.

---

## 🚀 Funcionalidades

### 🎙️ Interface por voz

* Envio de comandos por voz
* Respostas faladas pela IA
* Interação contínua sem precisar digitar
* Ideal para:

  * brainstorming rápido
  * revisão de código
  * organização de tarefas
  * aquela vibe "JARVIS"

---

### 📁 Projetos com contexto

* Organização por projetos independentes
* Cada projeto mantém:

  * contexto técnico
  * decisões importantes
  * histórico de evolução
* Separação clara entre diferentes ideias e sistemas

---

### ✅ Gestão de tarefas integrada

* Criação de tarefas dentro do projeto
* Organização simples (todo / doing / done)
* Sugestão de próximas ações com base no contexto
* Suporte a subtarefas e refinamento iterativo

---

### 💻 Programação multi-linguagem

* Geração e explicação de código
* Suporte a múltiplas linguagens
* Refatoração e debugging assistido
* Execução local (sandbox leve)

---

### 🧠 Memória local e contínua

* Registro automático de:

  * decisões técnicas
  * padrões usados
  * preferências
* Memória organizada em camadas — decisões arquiteturais são preservadas com prioridade, código é indexado por arquivo/função, e o histórico de conversa é resumido de forma incremental
* Recuperação inteligente durante o desenvolvimento
* Sem dependência de serviços externos

---

### 🔎 Modo pesquisa

* Busca na internet quando necessário
* Complementa o conhecimento local da IA
* Ativado sob demanda / comando (não intrusivo)

---

### 📚 Área de contexto / aprendizado

* Espaço para adicionar:

  * anotações
  * referências
  * documentação
* A IA utiliza esse conteúdo como base de conhecimento
* Funciona como um "cérebro auxiliar" do projeto

---

### 🤖 Otimização de agentes

* Agentes como **perfis lógicos** (system prompt + ferramentas) sobre um único modelo carregado, não instâncias separadas de LLM
* Execução apenas quando necessário
* Foco em reduzir custo computacional e complexidade
* Respostas mais diretas e úteis

---

## 🗺️ Roadmap

O desenvolvimento segue a ordem **MVP → V1 → V2**, priorizando estabilidade antes de sofisticação.

### 🚧 MVP — a base tem que funcionar

* [ ] Estrutura inicial do backend (FastAPI)
* [ ] Loop de agente (pensar → agir → observar)
* [ ] Sistema de ferramentas isolado e confiável
* [ ] Orquestrador simples (roteamento por heurística, com fallback seguro)
* [ ] Gerenciamento de contexto com truncamento inteligente
* [ ] Integração com o ambiente de desenvolvimento real

### 🟡 V1 — fica bom de usar

* [ ] Classificador de intenção híbrido (heurística + LLM leve)
* [ ] Memória em camadas (decisões / código / conversa)
* [ ] Agente Revisor obrigatório
* [ ] Controle de recursos (RAM/CPU, lazy load)
* [ ] Feedback de execução em tempo real na interface

### 🔵 V2 — escala e diferencial

* [ ] Modo Engenheiro — modelo de código maior via troca controlada de modelo (cold swap)
* [ ] RAG avançado (embeddings especializados em código)
* [ ] Planejamento multi-step explícito
* [ ] Especialização por domínio (firmware, BLE, Android etc.)

### 📦 Empacotamento

* [ ] Executável `.exe` para Windows e e Linux (backend + frontend embutidos na pasta + executavel)

---

## 🎯 Objetivo

Criar uma ferramenta onde:

> você não gerencia projetos *separado* da IA —
> você desenvolve **junto com ela**, de forma contínua, inclusive por voz.

---

## 🔐 Privacidade

* Execução local por padrão
* Nenhum envio obrigatório de dados
* Controle total sobre memória e armazenamento

---

## 🧭 Hermes vs Solaris

| Característica | Hermes                     | Solaris          |
| -------------- | -------------------------- | ---------------- |
| Execução       | Local                      | Cloud            |
| Foco           | Projetos e desenvolvimento | Assistente geral |
| Interface      | Texto + Voz                | Texto            |
| Privacidade    | Total                      | Parcial          |
| Complexidade   | Baixa                      | Alta             |

---

Este projeto faz parte de uma série de estudos focados em Vibe Coding que estou realizando, explorando desenvolvimento prático, iteração rápida e construção orientada à experiência.

Sinta-se à vontade para contribuir com sugestões, melhorias ou novas funcionalidades, toda colaboração é bem-vinda!

## 👨‍💻 Autor

**Felipe Sant'Oliver**

---

## 📄 Licença

MIT

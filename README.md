# 🏠 Syndra Agent — IA para Condomínios

> Agente de IA para gestão condominial via WhatsApp, com memória persistente no Supabase e deploy em VPS.

---

## 📁 Estrutura do Projeto

```
syndra-agent/
├── specs/                          # Especificações técnicas (SandeClaw-style)
│   ├── 01-persona.md               # Identidade e persona da Syndra
│   ├── 02-capabilities.md          # Capacidades e escopo de atuação
│   ├── 03-knowledge-base.md        # Base de conhecimento e RAG
│   ├── 04-flows.md                 # Fluxos de conversa e decisão
│   ├── 05-integrations.md          # WhatsApp + Supabase + APIs
│   ├── 06-security.md              # Segurança e privacidade
│   └── 07-deployment.md            # Deploy em VPS
├── src/
│   ├── agent/                      # Núcleo do agente (LangChain/CrewAI)
│   │   ├── syndra.py                 # Agente principal
│   │   ├── prompts.py              # System prompts
│   │   ├── tools.py                # Ferramentas do agente
│   │   └── memory.py               # Gerenciamento de memória
│   ├── whatsapp/                   # Integração WhatsApp (Evolution API)
│   │   ├── webhook.py              # Receber mensagens
│   │   ├── sender.py               # Enviar mensagens
│   │   └── media.py                # Áudio, imagens, docs
│   ├── supabase/                   # Camada de dados
│   │   ├── client.py               # Conexão Supabase
│   │   ├── schema.sql              # Schema do banco
│   │   └── repositories/           # CRUD por entidade
│   └── api/                        # FastAPI (servidor HTTP)
│       ├── main.py                 # Entrada da aplicação
│       └── routes/                 # Endpoints REST
├── config/
│   ├── .env.example                # Variáveis de ambiente
│   └── settings.py                 # Configurações da aplicação
├── scripts/
│   ├── setup_vps.sh                # Setup automático na VPS
│   └── seed_knowledge.py           # Popular base de conhecimento
├── docs/
│   └── architecture.md             # Diagrama de arquitetura
├── docker-compose.yml              # Orquestração de containers
├── Dockerfile                      # Imagem da aplicação
└── requirements.txt                # Dependências Python
```

---

## 🚀 Stack Tecnológica

| Camada | Tecnologia |
|---|---|
| IA/Agente | OpenRouter / OpenAI / Gemini |
| Orquestração | LangChain |
| WhatsApp | Evolution API v2 |
| Banco de Dados | Supabase (PostgreSQL + pgvector) |
| API Server | FastAPI + Uvicorn |
| Deploy | Docker + Nginx (VPS Ubuntu 22.04) |
| Filas | Redis (mensagens assíncronas) |

---

## ⚡ Início Rápido

```bash
# 1. Clonar repositório
git clone <repo> && cd syndra-agent

# 2. Configurar variáveis de ambiente
cp config/.env.example .env && nano .env

# 3. Deploy completo na VPS
chmod +x scripts/setup_vps.sh && ./scripts/setup_vps.sh

# 4. Popular base de conhecimento
python scripts/seed_knowledge.py
```

---

## 📚 Documentação Técnica

Todas as especificações técnicas estão na pasta `/specs`.
Leia na ordem numérica para entendimento completo do sistema.

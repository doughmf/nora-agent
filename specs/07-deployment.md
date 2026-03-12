# SPEC-07: Deployment — Deploy em VPS

**Versão:** 1.0  
**Status:** Aprovado

---

## 1. REQUISITOS DA VPS

| Recurso | Mínimo | Recomendado |
|---|---|---|
| OS | Ubuntu 22.04 LTS | Ubuntu 22.04 LTS |
| CPU | 2 vCPUs | 4 vCPUs |
| RAM | 4 GB | 8 GB |
| Disco | 40 GB SSD | 80 GB SSD |
| Banda | 100 Mbps | 1 Gbps |
| IP | 1 IP fixo | 1 IP fixo |

**Providers sugeridos:** Hetzner (melhor custo-benefício), DigitalOcean, Vultr, Contabo

---

## 2. DEPLOY COM EASYPANEL

O deploy será feito de forma visual usando o Easypanel (um painel Docker moderno).

### Passo 1: Instalar o Easypanel na VPS
Acesse a VPS via SSH (como root) e execute o comando oficial:
```bash
curl -sSL https://get.easypanel.io | sh
```
Acesse `http://<IP-DA-VPS>:3000` no navegador e configure sua senha de administrador.

### Passo 2: Criar o Projeto
1. Dentro do Easypanel, clique em **Create Project**.
2. Dê o nome de `nora-agent`.

### Passo 3: Adicionar a Aplicação (via Compose)
A forma mais fácil de rodar todo o sistema de uma vez é usando o Docker Compose nativo do repositório no Easypanel.
1. Acesse seu projeto `nora-agent`.
2. Clique em **Services** -> **New Service**.
3. Escolha **App** ou **Compose**. Sugerimos **Compose** para subir os 3 serviços (Nora, Redis, Evolution) simultaneamente colando o seu arquivo `docker-compose.yml`.

Caso prefira deploy individual por Serviço do tipo "App", você criará:
1. **Redis**: Use o template *Redis* do Easypanel.
2. **Evolution API**: Crie um App a partir da imagem Docker `atendai/evolution-api:v2.2.3`.
3. **Nora Agent**: Crie um App e conecte ao repositório GitHub (opção App -> GitHub) apontando para o seu `Dockerfile`.

### Passo 4: Configurar Variáveis de Ambiente
No Easypanel, vá até a aba **Environment** do serviço e cole as chaves do seu `.env.example`.

### Passo 5: Configurar Domínios
O Easypanel traz Traefik integrado que gerencia HTTPS/SSL automaticamente.
Vá na aba **Domains** do aplicativo e adicione:
- `api.seu-dominio.com` apontando para a porta 8080 (Evolution API)
- `nora.seu-dominio.com` apontando para a porta 8000 (Nora FastAPI)

E clique em **Save**. O SSL será provisionado.

---

## 3. DOCKER COMPOSE COMPLETO

```yaml
# docker-compose.yml
version: '3.8'

services:
  # ─── Aplicação Nora ─────────────────────────
  nora-app:
    build: .
    container_name: nora_app
    restart: always
    ports:
      - "8000:8000"
    environment:
      - OPENROUTER_API_KEY=${OPENROUTER_API_KEY}
      - OPENAI_API_KEY=${OPENAI_API_KEY}
      - GEMINI_API_KEY=${GEMINI_API_KEY}
      - SUPABASE_URL=${SUPABASE_URL}
      - SUPABASE_SERVICE_KEY=${SUPABASE_SERVICE_KEY}
      - EVOLUTION_API_URL=http://evolution-api:8080
      - EVOLUTION_API_KEY=${EVOLUTION_API_KEY}
      - EVOLUTION_INSTANCE=${EVOLUTION_INSTANCE}
      - REDIS_URL=redis://redis:6379
    depends_on:
      - redis
      - evolution-api
    volumes:
      - ./knowledge_docs:/app/knowledge_docs
      - ./logs:/app/logs
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8000/health"]
      interval: 30s
      timeout: 10s
      retries: 3

  # ─── Evolution API (WhatsApp) ───────────────
  evolution-api:
    image: atendai/evolution-api:v2.2.3
    container_name: evolution_api
    restart: always
    ports:
      - "8080:8080"
    environment:
      - SERVER_URL=https://${DOMAIN}
      - AUTHENTICATION_API_KEY=${EVOLUTION_API_KEY}
      - WEBHOOK_GLOBAL_URL=https://${DOMAIN}/webhook/whatsapp
      - WEBHOOK_GLOBAL_ENABLED=true
      - WEBHOOK_EVENTS_MESSAGES_UPDATE=true
      - STORE_MESSAGES=true
      - STORE_MESSAGE_UP=true
    volumes:
      - evolution_data:/evolution/instances

  # ─── Redis (Fila de mensagens) ──────────────
  redis:
    image: redis:7-alpine
    container_name: nora_redis
    restart: always
    command: redis-server --appendonly yes --requirepass ${REDIS_PASSWORD}
    volumes:
      - redis_data:/data

volumes:
  evolution_data:
  redis_data:
```

---

## 4. DOCKERFILE

```dockerfile
# Dockerfile
FROM python:3.11-slim

WORKDIR /app

# Instalar dependências do sistema
RUN apt-get update && apt-get install -y \
    gcc \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Instalar dependências Python
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copiar código
COPY src/ ./src/
COPY config/ ./config/
COPY scripts/ ./scripts/

# Usuário não-root
RUN useradd -m -u 1000 nora && chown -R nora:nora /app
USER nora

EXPOSE 8000

CMD ["uvicorn", "src.api.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "2"]
```

---

## 5. REQUIREMENTS.TXT

```txt
# requirements.txt
openai==1.55.0         # Para embeddings e interações via OpenRouter
google-genai==0.3.0    # SDK Oficial do Gemini
fastapi==0.115.0
uvicorn[standard]==0.32.0
supabase==2.10.0
httpx==0.27.2
redis==5.2.0
python-dotenv==1.0.1
pdfplumber==0.11.4
pdfplumber==0.11.4
numpy==1.26.4
pydantic==2.10.0
pydantic-settings==2.6.0
```

---

## 6. MONITORAMENTO E MANUTENÇÃO

```bash
# Ver logs em tempo real
docker logs -f nora_app

# Reiniciar serviços pelo Easypanel
No dashboard do Easypanel -> Seu Serviço -> botão "Restart".

# Ver status da aplicação e logs
Logs estão disponíveis de forma visual na aba "Logs" dentro de cada serviço no painel.

# Atualizar aplicação
Se conectado por GitHub, clique no botão "Deploy" do menu lateral na interface ou configure Webhooks para auto-deploy a cada `git push`.

# Backup do banco (via Supabase Dashboard)
# Supabase faz backup automático diário — verificar no painel

# Verificar uso de recursos
docker stats
```

---

## 7. CHECKLIST DE GO-LIVE

```
PRÉ-DEPLOY:
□ VPS configurada com Ubuntu 22.04 e Easypanel instalado (`curl -sSL https://get.easypanel.io | sh`)
□ Domínio apontado para o Easypanel Server
□ Variáveis preenchidas na aba Environment do painel
□ PDFs do regimento disponíveis

DEPLOY:
□ Repositório importado no painel via "App" ou "Compose"
□ Todos os serviços com indicador visual verde (Running)
□ Abas "Domain" configuradas e HTTPS ativo automaticamente via Traefik
□ Webhook da Evolution API configurado com o novo domínio
□ Base de conhecimento populada via botão de exec no painel ou via rota segura webhook

PÓS-DEPLOY:
□ Testar onboarding com número novo
□ Testar fluxo de manutenção
□ Testar reserva de espaço
□ Testar broadcast de aviso
□ Testar detecção de emergência
□ Verificar logs sem erros (docker logs nora_app)
□ Confirmar que síndico recebe notificações urgentes
□ Enviar mensagem de apresentação no grupo do condomínio
```

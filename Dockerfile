FROM python:3.11-slim

WORKDIR /app

# Dependências do sistema
RUN apt-get update && apt-get install -y \
    gcc \
    libpq-dev \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Instalar dependências Python
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copiar código
COPY src/ ./src/
COPY config/ ./config/
COPY scripts/ ./scripts/

# Criar diretórios necessários
RUN mkdir -p /app/knowledge_docs /app/logs

# Usuário não-root
RUN useradd -m -u 1000 syndra && chown -R syndra:syndra /app
USER syndra

EXPOSE 8000

CMD ["uvicorn", "src.api.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "2"]

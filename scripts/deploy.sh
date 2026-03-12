#!/bin/bash
# =====================================================
# deploy.sh — Deploy da Syndra Agent na VPS
# Uso: bash deploy.sh
# =====================================================

set -e

PROJECT_DIR="/opt/syndra-agent"
REPO_DIR="$(cd "$(dirname "$0")" && pwd)"

echo "🚀 Iniciando deploy da Syndra Agent..."
echo "📁 Diretório: $PROJECT_DIR"

# Cria diretório do projeto se não existir
mkdir -p "$PROJECT_DIR/knowledge_docs"
mkdir -p "$PROJECT_DIR/logs"

# Copia arquivos (excluindo arquivos desnecessários)
rsync -av --exclude='.git' \
  --exclude='__pycache__' \
  --exclude='*.pyc' \
  --exclude='.env' \
  "$REPO_DIR/" "$PROJECT_DIR/"

echo "📦 Arquivos copiados."

# Entra no diretório do projeto
cd "$PROJECT_DIR"

# Para container existente se estiver rodando
docker compose down 2>/dev/null || true

# Build e sobe os containers
echo "🐳 Fazendo build e subindo containers..."
docker compose up -d --build

# Aguarda health check
echo "⏳ Aguardando servidor iniciar..."
sleep 10

# Verifica se está rodando
if curl -sf http://localhost:8000/health > /dev/null; then
  echo "✅ Syndra Agent está rodando!"
  curl -s http://localhost:8000/health | python3 -m json.tool
else
  echo "❌ Servidor não respondeu. Verificando logs..."
  docker compose logs syndra-app --tail=30
fi

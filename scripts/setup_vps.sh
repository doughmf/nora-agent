#!/bin/bash
# scripts/setup_vps.sh
# Execute como root na VPS zerada

set -e  # Parar em caso de erro

echo "🚀 Iniciando setup do Syndra Agent..."

# ──────────────────────────────────────
# 1. ATUALIZAR SISTEMA
# ──────────────────────────────────────
apt update && apt upgrade -y
apt install -y curl wget git nano ufw htop fail2ban

# ──────────────────────────────────────
# 2. INSTALAR DOCKER
# ──────────────────────────────────────
curl -fsSL https://get.docker.com | sh
systemctl enable docker
systemctl start docker

# Instalar Docker Compose
curl -L "https://github.com/docker/compose/releases/latest/download/docker-compose-$(uname -s)-$(uname -m)" \
    -o /usr/local/bin/docker-compose
chmod +x /usr/local/bin/docker-compose

echo "✅ Docker instalado: $(docker --version)"

# ──────────────────────────────────────
# 3. INSTALAR NGINX
# ──────────────────────────────────────
apt install -y nginx certbot python3-certbot-nginx
systemctl enable nginx

# ──────────────────────────────────────
# 4. CONFIGURAR FIREWALL (UFW)
# ──────────────────────────────────────
ufw default deny incoming
ufw default allow outgoing
ufw allow ssh
ufw allow 80/tcp    # HTTP
ufw allow 443/tcp   # HTTPS
ufw allow 8080/tcp  # Evolution API (temporário, remover após configurar Nginx)
ufw --force enable

echo "✅ Firewall configurado"

# ──────────────────────────────────────
# 5. CONFIGURAR FAIL2BAN
# ──────────────────────────────────────
cat > /etc/fail2ban/jail.local << 'EOF'
[DEFAULT]
bantime = 3600
findtime = 600
maxretry = 5

[sshd]
enabled = true
EOF
systemctl restart fail2ban

# ──────────────────────────────────────
# 6. CLONAR REPOSITÓRIO
# ──────────────────────────────────────
git clone https://github.com/seu-usuario/syndra-agent.git /opt/syndra-agent
cd /opt/syndra-agent

# ──────────────────────────────────────
# 7. CONFIGURAR VARIÁVEIS DE AMBIENTE
# ──────────────────────────────────────
cp config/.env.example .env
echo ""
echo "⚠️  ATENÇÃO: Edite o arquivo .env antes de continuar!"
echo "   nano /opt/syndra-agent/.env"
echo ""
read -p "Pressione ENTER após editar o .env..."

# ──────────────────────────────────────
# 8. SUBIR CONTAINERS
# ──────────────────────────────────────
docker-compose up -d

echo "⏳ Aguardando containers iniciarem..."
sleep 15

# ──────────────────────────────────────
# 9. CONFIGURAR SSL (HTTPS)
# ──────────────────────────────────────
read -p "Seu domínio (ex: syndra.residencial.com.br): " DOMAIN

# Configurar Nginx
cat > /etc/nginx/sites-available/syndra-agent << EOF
server {
    listen 80;
    server_name $DOMAIN;

    location / {
        proxy_pass http://localhost:8000;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
    }

    location /evolution/ {
        proxy_pass http://localhost:8080/;
        proxy_set_header Host \$host;
        proxy_http_version 1.1;
        proxy_set_header Upgrade \$http_upgrade;
        proxy_set_header Connection "upgrade";
    }
}
EOF

ln -sf /etc/nginx/sites-available/syndra-agent /etc/nginx/sites-enabled/
nginx -t && systemctl reload nginx

# Gerar certificado SSL
certbot --nginx -d $DOMAIN --non-interactive --agree-tos -m admin@$DOMAIN

echo "✅ SSL configurado para $DOMAIN"

# ──────────────────────────────────────
# 10. POPULAR BASE DE CONHECIMENTO
# ──────────────────────────────────────
echo ""
echo "📚 Populando base de conhecimento..."
echo "   Coloque seus PDFs em /opt/syndra-agent/knowledge_docs/"
echo "   Depois execute: docker exec syndra-app python scripts/seed_knowledge.py"

echo ""
echo "✅ ══════════════════════════════════════"
echo "✅  Syndra Agent instalado com sucesso!"
echo "✅  URL: https://$DOMAIN"
echo "✅  Webhook: https://$DOMAIN/webhook/whatsapp"
echo "✅ ══════════════════════════════════════"

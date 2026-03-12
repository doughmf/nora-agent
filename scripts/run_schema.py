"""
Executa schema.sql no Supabase via Supabase Management API.
Requer SUPABASE_ACCESS_TOKEN (Personal Access Token do dashboard).
Se não disponível, imprime instruções para execução manual.
"""
import httpx
import os
from dotenv import load_dotenv

load_dotenv("config/.env")

SUPABASE_URL = os.getenv("SUPABASE_URL", "")
SUPABASE_SERVICE_KEY = os.getenv("SUPABASE_SERVICE_KEY", "")
# Token pessoal do Supabase (https://supabase.com/dashboard/account/tokens)
ACCESS_TOKEN = os.getenv("SUPABASE_ACCESS_TOKEN", "")

project_ref = SUPABASE_URL.replace("https://", "").replace(".supabase.co", "")

with open("src/supabase/schema.sql", "r", encoding="utf-8") as f:
    full_sql = f.read()

if not ACCESS_TOKEN:
    print("=" * 60)
    print("⚠️  SUPABASE_ACCESS_TOKEN não configurado.")
    print("Para executar o schema manualmente:")
    print(f"1. Acesse: https://supabase.com/dashboard/project/{project_ref}/sql/new")
    print("2. Cole o conteúdo do arquivo: src/supabase/schema.sql")
    print("3. Clique em RUN")
    print("=" * 60)
    exit(0)

print(f"Executando schema via Management API no projeto: {project_ref}")

with httpx.Client(timeout=60) as client:
    resp = client.post(
        f"https://api.supabase.com/v1/projects/{project_ref}/database/query",
        headers={
            "Authorization": f"Bearer {ACCESS_TOKEN}",
            "Content-Type": "application/json"
        },
        json={"query": full_sql}
    )
    
    if resp.status_code == 200:
        print("✅ Schema executado com sucesso!")
        print(resp.json())
    else:
        print(f"❌ Erro {resp.status_code}: {resp.text[:500]}")

# scripts/seed_settings.py
import os
import sys

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.supabase.client import supabase
from dotenv import load_dotenv

load_dotenv()

KEYS_TO_MIGRATE = [
    "CONDO_NAME",
    "CONDO_CNPJ",
    "CONDO_ADDRESS",
    "SINDICO_NAME",
    "SINDICO_PHONE",
    "ZELADOR_NAME",
    "ZELADOR_PHONE",
    "PORTARIA_PHONE",
    "ADMINISTRADORA_PHONE",
    "SALAO_PRECO_NOITE",
    "SALAO_PRECO_DIA",
    "CHURRASQUEIRA_PRECO",
    "PIX_CHAVE",
    "PIX_NOME"
]

def run():
    print("=== MIGRANDO CONFIGURAÇÕES .ENV PARA O SUPABASE ===")
    
    inseridos = 0
    for key in KEYS_TO_MIGRATE:
        val = os.getenv(key)
        if val is not None:
            try:
                supabase.table("system_settings").upsert({
                    "key": key,
                    "value": str(val)
                }).execute()
                print(f"✅ {key} migrado com sucesso.")
                inseridos += 1
            except Exception as e:
                print(f"❌ Erro ao migrar {key}: {e}")
        else:
            print(f"⚠️ Chave '{key}' não está presente no .env local. Pulando...")
            
    print(f"\nFinalizado! {inseridos} configurações copiadas para o painel web.")

if __name__ == "__main__":
    run()

# scripts/create_admin.py
import os
import sys
from passlib.context import CryptContext

# Adicionar pasta pai ao path para importar config
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.supabase.client import supabase

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

def run():
    print("=== Cadastro de Usuário do Painel NORA ===")
    nome = input("Nome completo: ")
    username = input("Username de login: ")
    senha = input("Senha nova: ")
    
    print("\nNíveis disponíveis:")
    print("1 - admin (Acesso total)")
    print("2 - sindico (Pode ver estatísticas e aprovar/enviar broadcats)")
    print("3 - colaborador (Portaria/Zeladoria - Apenas leitura e gestão de chamados)")
    papel_escolhido = input("Escolha o nível (1/2/3): ")

    niveis = {"1": "admin", "2": "sindico", "3": "colaborador"}
    role = niveis.get(papel_escolhido, "colaborador")

    hashed_password = pwd_context.hash(senha)

    print(f"\nCriando usuário '{username}' com a função de '{role}'...")

    try:
        response = supabase.table("system_users").insert({
            "name": nome,
            "username": username,
            "password_hash": hashed_password,
            "role": role
        }).execute()
        
        if response.data:
            print("✅ Usuário criado com sucesso no banco de dados!")
        else:
            print("⚠️ A resposta do Supabase não retornou dados, mas pode ter sido criada. Verifique o banco.")
            
    except Exception as e:
        print(f"❌ Erro ao criar usuário: {e}")

if __name__ == "__main__":
    run()

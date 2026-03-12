import os
import sys

# Corrige o path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fastapi.testclient import TestClient
from src.api.main import app

def simulate_admin_login() -> str:
    from src.api.main import JWT_SECRET, create_access_token
    # Gera um token falso com role="admin"
    token = create_access_token({"sub": "admin", "role": "admin"})
    return token

client = TestClient(app)

token = simulate_admin_login()
client.cookies.set("syndra_admin_session", token)

print("Tentando acessar /admin/settings...")
try:
    response = client.get("/admin/settings")
    print(f"Status Code: {response.status_code}")
    if response.status_code == 500:
        print("Erro 500! A resposta é:")
        print(response.text)
    else:
        print("Sucesso! O HTML tem:")
        print(response.text[:200])
except Exception as e:
    import traceback
    traceback.print_exc()

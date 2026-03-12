from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    # LLM API (OpenRouter)
    OPENROUTER_API_KEY: str = ""
    
    # Supabase
    SUPABASE_URL: str = ""
    SUPABASE_SERVICE_KEY: str = ""
    SUPABASE_ANON_KEY: str = ""
    
    # Evolution API
    EVOLUTION_API_URL: str = "http://localhost:8080"
    EVOLUTION_API_KEY: str = ""
    EVOLUTION_INSTANCE: str = "syndra-condominio"
    
    # Redis
    REDIS_URL: str = "redis://localhost:6379"
    
    # Application Config
    APP_HOST: str = "0.0.0.0"
    APP_PORT: int = 8000
    SECRET_KEY: str = ""
    DEBUG: bool = False
    
    # Condominio Variables
    CONDO_NAME: str = "Condomínio Exemplo"
    SINDICO_PHONE: str = ""
    ZELADOR_PHONE: str = ""
    PORTARIA_PHONE: str = ""

    # Extra Variables from .env (Allowing to prevent validation errors)
    SUPABASE_ACCESS_TOKEN: str = ""
    REDIS_PASSWORD: str = ""
    ADMIN_KEY: str = ""
    DOMAIN: str = ""
    CONDO_CNPJ: str = ""
    CONDO_ADDRESS: str = ""
    SINDICO_NAME: str = ""
    ZELADOR_NAME: str = ""
    ADMINISTRADORA_PHONE: str = ""
    SALAO_PRECO_NOITE: str = ""
    SALAO_PRECO_DIA: str = ""
    CHURRASQUEIRA_PRECO: str = ""
    PIX_CHAVE: str = ""
    PIX_NOME: str = ""

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="allow")

settings = Settings()

# Re-export key variables for easier access
SUPABASE_URL = settings.SUPABASE_URL
SUPABASE_SERVICE_KEY = settings.SUPABASE_SERVICE_KEY
SUPABASE_ANON_KEY = settings.SUPABASE_ANON_KEY
OPENROUTER_API_KEY = settings.OPENROUTER_API_KEY
EVOLUTION_API_URL = settings.EVOLUTION_API_URL
EVOLUTION_API_KEY = settings.EVOLUTION_API_KEY
EVOLUTION_INSTANCE = settings.EVOLUTION_INSTANCE

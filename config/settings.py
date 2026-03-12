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
    EVOLUTION_INSTANCE: str = "nora-condominio"
    
    # Redis
    REDIS_URL: str = "redis://localhost:6379"
    
    # Application Config
    APP_HOST: str = "0.0.0.0"
    APP_PORT: int = 8000
    SECRET_KEY: str = ""
    DEBUG: bool = False
    
    # Condominio Variables
    CONDO_NAME: str = "Residencial Nogueira Martins"
    SINDICO_PHONE: str = ""
    ZELADOR_PHONE: str = ""
    PORTARIA_PHONE: str = ""

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

settings = Settings()

# Re-export key variables for easier access
SUPABASE_URL = settings.SUPABASE_URL
SUPABASE_SERVICE_KEY = settings.SUPABASE_SERVICE_KEY
OPENROUTER_API_KEY = settings.OPENROUTER_API_KEY
EVOLUTION_API_URL = settings.EVOLUTION_API_URL
EVOLUTION_API_KEY = settings.EVOLUTION_API_KEY
EVOLUTION_INSTANCE = settings.EVOLUTION_INSTANCE

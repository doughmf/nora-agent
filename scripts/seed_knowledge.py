# scripts/seed_knowledge.py
import openai
from supabase import create_client
import os
from config.settings import SUPABASE_URL, SUPABASE_SERVICE_KEY, OPENROUTER_API_KEY

supabase = create_client(SUPABASE_URL, SUPABASE_SERVICE_KEY)

# Usa OpenRouter para embeddings (modelo compatível com OpenAI)
client = openai.Client(
    api_key=OPENROUTER_API_KEY,
    base_url="https://openrouter.ai/api/v1"
)

def chunk_document(text: str, chunk_size: int = 500) -> list[str]:
    """Divide documento em chunks com overlap."""
    words = text.split()
    chunks = []
    for i in range(0, len(words), chunk_size - 50):  # 50 words overlap
        chunk = " ".join(words[i:i + chunk_size])
        chunks.append(chunk)
    return chunks

def embed_text(text: str) -> list[float]:
    """Gera embedding via OpenRouter."""
    response = client.embeddings.create(
        input=text,
        model="openai/text-embedding-3-small"  # via OpenRouter
    )
    return response.data[0].embedding

def ingest_text(text: str, category: str, source_name: str):
    """Ingere texto na base de conhecimento."""
    chunks = chunk_document(text)
    for chunk in chunks:
        embedding = embed_text(chunk)
        supabase.table("knowledge_chunks").insert({
            "source": source_name,
            "category": category,
            "content": chunk,
            "embedding": embedding
        }).execute()
    print(f"✅ Ingested: {source_name} ({len(chunks)} chunks)")

if __name__ == "__main__":
    # Example usage:
    # ingest_pdf("knowledge_docs/regimento.pdf", "regimento", "Regimento Interno 2023")
    print("Seed Knowledge completed.")

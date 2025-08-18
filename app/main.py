import os
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.rag import RAGEngine

app = FastAPI(title="Smart Librarian API")

# CORS (tweak as needed)
app.add_middleware(
    CORSMiddleware,
    allow_origins=os.getenv("CORS_ALLOW_ORIGINS", "*").split(","),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

_rag: RAGEngine | None = None

SEED_ON_STARTUP = os.getenv("SEED_ON_STARTUP", "true").lower() == "true"


@app.on_event("startup")
def _startup():
    global _rag
    _rag = RAGEngine()
    if SEED_ON_STARTUP:
        _rag.seed_if_empty()


@app.get("/healthz")
def health():
    return {"ok": True}


@app.get("/stats")
def stats():
    global _rag
    if _rag is None:
        return {"collection": None}
    return {
        "collection": _rag.collection_name,
        "count": _rag.collection.count(),
        "path": _rag.chroma_path,
        "model": _rag.embedding_model,
        "batch": _rag.embed_batch_size,
    }

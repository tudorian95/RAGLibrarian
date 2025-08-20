# app/main.py
import os
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from .schemas import ChatRequest, ChatResponse, RetrievedDoc
from .rag import RAGEngine
from .llm import recommend_and_summarize
from .ui import router as ui_router

app = FastAPI(title="Smart Librarian", version="1.1.0")

# CORS (allow local use from browsers/tools)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"],
)

# RAG engine singleton
_rag = None

@app.on_event("startup")
def _startup():
    global _rag
    _rag = RAGEngine()
    _rag.seed_if_empty()

# Minimal UI (homepage)
app.include_router(ui_router)

@app.post("/chat", response_model=ChatResponse)
def chat(req: ChatRequest):
    """Legacy endpoint kept for compatibility; performs LLM+RAG."""
    return _recommend_core(req)

@app.post("/recommend", response_model=ChatResponse)
def recommend(req: ChatRequest):
    """
    NEW explicit endpoint:
    - Uses RAG to retrieve candidates from Chroma (semantic)
    - Asks the LLM to pick exactly 1 title
    - Calls the local tool get_summary_by_title(title) for the detailed summary
    - Returns assistant message + chosen title + full summary + candidate sources
    """
    return _recommend_core(req)

def _recommend_core(req: ChatRequest) -> ChatResponse:
    if not os.getenv("OPENAI_API_KEY"):
        raise HTTPException(status_code=500, detail="OPENAI_API_KEY is not set.")

    prompt = (req.prompt or "").strip()
    if not prompt:
        raise HTTPException(status_code=400, detail="Empty prompt.")

    # 1) Retrieve top candidates via RAG
    candidates = _rag.search(prompt, k=3)

    # If nothing comes back, fail fast with a helpful message
    if not candidates:
        return ChatResponse(
            message="I couldn't find a matching book for that theme. Try rephrasing or using broader terms.",
            recommendation_title=None,
            summary=None,
            sources=[],
        )

    # 2) Ask LLM to pick one & call the summary tool
    assistant_text, title, full_summary = recommend_and_summarize(prompt, candidates)

    # 3) Return structured result
    return ChatResponse(
        message=assistant_text,
        recommendation_title=title,
        summary=full_summary or None,
        sources=[RetrievedDoc(**c) for c in candidates],
    )

@app.get("/healthz")
def health():
    return {"ok": True}


@app.get("/stats")
def stats():
    global _rag
    if _rag is None:
        return {"ready": False}
    return {
        "ready": True,
        "collection": _rag.collection_name,
        "count": _rag.collection.count(),
        "path": _rag.chroma_path,
        "model": _rag.embedding_model,
        "batch": _rag.embed_batch_size,
    }

# Add this new endpoint to force (re)seed:
@app.post("/seed")
def seed():
    try:
        before, after = _rag.reseed()
        return {"ok": True, "before": before, "after": after}
    except Exception as e:
        # surface the exact error in Swagger/UI
        raise HTTPException(status_code=500, detail=f"Seeding failed: {e}")
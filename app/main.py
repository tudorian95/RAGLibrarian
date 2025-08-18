# app/main.py
import os
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from .schemas import ChatRequest, ChatResponse, RetrievedDoc
from .rag import RAGEngine
from .llm import recommend_and_summarize
from .ui import router as ui_router

app = FastAPI(title="Smart Librarian", version="1.0.0")

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

# Minimal UI
app.include_router(ui_router)

@app.post("/chat", response_model=ChatResponse)
def chat(req: ChatRequest):
    if not os.getenv("OPENAI_API_KEY"):
        raise HTTPException(status_code=500, detail="OPENAI_API_KEY is not set.")

    if not req.prompt or not req.prompt.strip():
        raise HTTPException(status_code=400, detail="Empty prompt.")

    candidates = _rag.search(req.prompt, k=3)
    assistant_text, title, full_summary = recommend_and_summarize(req.prompt, candidates)

    return ChatResponse(
        message=assistant_text,
        recommendation_title=title,
        summary=full_summary or None,
        sources=[RetrievedDoc(**c) for c in candidates],
    )

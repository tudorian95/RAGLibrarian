# app/rag.py
import os
import json
from typing import List, Dict, Any
from pathlib import Path

import chromadb
from chromadb.utils import embedding_functions

CHROMA_PATH = Path(os.getenv("CHROMA_PATH", "/app/chroma_data"))
COLLECTION_NAME = os.getenv("COLLECTION_NAME", "books")

DATA_JSON = Path(__file__).resolve().parent.parent / "data" / "book_summaries.json"

class RAGEngine:
    def __init__(self):
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise RuntimeError("OPENAI_API_KEY is not set.")
        self.client = chromadb.PersistentClient(path=str(CHROMA_PATH))
        self.embedding_fn = embedding_functions.OpenAIEmbeddingFunction(
            api_key=api_key,
            model_name=os.getenv("EMBEDDING_MODEL", "text-embedding-3-small"),
        )
        try:
            self.collection = self.client.get_collection(
                name=COLLECTION_NAME, embedding_function=self.embedding_fn
            )
        except Exception:
            self.collection = self.client.create_collection(
                name=COLLECTION_NAME, embedding_function=self.embedding_fn
            )

    def _load_seed(self) -> List[Dict[str, Any]]:
        with open(DATA_JSON, "r", encoding="utf-8") as f:
            return json.load(f)

    def seed_if_empty(self) -> None:
        count = self.collection.count()
        if count and count > 0:
            return
        entries = self._load_seed()
        ids, docs, metas = [], [], []
        for entry in entries:
            ids.append(entry["title"])
            # Put short summary + themes into the vector doc for semantic match
            doc = f"{entry['short_summary']}\nThemes: {', '.join(entry.get('themes', []))}"
            docs.append(doc)
            metas.append({
                "title": entry["title"],
                "author": entry.get("author"),
                "themes": entry.get("themes", []),
            })
        self.collection.add(ids=ids, documents=docs, metadatas=metas)

    def search(self, query: str, k: int = 3) -> List[Dict[str, Any]]:
        """Return top-k docs with metadata and (if available) distances/scores."""
        res = self.collection.query(query_texts=[query], n_results=k, include=["metadatas", "distances"])
        results = []
        if not res or not res.get("metadatas"):
            return results
        for meta, dist in zip(res["metadatas"][0], res.get("distances", [[None]])[0]):
            results.append({
                "title": meta.get("title"),
                "author": meta.get("author"),
                "themes": meta.get("themes", []),
                "score": float(dist) if dist is not None else None,
            })
        return results

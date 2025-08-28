# app/rag.py 
import os
# Disable Chroma telemetry early (prevents OpenAI proxies issue inside telemetry)
os.environ["CHROMA_TELEMETRY_ENABLED"] = "false"

import json
from typing import List, Dict, Any, Tuple
from pathlib import Path

import chromadb
from openai import OpenAI
from openai import APIError, RateLimitError, BadRequestError, PermissionDeniedError, NotFoundError

CHROMA_PATH = Path(os.getenv("CHROMA_PATH", "/app/chroma_data"))
COLLECTION_NAME = os.getenv("COLLECTION_NAME", "smartlib")
EMBED_MODEL = os.getenv("EMBEDDING_MODEL", "text-embedding-3-small")
EMBED_BATCH = int(os.getenv("EMBED_BATCH", "64"))

DATA_JSON = Path(__file__).resolve().parent.parent / "data" / "book_summaries.json"


class RAGEngine:
    def __init__(self):
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise RuntimeError("OPENAI_API_KEY is not set.")

        self.chroma_path = str(CHROMA_PATH)
        self.collection_name = COLLECTION_NAME
        self.embedding_model = EMBED_MODEL
        self.embed_batch_size = EMBED_BATCH

        # Chroma persistent client (we pass embeddings explicitly)
        self.client = chromadb.PersistentClient(path=self.chroma_path)

        # Modern OpenAI client
        self.openai = OpenAI(api_key=api_key)

        # Create or get collection
        try:
            self.collection = self.client.get_collection(name=self.collection_name)
        except Exception:
            self.collection = self.client.create_collection(name=self.collection_name)

    # ---------- Seeding ----------

    def _read_entries(self) -> List[Dict[str, Any]]:
        if not DATA_JSON.exists():
            raise FileNotFoundError(f"Seed file not found: {DATA_JSON}")
        with open(DATA_JSON, "r", encoding="utf-8") as f:
            return json.load(f)

    def _embed(self, texts: List[str]) -> List[List[float]]:
        resp = self.openai.embeddings.create(model=self.embedding_model, input=texts)
        return [d.embedding for d in resp.data]

    def _chunk(self, items: List[Any], size: int) -> List[List[Any]]:
        return [items[i:i + size] for i in range(0, len(items), size)]

    def seed_if_empty(self) -> Tuple[int, int]:
        """Seed only if empty. Returns (before_count, after_count)."""
        before = self.collection.count()
        if before and before > 0:
            return before, before
        return self._seed(force=True)

    def reseed(self) -> Tuple[int, int]:
        """Force reseed (clears collection). Returns (before_count, after_count)."""
        before = self.collection.count()
        if before:
            self.client.delete_collection(self.collection_name)
            self.collection = self.client.create_collection(name=self.collection_name)
        return self._seed(force=True, before=before or 0)

    def _seed(self, force: bool = False, before: int = 0) -> Tuple[int, int]:
        entries = self._read_entries()
        if not entries:
            raise RuntimeError("Seed file is empty.")

        ids: List[str] = []
        docs: List[str] = []
        metas: List[Dict[str, Any]] = []

        for e in entries:
            themes_list = e.get("themes", [])
            # ✅ Chroma metadata must be primitives → store as comma-separated string
            themes_str = ", ".join(themes_list) if isinstance(themes_list, list) else str(themes_list or "")
            ids.append(e["title"])
            docs.append(f"{e['short_summary']}\nThemes: {themes_str}")
            metas.append({
                "title": e["title"],
                "author": e.get("author") or "",
                "themes": themes_str,   # ✅ string, not list
            })

        # Embed & add in chunks
        for i_chunk, id_chunk in enumerate(self._chunk(ids, self.embed_batch_size)):
            start = i_chunk * self.embed_batch_size
            end = (i_chunk + 1) * self.embed_batch_size
            doc_chunk = docs[start:end]
            meta_chunk = metas[start:end]
            try:
                embeds = self._embed(doc_chunk)
                self.collection.add(ids=id_chunk, embeddings=embeds, documents=doc_chunk, metadatas=meta_chunk)
            except (PermissionDeniedError, NotFoundError, BadRequestError, RateLimitError, APIError) as e:
                raise RuntimeError(f"Embedding/add failed on chunk {i_chunk}: {e}") from e

        after = self.collection.count()
        return before, after

    # ---------- Search ----------

    def search(self, query: str, k: int = 3) -> List[Dict[str, Any]]:
        """Semantic search using our own embeddings."""
        q_vec = self._embed([query])[0]
        res = self.collection.query(
            query_embeddings=[q_vec],
            n_results=k,
            include=["metadatas", "distances"]
        )
        results: List[Dict[str, Any]] = []
        if not res or not res.get("metadatas"):
            return results

        metas = res["metadatas"][0]
        dists = res.get("distances", [[None]])[0]
        for meta, dist in zip(metas, dists):
            # themes are stored as a comma-separated string in metadata -> convert back to list[str]
            themes_field = meta.get("themes", "")
            if isinstance(themes_field, str):
                theme_list = [t.strip() for t in themes_field.split(",") if t.strip()]
            elif isinstance(themes_field, list):
                # (shouldn't happen now, but defensive)
                theme_list = [str(t) for t in themes_field]
            else:
                theme_list = []

            results.append({
                "title": meta.get("title", ""),
                "author": meta.get("author", ""),
                "themes": theme_list,  # <-- list[str] to satisfy pydantic
                "score": float(dist) if dist is not None else None,
            })
        return results

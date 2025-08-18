import os
import json
import glob
from time import sleep
from typing import Any, Dict, Iterable, List, Tuple

import chromadb
from chromadb.utils import embedding_functions
from openai import OpenAI, RateLimitError


def _chunks(seq: List[Any], n: int) -> Iterable[List[Any]]:
    for i in range(0, len(seq), n):
        yield seq[i : i + n]


class RAGEngine:
    def __init__(self) -> None:
        # ---- OpenAI / Embeddings config
        self.embedding_model = os.getenv("EMBEDDING_MODEL", "text-embedding-3-small")
        self.embed_batch_size = int(os.getenv("EMBED_BATCH_SIZE", "64"))
        self.max_seed_docs = int(os.getenv("MAX_SEED_DOCS", "200"))

        # New-style project-scoped client (respects OPENAI_API_KEY, OPENAI_PROJECT)
        # If you're on Azure, wire your Azure client here instead.
        self.openai = OpenAI()

        # ---- Chroma config
        self.chroma_path = os.getenv("CHROMA_PATH", "/app/chroma_data")
        self.collection_name = os.getenv("CHROMA_COLLECTION", "smartlib")
        self.client = chromadb.PersistentClient(path=self.chroma_path)

        # You can still swap this to a custom embedding function if desired; we pass embeddings explicitly.
        self.collection = self._get_or_create_collection(self.collection_name)

    # ----------------------------
    # Chroma helpers
    # ----------------------------
    def _get_or_create_collection(self, name: str):
        try:
            return self.client.get_collection(name)
        except Exception:
            return self.client.create_collection(name=name)

    @staticmethod
    def _sanitize_metadata(meta: Dict[str, Any]) -> Dict[str, Any]:
        """
        Chroma metadatas must be primitives (str/int/float/bool/None).
        Convert lists/dicts/others to JSON strings to avoid validation errors.
        """
        out: Dict[str, Any] = {}
        for k, v in meta.items():
            if isinstance(v, (str, int, float, bool)) or v is None:
                out[k] = v
            elif isinstance(v, (list, tuple, set, dict)):
                out[k] = json.dumps(v, ensure_ascii=False)
            else:
                out[k] = str(v)
        return out

    # ----------------------------
    # Embedding
    # ----------------------------
    def embed(self, texts: List[str]) -> List[List[float]]:
        """
        Batch and retry to keep startup predictable and resilient.
        """
        out: List[List[float]] = []
        for batch in _chunks(texts, self.embed_batch_size):
            # Basic backoff for transient 429
            for attempt in range(4):
                try:
                    resp = self.openai.embeddings.create(
                        model=self.embedding_model, input=batch
                    )
                    out.extend([d.embedding for d in resp.data])
                    break
                except RateLimitError:
                    sleep(1.5 * (attempt + 1))
        return out

    # ----------------------------
    # Seeding
    # ----------------------------
    def seed_if_empty(self) -> None:
        """
        Seeds the collection if it's empty. Looks for:
          - /app/seed/seed.json (list of {"text": str, "metadata": dict})
          - /app/seed/seed.jsonl (one JSON object per line with same fields)
          - Any *.txt / *.md files under /app/seed (filename becomes title)
        Caps total docs via MAX_SEED_DOCS.
        """
        if (count := self.collection.count()) and count > 0:
            return

        docs, metas = self._load_seed()
        if not docs:
            # Nothing to seed; safe no-op
            return

        # Hard cap & embed
        docs = docs[: self.max_seed_docs]
        metas = metas[: self.max_seed_docs]

        embeds = self.embed(docs)
        ids = [f"seed-{i}" for i in range(len(docs))]

        # Add a CSV form of tags if present, for easy filtering
        safe_metas: List[Dict[str, Any]] = []
        for m in metas:
            m = dict(m or {})
            if "tags" in m and isinstance(m["tags"], (list, tuple, set)):
                m["tags_csv"] = ",".join(map(str, list(m["tags"])))
            safe_metas.append(self._sanitize_metadata(m))

        assert len(ids) == len(docs) == len(embeds) == len(safe_metas), "Length mismatch"

        self.collection.add(
            ids=ids,
            embeddings=embeds,
            documents=docs,
            metadatas=safe_metas,
        )

    def _load_seed(self) -> Tuple[List[str], List[Dict[str, Any]]]:
        """
        Flexible loader. Prefer your existing format if you already had one:
          - /app/seed/seed.json : [{"text": "...", "metadata": {...}}, ...]
          - /app/seed/seed.jsonl: {"text": "...", "metadata": {...}} per line
          - /app/seed/*.(txt|md): plain files; metadata: {"title": <filename>}
        If none found, returns empty lists.
        """
        seed_dir = os.getenv("SEED_DIR", "/app/seed")
        json_path = os.path.join(seed_dir, "seed.json")
        jsonl_path = os.path.join(seed_dir, "seed.jsonl")

        docs: List[str] = []
        metas: List[Dict[str, Any]] = []

        try:
            if os.path.isfile(json_path):
                with open(json_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                for row in data:
                    docs.append(row.get("text", "") or "")
                    metas.append(row.get("metadata", {}) or {})
                return docs, metas

            if os.path.isfile(jsonl_path):
                with open(jsonl_path, "r", encoding="utf-8") as f:
                    for line in f:
                        line = line.strip()
                        if not line:
                            continue
                        row = json.loads(line)
                        docs.append(row.get("text", "") or "")
                        metas.append(row.get("metadata", {}) or {})
                return docs, metas

            # Fallback: text/markdown files
            paths = sorted(
                glob.glob(os.path.join(seed_dir, "**", "*.txt"), recursive=True)
                + glob.glob(os.path.join(seed_dir, "**", "*.md"), recursive=True)
            )
            for p in paths:
                with open(p, "r", encoding="utf-8") as f:
                    content = f.read()
                docs.append(content)
                metas.append({"title": os.path.basename(p), "path": p})
            return docs, metas
        except Exception:
            # On any parsing/IO error, return nothing rather than crashing startup.
            return [], []

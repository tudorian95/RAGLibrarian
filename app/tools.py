# app/tools.py
import json
from pathlib import Path
from typing import Dict

DATA_JSON = Path(__file__).resolve().parent.parent / "data" / "book_summaries.json"

def load_book_dict() -> Dict[str, Dict]:
    with open(DATA_JSON, "r", encoding="utf-8") as f:
        data = json.load(f)
    # Return dict keyed by exact title for fast lookup
    return {entry["title"]: entry for entry in data}

_BOOKS = load_book_dict()

def get_summary_by_title(title: str) -> str:
    """Return the full summary for an exact title; raises KeyError if not found."""
    entry = _BOOKS.get(title)
    if not entry:
        raise KeyError(f"Title not found: {title}")
    return entry["full_summary"].strip()

def tool_schema() -> dict:
    """OpenAI tool/function schema for function calling."""
    return {
        "type": "function",
        "function": {
            "name": "get_summary_by_title",
            "description": "Return the full, detailed summary for a book by exact title.",
            "parameters": {
                "type": "object",
                "properties": {
                    "title": {
                        "type": "string",
                        "description": "Exact book title, e.g., '1984'."
                    }
                },
                "required": ["title"],
                "additionalProperties": False
            }
        }
    }

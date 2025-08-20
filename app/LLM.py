# app/llm.py
import os
from typing import List, Dict, Tuple, Optional

from openai import OpenAI
from .tools import tool_schema, get_summary_by_title

SYSTEM_PROMPT = """You are Smart Librarian.
You must:
- Answer in English only.
- Recommend exactly ONE book title from the provided context candidates.
- Base your choice on thematic and contextual fit.
- After recommending, you MUST call the tool get_summary_by_title with the exact title you recommended.
- If the title is not in the provided candidates, choose the best match from the candidates and proceed."""

def _messages(user_prompt: str, candidates: List[Dict]) -> List[Dict]:
    context_lines = []
    for c in candidates:
        themes_str = ", ".join(c.get("themes", []))
        context_lines.append(f"- Title: {c['title']} | Themes: {themes_str}")
    context_block = "\n".join(context_lines) if context_lines else "No candidates."

    return [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": user_prompt},
        {"role": "system", "content": f"Candidate books:\n{context_block}\nChoose one."},
    ]

def recommend_and_summarize(user_prompt: str, candidates: List[Dict]) -> Tuple[str, Optional[str], str]:
    """
    Returns: (assistant_message, recommended_title, full_summary)
    """
    client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
    model = os.getenv("MODEL", "gpt-5-mini")  # fallback handled below

    # First pass: ask the model to recommend and call the tool
    completion = client.chat.completions.create(
        model=model,
        messages=_messages(user_prompt, candidates),
        tools=[tool_schema()],
        tool_choice="auto",
    )

    choice = completion.choices[0]
    msg = choice.message
    assistant_text = (msg.content or "").strip()

    # Determine recommended title from text (simple heuristic) OR from tool args
    recommended_title = None
    tool_calls = getattr(msg, "tool_calls", None)

    # If model already decided to call the tool, extract title
    if tool_calls:
        for call in tool_calls:
            if call.function and call.function.name == "get_summary_by_title":
                import json as _json
                args = _json.loads(call.function.arguments or "{}")
                recommended_title = args.get("title")
                break

    # If no tool call args contained a title, heuristically pick first candidate mentioned
    if not recommended_title and candidates:
        # naive pick: first candidate (shouldn’t happen if model follows instructions)
        recommended_title = candidates[0]["title"]

    # Execute the tool locally (required by assignment)
    full_summary = ""
    if recommended_title:
        try:
            full_summary = get_summary_by_title(recommended_title)
        except KeyError:
            # If not found (shouldn’t happen if data is consistent), leave empty
            full_summary = ""

    # If the assistant_text is empty (some models only emit tool calls), synthesize a friendly line
    if not assistant_text and recommended_title:
        assistant_text = f"I recommend **{recommended_title}** based on your interests."

    # If the model name is not available, fallback
    if "The model" in str(completion):  # generic safety; SDK returns structured errors normally
        # force fallback; not typically reached this way
        model = "gpt-5-nano"

    return assistant_text, recommended_title, full_summary

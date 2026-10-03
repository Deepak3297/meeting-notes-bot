import json
import os
import httpx

PROMPT = """You are a meeting-notes assistant. Read the transcript and reply with ONLY JSON:
{"summary": "3-5 sentence overview",
 "decisions": ["..."],
 "action_items": [{"task": "...", "owner": "person or Unassigned"}]}
Use only what is in the transcript. Do not invent owners or decisions."""


def to_text(segments: list[dict]) -> str:
    return "\n".join(f"[{s['timestamp'] // 60:02d}:{s['timestamp'] % 60:02d}] {s['speaker']}: {s['text']}" for s in segments)


def parse(raw: str) -> dict:
    raw = raw.strip().removeprefix("```json").removeprefix("```").removesuffix("```").strip()
    data = json.loads(raw)
    return {
        "summary": str(data.get("summary", "")),
        "decisions": [str(d) for d in data.get("decisions", [])],
        "action_items": [
            {"task": str(a.get("task", "")), "owner": str(a.get("owner") or "Unassigned")}
            for a in data.get("action_items", [])
        ],
    }


def _gemini(segments: list[dict]) -> dict:
    """Free option: Google AI Studio key, no credit card."""
    model = os.getenv("GEMINI_MODEL", "gemini-3.5-flash")
    r = httpx.post(
        f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent",
        headers={"x-goog-api-key": os.getenv("GEMINI_API_KEY", "")},
        json={
            "systemInstruction": {"parts": [{"text": PROMPT}]},
            "contents": [{"parts": [{"text": to_text(segments)}]}],
            "generationConfig": {"responseMimeType": "application/json"},
        },
        timeout=60,
    )
    r.raise_for_status()
    return parse(r.json()["candidates"][0]["content"]["parts"][0]["text"])


def _claude(segments: list[dict]) -> dict:
    import anthropic
    msg = anthropic.Anthropic().messages.create(
        model=os.getenv("CLAUDE_MODEL", "claude-sonnet-5-5"),
        max_tokens=1500,
        system=PROMPT,
        messages=[{"role": "user", "content": to_text(segments)}],
    )
    return parse(msg.content[0].text)


def _demo(segments: list[dict]) -> dict:
    """No AI, no key: simple rules so the app can be demoed offline."""
    speakers = sorted({s["speaker"] for s in segments})
    actions = [{"task": s["text"], "owner": s["speaker"]} for s in segments if " will " in f" {s['text'].lower()} "]
    return {
        "summary": f"Demo summary: {len(segments)} messages from {', '.join(speakers)}. "
                   f"First topic: {segments[0]['text']}",
        "decisions": [],
        "action_items": actions,
    }


def summarize(segments: list[dict]) -> dict:
    provider = os.getenv("LLM_PROVIDER", "gemini").lower()
    return {"gemini": _gemini, "claude": _claude, "demo": _demo}[provider](segments)
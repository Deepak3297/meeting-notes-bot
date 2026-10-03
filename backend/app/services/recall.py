"""Thin client for Recall.ai (meeting bot API). Check docs.recall.ai if fields change."""
import os
import httpx


def _base():
    return f"https://{os.getenv('RECALL_REGION', 'us-east-1')}.recall.ai/api/v1"


def _headers():
    return {"Authorization": f"Token {os.getenv('RECALL_API_KEY', '')}"}


def create_bot(meeting_url: str) -> str:
    body = {
        "meeting_url": meeting_url,
        "bot_name": "Notes Bot",  # visible to participants: transparency
        "recording_config": {"transcript": {"provider": {"recallai_streaming": {}}}},
    }
    r = httpx.post(f"{_base()}/bot", json=body, headers=_headers(), timeout=30)
    r.raise_for_status()
    return r.json()["id"]


def fetch_transcript(bot_id: str) -> list[dict]:
    """Returns [{speaker, text, timestamp}] once the meeting is done."""
    bot = httpx.get(f"{_base()}/bot/{bot_id}", headers=_headers(), timeout=30)
    bot.raise_for_status()
    url = bot.json()["recordings"][0]["media_shortcuts"]["transcript"]["data"]["download_url"]
    raw = httpx.get(url, timeout=60).json()
    out = []
    for entry in raw:
        words = entry.get("words", [])
        if not words:
            continue
        out.append({
            "speaker": entry["participant"].get("name") or "Unknown",
            "text": " ".join(w["text"] for w in words),
            "timestamp": int(words[0]["start_timestamp"]["relative"]),
        })
    return out

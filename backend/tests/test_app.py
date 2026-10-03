import os
os.environ["DATABASE_URL"] = "sqlite:///./test.db"
from fastapi.testclient import TestClient
from app.main import app
from app.services import summarizer, recall

client = TestClient(app)
FAKE = {"summary": "Team agreed on launch.", "decisions": ["Launch Friday"],
        "action_items": [{"task": "Write release notes", "owner": "Asha"}]}
SEGS = [{"speaker": "Asha", "text": "Ship Friday?", "timestamp": 5}]


def test_parse_handles_code_fences_and_missing_owner():
    out = summarizer.parse('```json\n{"summary":"s","decisions":["d"],"action_items":[{"task":"t"}]}\n```')
    assert out["action_items"][0]["owner"] == "Unassigned"


def test_paste_flow_creates_ready_report(monkeypatch):
    monkeypatch.setattr(summarizer, "summarize", lambda s: FAKE)
    r = client.post("/meetings/paste", json={"transcript": "Asha: Ship Friday?\nBen: Yes."})
    assert r.json()["status"] == "ready"
    full = client.get(f"/meetings/{r.json()['id']}").json()
    assert full["decisions"] == ["Launch Friday"] and len(full["transcript"]) == 2


def test_webhook_flow(monkeypatch):
    monkeypatch.setattr(recall, "create_bot", lambda url: "bot-1")
    monkeypatch.setattr(recall, "fetch_transcript", lambda b: SEGS)
    monkeypatch.setattr(summarizer, "summarize", lambda s: FAKE)
    mid = client.post("/meetings", json={"meeting_url": "https://meet.google.com/x"}).json()["id"]
    ev = lambda e: client.post("/webhooks/recall", json={"event": e, "data": {"bot": {"id": "bot-1"}}})
    ev("bot.in_call_recording")
    assert client.get(f"/meetings/{mid}").json()["status"] == "recording"
    ev("bot.done")
    full = client.get(f"/meetings/{mid}").json()
    assert full["status"] == "ready" and full["action_items"][0]["owner"] == "Asha" or full["action_items"][0]["owner"] == "Asha"


def test_empty_paste_rejected():
    assert client.post("/meetings/paste", json={"transcript": "  "}).status_code == 400

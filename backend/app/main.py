import os
from fastapi import FastAPI, Depends, HTTPException, BackgroundTasks, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from sqlalchemy.orm import Session
from .db import Base, engine, get_db, SessionLocal
from .models import Meeting, Segment, Decision, ActionItem
from .services import recall, summarizer

Base.metadata.create_all(engine)
app = FastAPI(title="Meeting Notes Bot")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])


class JoinIn(BaseModel):
    meeting_url: str
    title: str = "Untitled meeting"


class PasteIn(BaseModel):
    title: str = "Pasted transcript"
    transcript: str  # one "Speaker: text" per line


def serialize(m: Meeting, full: bool = False) -> dict:
    d = {"id": m.id, "title": m.title, "status": m.status, "created_at": m.created_at.isoformat()}
    if full:
        d.update(
            meeting_url=m.meeting_url, summary=m.summary,
            decisions=[x.text for x in m.decisions],
            action_items=[{"task": a.task, "owner": a.owner} for a in m.action_items],
            transcript=[{"speaker": s.speaker, "text": s.text, "timestamp": s.timestamp} for s in m.segments],
        )
    return d


def process(meeting_id: int, segments: list[dict]):
    """Save transcript, summarize, save results. Runs after the meeting ends."""
    db = SessionLocal()
    try:
        m = db.get(Meeting, meeting_id)
        m.status = "processing"
        m.segments = [Segment(**s) for s in segments]
        db.commit()
        try:
            result = summarizer.summarize(segments)
        except Exception as e:
            print("SUMMARY ERROR:", repr(e))
            m.status = "failed"
            db.commit()
            return
        m.summary = result["summary"]
        m.decisions = [Decision(text=t) for t in result["decisions"]]
        m.action_items = [ActionItem(**a) for a in result["action_items"]]
        m.status = "ready"
        db.commit()
    finally:
        db.close()


def finish_from_recall(meeting_id: int, bot_id: str):
    try:
        segments = recall.fetch_transcript(bot_id)
    except Exception:
        db = SessionLocal()
        db.get(Meeting, meeting_id).status = "failed"
        db.commit()
        db.close()
        return
    process(meeting_id, segments)


@app.post("/meetings")
def join(body: JoinIn, db: Session = Depends(get_db)):
    try:
        bot_id = recall.create_bot(body.meeting_url)
    except Exception as e:
        raise HTTPException(502, f"Could not start the bot: {e}")
    m = Meeting(title=body.title, meeting_url=body.meeting_url, bot_id=bot_id, status="joining")
    db.add(m)
    db.commit()
    return serialize(m)


@app.post("/meetings/paste")
def paste(body: PasteIn, db: Session = Depends(get_db)):
    """Fallback: skip the bot and summarize a transcript you already have."""
    segments = []
    for i, line in enumerate(l for l in body.transcript.splitlines() if l.strip()):
        speaker, _, text = line.partition(":")
        segments.append({"speaker": speaker.strip() if text else "Unknown",
                         "text": (text or line).strip(), "timestamp": i * 10})
    if not segments:
        raise HTTPException(400, "Transcript is empty")
    m = Meeting(title=body.title, status="processing")
    db.add(m)
    db.commit()
    process(m.id, segments)
    db.refresh(m)
    return serialize(m)


@app.get("/meetings")
def list_meetings(db: Session = Depends(get_db)):
    return [serialize(m) for m in db.query(Meeting).order_by(Meeting.created_at.desc())]


@app.get("/meetings/{meeting_id}")
def get_meeting(meeting_id: int, db: Session = Depends(get_db)):
    m = db.get(Meeting, meeting_id)
    if not m:
        raise HTTPException(404, "Meeting not found")
    return serialize(m, full=True)


@app.post("/webhooks/recall")
async def recall_webhook(request: Request, bg: BackgroundTasks, token: str = "", db: Session = Depends(get_db)):
    expected = os.getenv("WEBHOOK_TOKEN")
    if expected and token != expected:
        raise HTTPException(403, "Bad token")
    payload = await request.json()
    event = payload.get("event", "")
    bot_id = payload.get("data", {}).get("bot", {}).get("id")
    m = db.query(Meeting).filter_by(bot_id=bot_id).first()
    if not m:
        return {"ok": True}  # unknown bot: ignore
    if event == "bot.in_call_recording":
        m.status = "recording"
    elif event == "bot.call_ended":
        m.status = "processing"
    elif event == "bot.fatal":
        m.status = "failed"
    elif event == "bot.done":
        bg.add_task(finish_from_recall, m.id, bot_id)
    db.commit()
    return {"ok": True}

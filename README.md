# Meeting Notes Bot

A bot joins a Google Meet / Teams / Zoom call, transcribes it, and produces a summary, decisions and action items when the call ends (Read.ai-style).

## Stack and why
| Layer | Choice | Why |
|---|---|---|
| Frontend | React + Vite | Component per concern (start form, report); polls status until the meeting is ready. UI was AI-assisted, then reviewed by me. |
| Backend | FastAPI | Async, Pydantic validation, auto docs at `/docs` |
| DB | SQLite by default, PostgreSQL via `DATABASE_URL` | Zero-setup for reviewers; relational data (meetings → segments/decisions/action items) |
| Bot | Recall.ai | Handles joining Meet/Teams/Zoom; building this from scratch is fragile |
| Summaries | Claude API | Returns JSON that is validated before saving |
| Tests | pytest | Recall and Claude are mocked; covers parsing, webhook flow, paste flow, bad input |

## Flow
1. `POST /meetings` with a meeting link → Recall sends "Notes Bot" into the call (visible name = transparency).
2. Recall calls `POST /webhooks/recall` as the bot moves: recording → call ended → done.
3. On `bot.done` the backend downloads the transcript, saves segments, asks Claude for JSON, saves decisions/action items, sets status `ready`.
4. React polls `GET /meetings/{id}` every 4s and renders the report when ready.
Fallback: `POST /meetings/paste` runs steps 3–4 on a pasted transcript, so the app is demoable without a live call.

## Every stored field is used
| Field | Used for |
|---|---|
| meetings.title / created_at | list label, report header, newest-first ordering |
| meetings.meeting_url | sent to Recall, shown on report |
| meetings.bot_id | webhook finds the right meeting |
| meetings.status | badge, polling stops at ready/failed |
| meetings.summary, decisions.text, action_items.task/owner | report "Notes" tab |
| transcript_segments.speaker/text/timestamp | "Transcript" tab and summarizer input |

## Run it
```bash
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env        # add RECALL_API_KEY and ANTHROPIC_API_KEY
uvicorn app.main:app --reload   # http://localhost:8000/docs

cd ../frontend && npm install && npm run dev   # http://localhost:5173
```
For real calls, expose the backend (`ngrok http 8000`) and in the Recall dashboard add a webhook to
`<ngrok-url>/webhooks/recall?token=<WEBHOOK_TOKEN>` with the bot events enabled.
Tests: `cd backend && pytest`

## Trade-offs / next steps
Background tasks are in-process; a queue (Celery/RQ) would survive restarts. Chunk very long transcripts before summarizing. Add auth and per-user meetings. Verify Recall's webhook signature instead of a shared token.

import { useEffect, useState } from "react";

const api = async (path, opts) => {
  const r = await fetch("/api" + path, opts && { ...opts, headers: { "Content-Type": "application/json" } });
  if (!r.ok) throw new Error((await r.json()).detail || "Request failed");
  return r.json();
};
const post = (path, body) => api(path, { method: "POST", body: JSON.stringify(body) });
const mmss = (s) => `${String(Math.floor(s / 60)).padStart(2, "0")}:${String(s % 60).padStart(2, "0")}`;
const LABEL = { joining: "Joining", recording: "Recording", processing: "Writing notes", ready: "Ready", failed: "Failed" };

function Start({ onCreated }) {
  const [mode, setMode] = useState("bot");
  const [title, setTitle] = useState("");
  const [value, setValue] = useState("");
  const [err, setErr] = useState("");
  const [busy, setBusy] = useState(false);
  const submit = async () => {
    setErr(""); setBusy(true);
    try {
      const m = mode === "bot"
        ? await post("/meetings", { meeting_url: value, title: title || "Untitled meeting" })
        : await post("/meetings/paste", { transcript: value, title: title || "Pasted transcript" });
      setValue(""); setTitle(""); onCreated(m);
    } catch (e) { setErr(e.message); }
    setBusy(false);
  };
  return (
    <section className="start">
      <div className="tabs">
        <button className={mode === "bot" ? "on" : ""} onClick={() => setMode("bot")}>Send bot to meeting</button>
        <button className={mode === "paste" ? "on" : ""} onClick={() => setMode("paste")}>Paste transcript</button>
      </div>
      <input placeholder="Meeting title" value={title} onChange={(e) => setTitle(e.target.value)} />
      {mode === "bot"
        ? <input placeholder="Google Meet, Teams or Zoom link" value={value} onChange={(e) => setValue(e.target.value)} />
        : <textarea rows={5} placeholder={"Asha: Can we ship on Friday?\nBen: Yes, I'll finish tests today."} value={value} onChange={(e) => setValue(e.target.value)} />}
      <button className="primary" disabled={busy || !value.trim()} onClick={submit}>
        {busy ? "Working…" : mode === "bot" ? "Send bot" : "Summarize"}
      </button>
      {err && <p className="err">{err}</p>}
    </section>
  );
}

function Report({ id }) {
  const [m, setM] = useState(null);
  const [tab, setTab] = useState("notes");
  useEffect(() => {
    let live = true, t;
    const load = async () => {
      const d = await api(`/meetings/${id}`);
      if (!live) return;
      setM(d);
      if (!["ready", "failed"].includes(d.status)) t = setTimeout(load, 4000);
    };
    setM(null); load();
    return () => { live = false; clearTimeout(t); };
  }, [id]);
  if (!m) return <p className="muted">Loading…</p>;
  return (
    <article>
      <header><h2>{m.title}</h2><span className={`badge ${m.status}`}>{LABEL[m.status]}</span></header>
      {m.meeting_url && <p className="muted">{m.meeting_url}</p>}
      {m.status !== "ready" && <p className="muted">{m.status === "failed" ? "Something went wrong while making notes for this meeting." : "Notes appear here when the meeting ends."}</p>}
      {m.status === "ready" && (<>
        <div className="tabs">
          <button className={tab === "notes" ? "on" : ""} onClick={() => setTab("notes")}>Notes</button>
          <button className={tab === "transcript" ? "on" : ""} onClick={() => setTab("transcript")}>Transcript</button>
        </div>
        {tab === "notes" ? (<>
          <h3>Summary</h3><p>{m.summary}</p>
          <h3>Decisions</h3>
          {m.decisions.length ? <ul>{m.decisions.map((d, i) => <li key={i}>{d}</li>)}</ul> : <p className="muted">No decisions recorded.</p>}
          <h3>Action items</h3>
          {m.action_items.length ? <ul>{m.action_items.map((a, i) => <li key={i}>{a.task} <b>{a.owner}</b></li>)}</ul> : <p className="muted">No action items.</p>}
        </>) : (
          <div className="transcript">{m.transcript.map((s, i) => <p key={i}><time>{mmss(s.timestamp)}</time><b>{s.speaker}</b> {s.text}</p>)}</div>
        )}
      </>)}
    </article>
  );
}

export default function App() {
  const [list, setList] = useState([]);
  const [sel, setSel] = useState(null);
  const refresh = () => api("/meetings").then(setList).catch(() => {});
  useEffect(() => { refresh(); const t = setInterval(refresh, 5000); return () => clearInterval(t); }, []);
  return (
    <div className="app">
      <aside>
        <h1>Meeting notes</h1>
        <Start onCreated={(m) => { setSel(m.id); refresh(); }} />
        <ul className="list">
          {list.map((m) => (
            <li key={m.id}><button className={sel === m.id ? "on" : ""} onClick={() => setSel(m.id)}>
              <span>{m.title}</span><span className={`badge ${m.status}`}>{LABEL[m.status]}</span>
            </button></li>
          ))}
          {!list.length && <li className="muted">No meetings yet. Send the bot to one, or paste a transcript.</li>}
        </ul>
      </aside>
      <main>{sel ? <Report id={sel} /> : <p className="muted">Pick a meeting to read its notes.</p>}</main>
    </div>
  );
}

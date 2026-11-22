"use client";

import { useCallback, useEffect, useState } from "react";
import { ratings, speaking, type RateItem, type RatePrompt, type RatingStats } from "@/lib/api";
import { taskName } from "@/lib/tasks";

const TASKS = ["write-an-email", "academic-discussion", "take-an-interview", "listen-and-repeat"];

function Prompt({ p }: { p: RatePrompt }) {
  switch (p.kind) {
    case "email":
      return (
        <div className="space-y-2 text-sm">
          <p>{p.scenario}</p>
          <p className="font-medium">Email to {p.recipient}. Must:</p>
          <ul className="list-disc pl-5">{p.points.map((x) => <li key={x}>{x}</li>)}</ul>
        </div>
      );
    case "discussion":
      return (
        <div className="space-y-2 text-sm">
          <div className="text-xs uppercase text-slate-500">{p.course}</div>
          <p><b>{p.professor.name}:</b> {p.professor.text}</p>
          {p.students.map((s) => <p key={s.name} className="text-slate-600"><b>{s.name}:</b> {s.text}</p>)}
        </div>
      );
    case "interview":
      return <p className="text-sm"><b>Interviewer:</b> {p.question}</p>;
    case "listen-repeat":
      return <p className="text-sm"><b>Sentence to repeat:</b> {p.sentence}</p>;
  }
}

export default function RatePage() {
  const [rater, setRater] = useState("");
  const [task, setTask] = useState(TASKS[0]);
  const [item, setItem] = useState<RateItem | null>(null);
  const [score, setScore] = useState<number | null>(null);
  const [note, setNote] = useState("");
  const [stats, setStats] = useState<RatingStats | null>(null);
  const [msg, setMsg] = useState<string | null>(null);
  const [err, setErr] = useState<string | null>(null);

  useEffect(() => {
    try {
      setRater(localStorage.getItem("ibt-rater") ?? "");
    } catch {}
    ratings.stats().then(setStats).catch((e: Error) => setErr(e.message));
  }, []);

  const load = useCallback(async () => {
    if (!rater.trim()) return;
    setErr(null);
    setScore(null);
    setNote("");
    try {
      setItem(await ratings.next(task, rater.trim()));
    } catch (e) {
      setErr((e as Error).message);
    }
  }, [rater, task]);

  const save = async () => {
    if (!item || item.done || score === null) return;
    try {
      await ratings.save(item.response_id, rater.trim(), score, note || undefined);
      setStats(await ratings.stats());
      await load();
    } catch (e) {
      setErr((e as Error).message);
    }
  };

  return (
    <div className="space-y-5">
      <div>
        <h1 className="text-2xl font-semibold">Rate responses</h1>
        <p className="text-sm text-slate-600">
          Blind human rating for the calibration set: you never see the app&apos;s score. Rate holistically against the
          rubric. Each response is shown to two different raters.
        </p>
      </div>
      {err && <div className="card border-red-200 bg-red-50 text-sm text-red-800">{err}</div>}

      <div className="card flex flex-wrap items-end gap-3">
        <div>
          <label className="label" htmlFor="rater">Your rater name</label>
          <input id="rater" className="input" value={rater} placeholder="e.g. rater-a"
            onChange={(e) => {
              setRater(e.target.value);
              try { localStorage.setItem("ibt-rater", e.target.value); } catch {}
            }} />
        </div>
        <div>
          <label className="label" htmlFor="task">Task</label>
          <select id="task" className="input" value={task} onChange={(e) => { setTask(e.target.value); setItem(null); }}>
            {TASKS.map((t) => <option key={t} value={t}>{taskName(t)}</option>)}
          </select>
        </div>
        <button className="btn-primary" onClick={load} disabled={!rater.trim()}>Start rating</button>
        <button className="btn-ghost ml-auto" onClick={async () => {
          try {
            const r = await ratings.export();
            setMsg(Object.entries(r).map(([t, v]) => `${taskName(t)}: ${v.rows} row(s)${v.file ? ` → ${v.file}` : ""}`).join(" · "));
          } catch (e) {
            setErr((e as Error).message);
          }
        }}>Export to eval data</button>
      </div>
      {msg && <p className="text-sm text-emerald-800">{msg}</p>}

      {stats && (
        <div className="grid gap-3 text-sm sm:grid-cols-4">
          {TASKS.map((t) => (
            <div key={t} className="card py-3">
              <div className="font-medium">{taskName(t)}</div>
              <div className="text-slate-600">{stats[t].responses} responses · {stats[t].rated_twice_or_more} double-rated · {stats[t].unrated} unrated</div>
            </div>
          ))}
        </div>
      )}

      {item && item.done && <div className="card text-sm text-slate-600">Nothing left for you to rate in this task. 🎉</div>}
      {item && !item.done && (
        <div className="grid gap-4 lg:grid-cols-[3fr_2fr]">
          <div className="space-y-4">
            <div className="card space-y-2">
              <div className="text-xs uppercase tracking-wide text-slate-500">Prompt · {item.remaining} left</div>
              <Prompt p={item.prompt} />
            </div>
            <div className="card space-y-3">
              <div className="text-xs uppercase tracking-wide text-slate-500">Response</div>
              {item.has_audio && <audio controls src={speaking.audioUrl(item.response_id)} className="h-9 w-full" />}
              {item.text !== null && <p className="whitespace-pre-wrap leading-7">{item.text || <i className="text-slate-400">(blank)</i>}</p>}
              {item.transcript !== null && (
                <p className="text-sm text-slate-600"><b>Transcript (automatic, may contain errors):</b> {item.transcript || "(none)"}</p>
              )}
            </div>
          </div>
          <div className="card space-y-3">
            <div className="text-xs uppercase tracking-wide text-slate-500">Rubric</div>
            <div className="space-y-2">
              {[5, 4, 3, 2, 1, 0].map((k) => (
                <button key={k} onClick={() => setScore(k)}
                  className={`block w-full rounded-lg border p-2 text-left text-sm ${score === k
                    ? "border-indigo-400 bg-indigo-50" : "border-slate-200 hover:bg-slate-50"}`}>
                  <b className="mr-1">{k}</b>{item.rubric.labels[String(k)] && <b>{item.rubric.labels[String(k)]}. </b>}
                  <span className="text-slate-600">{item.rubric.bands[String(k)]}</span>
                </button>
              ))}
            </div>
            <input className="input" placeholder="Note (optional)" value={note} onChange={(e) => setNote(e.target.value)} />
            <div className="flex gap-2">
              <button className="btn-primary" onClick={save} disabled={score === null}>Save & next</button>
              <button className="btn-ghost" onClick={load}>Skip</button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

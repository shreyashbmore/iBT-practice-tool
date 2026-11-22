"use client";

import { useEffect, useState } from "react";
import { drafts, type DraftSummary, type GenTask } from "@/lib/api";

const CEFR = ["A1", "A2", "B1", "B2", "C1", "C2"];

function QABadge({ d }: { d: DraftSummary }) {
  const qa = d.review?.qa;
  if (!qa) return null;
  const bad = qa.mismatches.length > 0 || qa.warnings.length > 0;
  return (
    <span className={`rounded-full border px-2 py-0.5 text-xs ${bad ? "border-amber-300 bg-amber-50 text-amber-800"
      : "border-emerald-200 bg-emerald-50 text-emerald-700"}`}>
      {qa.questions_checked ? `solver ${qa.solver_agreed}/${qa.questions_checked}` : "no MCQ"}
      {qa.warnings.length > 0 && ` · ${qa.warnings.length} warning(s)`}
    </span>
  );
}

export default function Review() {
  const [tasks, setTasks] = useState<GenTask[]>([]);
  const [list, setList] = useState<DraftSummary[]>([]);
  const [task, setTask] = useState("read-daily-life");
  const [cefr, setCefr] = useState("B1");
  const [topic, setTopic] = useState("");
  const [busy, setBusy] = useState<string | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [open, setOpen] = useState<{ id: string; data: Record<string, unknown> } | null>(null);

  const refresh = () => drafts.list().then(setList).catch((e: Error) => setErr(e.message));
  useEffect(() => {
    drafts.tasks().then(setTasks).catch((e: Error) => setErr(e.message));
    refresh();
  }, []);

  const run = async (label: string, fn: () => Promise<unknown>) => {
    setBusy(label);
    setErr(null);
    try {
      await fn();
    } catch (e) {
      setErr((e as Error).message);
    } finally {
      setBusy(null);
    }
  };

  const spec = tasks.find((t) => t.task === task);

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-semibold">Content review</h1>
        <p className="text-sm text-slate-600">
          Generate original practice sets with your LLM. Each draft is validated, every multiple-choice question is
          re-solved without the key to catch ambiguous items, and nothing is used for practice until you approve it.
        </p>
      </div>
      {err && <div className="card border-red-200 bg-red-50 text-sm text-red-800">{err}</div>}

      <section className="card space-y-3">
        <h2 className="font-semibold">Generate a draft</h2>
        <div className="grid gap-3 sm:grid-cols-[2fr_1fr_2fr_auto]">
          <select className="input" value={task} onChange={(e) => setTask(e.target.value)} aria-label="Task">
            {tasks.map((t) => <option key={t.task} value={t.task}>{t.label}</option>)}
          </select>
          <select className="input" value={cefr} onChange={(e) => setCefr(e.target.value)} aria-label="CEFR level">
            {CEFR.map((c) => <option key={c}>{c}</option>)}
          </select>
          <input className="input" placeholder="Topic (optional)" value={topic} onChange={(e) => setTopic(e.target.value)} />
          <button className="btn-primary" disabled={!!busy} onClick={() => run("gen", async () => {
            const d = await drafts.generate(task, cefr, topic);
            await refresh();
            setOpen({ id: d.id as string, data: d });
          })}>{busy === "gen" ? "Generating…" : "Generate"}</button>
        </div>
        {spec && <p className="text-xs text-slate-500">{spec.guidance}</p>}
      </section>

      <section className="space-y-3">
        <h2 className="font-semibold">Drafts ({list.length})</h2>
        {list.length === 0 && <p className="text-sm text-slate-500">No drafts waiting for review.</p>}
        {list.map((d) => (
          <div key={d.id} className="card space-y-3">
            <div className="flex flex-wrap items-center justify-between gap-2">
              <div>
                <div className="font-medium">{d.title}</div>
                <div className="text-xs text-slate-500">
                  {d.id} · {d.review?.cefr} · {d.review?.model ?? "model?"} · {d.review?.generated_at}
                  {d.review?.usage?.cost_usd != null && ` · ~$${d.review.usage.cost_usd.toFixed(4)}`}
                </div>
              </div>
              <div className="flex items-center gap-2">
                <QABadge d={d} />
                <button className="btn-ghost" onClick={() => run(`open-${d.id}`, async () =>
                  setOpen(open?.id === d.id ? null : { id: d.id, data: await drafts.get(d.id) }))}>
                  {open?.id === d.id ? "Hide" : "Preview"}
                </button>
                <button className="btn-primary" disabled={!!busy}
                  onClick={() => run(`ok-${d.id}`, async () => { await drafts.approve(d.id); setOpen(null); await refresh(); })}>
                  Approve
                </button>
                <button className="btn-danger" disabled={!!busy}
                  onClick={() => run(`rm-${d.id}`, async () => { await drafts.discard(d.id); setOpen(null); await refresh(); })}>
                  Discard
                </button>
              </div>
            </div>
            {d.review?.qa && (d.review.qa.mismatches.length > 0 || d.review.qa.warnings.length > 0) && (
              <ul className="list-disc pl-5 text-sm text-amber-800">
                {d.review.qa.mismatches.map((m) => <li key={m}>Solver chose a different answer for {m} — check the key and distractors.</li>)}
                {d.review.qa.warnings.map((w) => <li key={w}>{w}</li>)}
              </ul>
            )}
            {open?.id === d.id && (
              <pre className="max-h-[60vh] overflow-auto whitespace-pre-wrap rounded-lg bg-slate-50 p-3 text-xs leading-5">
                {JSON.stringify((open.data as { items?: unknown }).items ?? open.data, null, 2)}
              </pre>
            )}
          </div>
        ))}
      </section>
    </div>
  );
}

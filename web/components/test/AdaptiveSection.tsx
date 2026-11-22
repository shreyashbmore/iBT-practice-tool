"use client";

import Link from "next/link";
import { useState } from "react";
import { forms, type FinalResult, type Module, type SetAnswers } from "@/lib/api";
import ObjectiveModule from "@/components/objective/ObjectiveModule";
import ObjectiveResults from "@/components/objective/ObjectiveResults";

export function AdaptiveSection({ formId, onDone }: { formId: string; onDone?: (responseId: string) => void }) {
  const [phase, setPhase] = useState<"intro" | "module" | "between" | "done">("intro");
  const [attempt, setAttempt] = useState<{ id: string; title: string; directions: string } | null>(null);
  const [module, setModule] = useState<Module | null>(null);
  const [next, setNext] = useState<Module | null>(null);
  const [final, setFinal] = useState<FinalResult | null>(null);
  const [titles, setTitles] = useState<Record<string, string>>({});
  const [err, setErr] = useState<string | null>(null);

  const start = async () => {
    try {
      const r = await forms.start(formId);
      setAttempt({ id: r.attempt_id, title: r.form.title, directions: r.form.directions });
      setModule(r.module);
      setTitles(Object.fromEntries(r.module.sets.map((s) => [s.id, s.title])));
      setPhase("module");
    } catch (e) {
      setErr((e as Error).message);
    }
  };

  const submit = async (answers: SetAnswers, elapsed: number) => {
    if (!attempt || !module) return;
    try {
      const r = await forms.submit(formId, attempt.id, module.stage, answers, elapsed);
      if (r.next) {
        setNext(r.next);
        setTitles((t) => ({ ...t, ...Object.fromEntries(r.next!.sets.map((s) => [s.id, s.title])) }));
        setPhase("between");
      } else if (r.final) {
        if (onDone) {
          onDone(r.final.response_id);
          return;
        }
        setFinal(r.final);
        setPhase("done");
      }
    } catch (e) {
      setErr((e as Error).message);
    }
  };

  if (phase === "intro") {
    return (
      <div className="card space-y-4">
        {!onDone && <Link href="/" className="text-sm text-slate-500 hover:underline">← Home</Link>}
        <h1 className="text-xl font-semibold">{onDone ? "Section start" : "Section test"}</h1>
        <p className="text-slate-700">
          Two timed modules. Your result in module 1 decides whether module 2 is easier or harder — the same
          multistage design as the 2026 test. You can&apos;t go back to module 1 once it&apos;s submitted.
        </p>
        {err && <p className="text-sm text-red-700">{err}</p>}
        <button className="btn-primary" onClick={start}>Start module 1</button>
      </div>
    );
  }
  if (phase === "between" && next) {
    return (
      <div className="card space-y-4">
        <h1 className="text-xl font-semibold">Module 1 complete</h1>
        <p className="text-slate-700">Module 2 has {next.sets.reduce((n, s) => n + s.n_items, 0)} item(s) and about {Math.round(next.time_limit_s / 60)} minutes. The timer starts when you continue.</p>
        <button className="btn-primary" onClick={() => { setModule(next); setNext(null); setPhase("module"); }}>Start module 2</button>
      </div>
    );
  }
  if (phase === "module" && module) {
    return (
      <div className="space-y-2">
        {err && <p className="text-sm text-red-700">{err}</p>}
        <ObjectiveModule key={module.stage} sets={module.sets} timeLimit={module.time_limit_s}
          label={module.stage === "router" ? "Module 1" : "Module 2"} onSubmit={(a, el) => submit(a, el)} />
      </div>
    );
  }
  if (phase === "done" && final) {
    return (
      <div className="space-y-4">
        <div className="card flex flex-wrap items-center justify-between gap-4">
          <div>
            <div className="text-sm text-slate-500">{attempt?.title}</div>
            <div className="text-3xl font-semibold">{final.score}<span className="text-lg text-slate-400"> / {final.max_score}</span>
              <span className="ml-3 text-lg text-slate-500">{final.percent}%</span></div>
            <div className="text-sm text-slate-600">
              Module 2 route: <b>{final.route === "upper" ? "harder (upper)" : "easier (lower)"}</b>
            </div>
          </div>
          {final.band && (
            <div className="text-right">
              <div className="text-sm text-slate-500">Estimated band</div>
              <div className="text-3xl font-semibold">{final.band.band.toFixed(1)}</div>
              <div className="text-sm text-slate-600">CEFR {final.band.cefr}</div>
            </div>
          )}
        </div>
        {final.stages.map((st) => (
          <div key={st.stage} className="space-y-2">
            <h2 className="font-semibold">{st.stage === "router" ? "Module 1" : `Module 2 (${st.stage})`} — {st.score} / {st.max_score}</h2>
            <ObjectiveResults results={st.sets} titles={titles} />
          </div>
        ))}
      </div>
    );
  }
  return <p className="text-sm text-slate-500">Loading…</p>;
}

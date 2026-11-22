"use client";

import { useCallback, useState } from "react";
import { practice, type BuildItem, type BuildOut, type PracticeSet } from "@/lib/api";
import { useCountdown } from "@/lib/useCountdown";
import Timer from "@/components/Timer";
import StartScreen from "./StartScreen";

// slot value = index into item.chunks (so duplicate chunk texts stay distinct), or null
type Fill = (number | null)[];

export default function BuildSentenceRunner({ set, items, onDone }: {
  set: PracticeSet; items: BuildItem[]; onDone?: (responseId: string) => void;
}) {
  const [phase, setPhase] = useState<"intro" | "test" | "done">("intro");
  const [idx, setIdx] = useState(0);
  const [fills, setFills] = useState<Record<string, Fill>>(() =>
    Object.fromEntries(items.map((i) => [i.id, Array(i.slots).fill(null)])),
  );
  const [result, setResult] = useState<BuildOut | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  const submit = useCallback(
    async (timedOut: boolean) => {
      setSubmitting(true);
      setErr(null);
      const answers = Object.fromEntries(
        // keep slot positions: empty slots are sent as "" so a gap stays a gap
        items.map((i) => {
          const f = fills[i.id];
          return [i.id, f.every((x) => x === null) ? [] : f.map((x) => (x === null ? "" : i.chunks[x]))];
        }),
      );
      try {
        const r = await practice.submitBuild(set.id, answers, timer.elapsed(), timedOut);
        timer.stop();
        if (onDone) {
          onDone(r.response_id);
          return;
        }
        setResult(r);
        setPhase("done");
      } catch (e) {
        setErr((e as Error).message);
      } finally {
        setSubmitting(false);
      }
    },
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [fills, items, set.id, onDone],
  );
  const timer = useCountdown(set.time_limit_s, () => submit(true));

  if (phase === "intro") {
    return (
      <StartScreen title={set.title} directions={set.directions} minutes={Math.round(set.time_limit_s / 60)}
        onStart={() => { timer.start(); setPhase("test"); }} />
    );
  }
  if (phase === "done" && result) return <BuildResults result={result} items={items} />;

  const item = items[idx];
  const fill = fills[item.id];
  const used = new Set(fill.filter((x) => x !== null));
  const place = (chunkIdx: number) => {
    const slot = fill.indexOf(null);
    if (slot < 0) return;
    const next = [...fill];
    next[slot] = chunkIdx;
    setFills({ ...fills, [item.id]: next });
  };
  const unplace = (slot: number) => {
    const next = [...fill];
    next[slot] = null;
    setFills({ ...fills, [item.id]: next });
  };
  const parts = item.template.split("[]");
  const answered = items.filter((i) => fills[i.id].every((x) => x !== null)).length;

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <span className="text-sm text-slate-600">
          Question {idx + 1} of {items.length} · {answered} complete
        </span>
        <Timer remaining={timer.remaining} total={set.time_limit_s} />
      </div>

      <div className="card space-y-6">
        <div className="rounded-lg bg-slate-50 p-4">
          <div className="text-xs font-medium uppercase tracking-wide text-slate-500">{item.speaker}</div>
          <div className="mt-1 text-lg">{item.context}</div>
        </div>

        <div className="flex flex-wrap items-center gap-x-1.5 gap-y-3 text-lg leading-9">
          {parts.map((p, i) => (
            <span key={i} className="contents">
              {p.trim() && <span>{p.trim()}</span>}
              {i < parts.length - 1 && (
                fill[i] === null ? (
                  <span className="inline-block min-w-20 border-b-2 border-dashed border-slate-400">&nbsp;</span>
                ) : (
                  <button onClick={() => unplace(i)} title="Click to remove"
                    className="rounded-md border border-indigo-300 bg-indigo-50 px-2 text-indigo-800 hover:bg-indigo-100">
                    {item.chunks[fill[i] as number]}
                  </button>
                )
              )}
            </span>
          ))}
        </div>

        <div className="flex flex-wrap gap-2 border-t border-slate-100 pt-4">
          {item.chunks.map((c, ci) => (
            <button key={ci} onClick={() => place(ci)} disabled={used.has(ci) || !fill.includes(null)}
              className="rounded-md border border-slate-300 bg-white px-3 py-1.5 hover:bg-slate-100 disabled:invisible">
              {c}
            </button>
          ))}
        </div>
      </div>

      {err && <p className="text-sm text-red-700">{err}</p>}
      <div className="flex justify-between">
        <button className="btn-ghost" onClick={() => setIdx(idx - 1)} disabled={idx === 0}>← Back</button>
        {idx < items.length - 1 ? (
          <button className="btn-primary" onClick={() => setIdx(idx + 1)}>Next →</button>
        ) : (
          <button className="btn-primary" onClick={() => submit(false)} disabled={submitting}>
            {submitting ? "Submitting…" : `Submit (${answered}/${items.length} complete)`}
          </button>
        )}
      </div>
    </div>
  );
}

export function BuildResults({ result, items }: { result: BuildOut; items: BuildItem[] }) {
  const byId = Object.fromEntries(items.map((i) => [i.id, i]));
  return (
    <div className="space-y-4">
      <div className="card flex items-center justify-between">
        <div>
          <div className="text-sm text-slate-500">Build a Sentence score</div>
          <div className="text-3xl font-semibold">
            {result.score} <span className="text-lg text-slate-400">/ {result.max_score}</span>
          </div>
        </div>
        <button className="btn-ghost" onClick={() => window.location.reload()}>Try again</button>
      </div>
      {result.results.map((r, i) => (
        <div key={r.item_id} className={`card border-l-4 ${r.correct ? "border-l-emerald-500" : "border-l-red-400"}`}>
          <div className="text-xs text-slate-500">
            {i + 1}. {byId[r.item_id]?.speaker}: “{byId[r.item_id]?.context}”
          </div>
          <div className="mt-2">
            <span className={r.correct ? "text-emerald-700" : "text-red-700"}>{r.correct ? "✓" : "✗"}</span>{" "}
            {r.your_sentence}
          </div>
          {!r.correct && <div className="mt-1 text-emerald-800">Correct: {r.correct_sentence}</div>}
          {r.explanation && <div className="mt-1 text-sm text-slate-600">{r.explanation}</div>}
        </div>
      ))}
    </div>
  );
}

"use client";

import type { ItemResult, ObjectiveResult } from "@/lib/api";

function ItemBlock({ r }: { r: ItemResult }) {
  if (r.task === "complete-the-words") {
    return (
      <div className="space-y-2">
        <div className="flex flex-wrap gap-2 text-sm">
          {r.questions.map((q) => (
            <span key={q.id} className={`rounded-md border px-2 py-0.5 ${q.correct
              ? "border-emerald-200 bg-emerald-50 text-emerald-800" : "border-red-200 bg-red-50 text-red-800"}`}>
              {String(q.answer)}{!q.correct && <span className="text-red-500"> (you: {String(q.chosen || "—")})</span>}
            </span>
          ))}
        </div>
        {r.full_text && <p className="text-sm leading-7 text-slate-600">{r.full_text}</p>}
      </div>
    );
  }
  return (
    <div className="space-y-3">
      {r.questions.map((q, n) => (
        <div key={q.id} className="text-sm">
          <div className="font-medium">
            <span className={q.correct ? "text-emerald-700" : "text-red-700"}>{q.correct ? "✓" : "✗"}</span> {n + 1}. {q.prompt}
          </div>
          <ul className="ml-5 mt-1 space-y-0.5">
            {q.options?.map((o, k) => (
              <li key={k} className={k === q.answer ? "font-medium text-emerald-800"
                : k === q.chosen ? "text-red-700 line-through" : "text-slate-500"}>
                {o}{k === q.answer && " ✓"}{k === q.chosen && k !== q.answer && " (your answer)"}
              </li>
            ))}
          </ul>
          {q.explanation && <div className="ml-5 mt-1 text-slate-600">{q.explanation}</div>}
        </div>
      ))}
      {r.transcript && (
        <details className="rounded-lg bg-slate-50 p-3 text-sm">
          <summary className="cursor-pointer font-medium">Transcript</summary>
          <div className="mt-2 space-y-1">
            {r.transcript.map((l, i) => <p key={i}><b>{l.speaker}:</b> {l.text}</p>)}
          </div>
        </details>
      )}
    </div>
  );
}

export default function ObjectiveResults({ results, titles }: {
  results: ObjectiveResult[]; titles?: Record<string, string>;
}) {
  return (
    <div className="space-y-4">
      {results.map((s) => (
        <div key={s.set_id} className="card space-y-4">
          <div className="flex items-baseline justify-between">
            <h3 className="font-semibold">{titles?.[s.set_id] ?? s.set_id}</h3>
            <span className="text-lg font-semibold">{s.score}<span className="text-sm text-slate-400"> / {s.max_score}</span></span>
          </div>
          {s.items.map((r) => <ItemBlock key={r.item_id} r={r} />)}
        </div>
      ))}
    </div>
  );
}

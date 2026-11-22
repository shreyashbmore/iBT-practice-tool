"use client";

import { useState } from "react";
import type { ErrorNote, Level, WritingScore } from "@/lib/api";

const LEVEL_STYLE: Record<Level, string> = {
  strong: "bg-emerald-50 text-emerald-700 border-emerald-200",
  adequate: "bg-sky-50 text-sky-700 border-sky-200",
  limited: "bg-amber-50 text-amber-800 border-amber-200",
  weak: "bg-red-50 text-red-700 border-red-200",
};

type Span = { start: number; end: number; kind: "evidence" | "error"; note?: ErrorNote };

function findSpans(text: string, s: WritingScore): Span[] {
  const lower = text.toLowerCase();
  const spans: Span[] = [];
  const add = (q: string, kind: Span["kind"], note?: ErrorNote) => {
    const i = lower.indexOf(q.toLowerCase());
    if (q && i >= 0) spans.push({ start: i, end: i + q.length, kind, note });
  };
  s.errors.forEach((e) => add(e.quote, "error", e));
  s.dimensions.forEach((d) => d.evidence.forEach((q) => add(q, "evidence")));
  // keep non-overlapping spans, errors first
  spans.sort((a, b) => (a.kind === b.kind ? a.start - b.start : a.kind === "error" ? -1 : 1));
  const kept: Span[] = [];
  for (const sp of spans) if (!kept.some((k) => sp.start < k.end && k.start < sp.end)) kept.push(sp);
  return kept.sort((a, b) => a.start - b.start);
}

function AnnotatedText({ text, score }: { text: string; score: WritingScore }) {
  const spans = findSpans(text, score);
  const out: React.ReactNode[] = [];
  let pos = 0;
  spans.forEach((sp, i) => {
    if (sp.start > pos) out.push(text.slice(pos, sp.start));
    const t = text.slice(sp.start, sp.end);
    out.push(
      sp.kind === "error" ? (
        <mark key={i} title={`→ ${sp.note?.correction}${sp.note?.explanation ? ` — ${sp.note.explanation}` : ""}`}
          className="rounded bg-transparent text-inherit underline decoration-red-500 decoration-wavy underline-offset-4">
          {t}
        </mark>
      ) : (
        <mark key={i} className="rounded bg-indigo-100 px-0.5 text-inherit">{t}</mark>
      ),
    );
    pos = sp.end;
  });
  out.push(text.slice(pos));
  return <div className="whitespace-pre-wrap rounded-lg bg-slate-50 p-4 leading-7">{out}</div>;
}

export default function FeedbackReport({ score, text }: { score: WritingScore; text: string }) {
  const [showRewrite, setShowRewrite] = useState(false);
  const cost = score.usage.cost_usd;

  return (
    <div className="space-y-4">
      <div className="card flex flex-wrap items-center gap-6">
        <div>
          <div className="text-sm text-slate-500">Estimated rubric score</div>
          <div className="text-4xl font-semibold">
            {score.score} <span className="text-xl text-slate-400">/ {score.max_score}</span>
          </div>
          <div className="text-sm font-medium text-slate-700">{score.label}</div>
        </div>
        <div className="flex-1 text-sm text-slate-700">{score.rationale}</div>
        {!score.guard && (
          <div className="text-right text-xs text-slate-500">
            <span className={`rounded-full border px-2 py-0.5 ${score.confidence === "high"
              ? "border-emerald-200 bg-emerald-50 text-emerald-700" : "border-amber-200 bg-amber-50 text-amber-800"}`}>
              {score.confidence === "high" ? "consistent" : "low confidence"}
            </span>
            <div className="mt-1">scoring passes: {score.samples.join(" · ")}</div>
          </div>
        )}
      </div>

      {score.dimensions.length > 0 && (
        <div className="grid gap-3 sm:grid-cols-2">
          {score.dimensions.map((d) => (
            <div key={d.id} className="card space-y-2">
              <div className="flex items-center justify-between">
                <h3 className="font-medium">{d.name}</h3>
                <span className={`rounded-full border px-2 py-0.5 text-xs ${LEVEL_STYLE[d.level]}`}>{d.level}</span>
              </div>
              <p className="text-sm text-slate-700">{d.comment}</p>
              {d.evidence.map((q) => (
                <blockquote key={q} className="border-l-2 border-indigo-300 pl-2 text-sm italic text-slate-600">“{q}”</blockquote>
              ))}
            </div>
          ))}
        </div>
      )}

      {text && !score.guard && (
        <div className="card space-y-2">
          <div className="flex items-center justify-between">
            <h3 className="font-medium">Your response</h3>
            <span className="text-xs text-slate-500">
              <mark className="bg-indigo-100 px-1">evidence</mark>{" "}
              <span className="underline decoration-red-500 decoration-wavy">error</span> (hover for correction)
            </span>
          </div>
          <AnnotatedText text={text} score={score} />
        </div>
      )}

      {score.errors.length > 0 && (
        <div className="card">
          <h3 className="mb-2 font-medium">Language to fix</h3>
          <ul className="space-y-2 text-sm">
            {score.errors.map((e, i) => (
              <li key={i}>
                <span className="text-red-700 line-through decoration-red-300">{e.quote}</span>{" → "}
                <span className="font-medium text-emerald-800">{e.correction}</span>
                <span className="ml-2 rounded bg-slate-100 px-1.5 text-xs text-slate-500">{e.type.replace("_", " ")}</span>
                {e.explanation && <div className="text-slate-600">{e.explanation}</div>}
              </li>
            ))}
          </ul>
        </div>
      )}

      {score.next_steps.length > 0 && (
        <div className="card">
          <h3 className="mb-2 font-medium">To reach the next band</h3>
          <ul className="list-disc space-y-1 pl-5 text-sm">
            {score.next_steps.map((s) => <li key={s}>{s}</li>)}
          </ul>
        </div>
      )}

      {score.improved_version && (
        <div className="card">
          <button className="btn-ghost" onClick={() => setShowRewrite(!showRewrite)}>
            {showRewrite ? "Hide" : "Show"} a stronger version of your response
          </button>
          {showRewrite && (
            <p className="mt-3 whitespace-pre-wrap rounded-lg bg-emerald-50 p-4 leading-7">{score.improved_version}</p>
          )}
        </div>
      )}

      <p className="text-xs text-slate-500">
        Estimated by {score.model ?? "rules"}{score.provider ? ` (${score.provider})` : ""} · rubric {score.rubric_version}
        {score.prompt_version && ` · prompt ${score.prompt_version}`}
        {score.usage.prompt_tokens > 0 && ` · ${score.usage.prompt_tokens + score.usage.completion_tokens} tokens`}
        {cost != null && ` · ~$${cost.toFixed(4)}`}
        {score.latency_ms > 0 && ` · ${(score.latency_ms / 1000).toFixed(1)} s`}.
        {" "}This is an AI estimate against paraphrased ETS rubric descriptors, not an official score.
      </p>
    </div>
  );
}

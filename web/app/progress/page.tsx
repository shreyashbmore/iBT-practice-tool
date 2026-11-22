"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { progressApi, type Progress } from "@/lib/api";
import { SECTIONS, taskName } from "@/lib/tasks";
import LineChart from "@/components/charts/LineChart";

const day = (iso: string) => new Date(iso).toLocaleDateString(undefined, { month: "short", day: "numeric" });

function Stat({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <div className="text-xs text-slate-500">{label}</div>
      <div className="text-lg font-semibold tabular-nums">{value}</div>
    </div>
  );
}

export default function ProgressPage() {
  const [p, setP] = useState<Progress | null>(null);
  const [err, setErr] = useState<string | null>(null);
  useEffect(() => {
    progressApi.get().then(setP).catch((e: Error) => setErr(e.message));
  }, []);

  if (err) return <div className="card border-red-200 bg-red-50 text-sm text-red-800">{err}</div>;
  if (!p) return <p className="text-sm text-slate-500">Loading…</p>;

  const order = [...SECTIONS.flatMap((s) => s.tasks.map((t) => t.id)), "reading-test", "listening-test"];
  const tasks = order.filter((t) => p.tasks[t]);
  const lastMock = p.mocks[p.mocks.length - 1];

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-semibold">Progress</h1>

      <section className="card space-y-3">
        <div className="flex items-baseline justify-between">
          <h2 className="font-semibold">Full mock tests</h2>
          <Link href="/mock/mock-01" className="text-sm text-indigo-700 hover:underline">Take a mock test →</Link>
        </div>
        {p.mocks.length === 0 ? (
          <p className="text-sm text-slate-500">No completed mock tests yet.</p>
        ) : (
          <>
            <div className="flex flex-wrap gap-8">
              <Stat label="Latest overall band" value={`${lastMock.band.toFixed(1)} (${lastMock.cefr})`} />
              <Stat label="Comparable total" value={`≈ ${lastMock.comparable_total} / 120`} />
              {["reading", "listening", "writing", "speaking"].map((s) => (
                <Stat key={s} label={s[0].toUpperCase() + s.slice(1)} value={lastMock.sections[s]?.toFixed(1) ?? "—"} />
              ))}
            </div>
            {p.mocks.length > 1 && (
              <LineChart title="Overall band per mock test" yMin={1} yMax={6} yTicks={[1, 2, 3, 4, 5, 6]}
                format={(v) => v.toFixed(1)}
                points={p.mocks.map((m) => ({ x: day(m.date), y: m.band, label: `band ${m.band.toFixed(1)} · ${m.cefr}` }))} />
            )}
          </>
        )}
      </section>

      <section className="space-y-3">
        <h2 className="font-semibold">By task</h2>
        {tasks.length === 0 && <p className="text-sm text-slate-500">Practise a task to see your progress here.</p>}
        <div className="grid gap-4 lg:grid-cols-2">
          {tasks.map((t) => {
            const s = p.tasks[t];
            return (
              <div key={t} className="card space-y-3">
                <div className="flex items-baseline justify-between">
                  <h3 className="font-medium">{taskName(t)}</h3>
                  <span className="text-xs text-slate-500">{s.attempts} response{s.attempts === 1 ? "" : "s"}</span>
                </div>
                <div className="flex gap-8">
                  <Stat label="Last" value={`${Math.round(s.last_pct)}%`} />
                  <Stat label="Best" value={`${Math.round(s.best_pct)}%`} />
                  <Stat label="Average" value={`${Math.round(s.avg_pct)}%`} />
                </div>
                {s.history.length > 1 && (
                  <LineChart title={`${taskName(t)} score over time`} yMin={0} yMax={100} yTicks={[0, 50, 100]} height={120}
                    format={(v) => `${Math.round(v)}%`}
                    points={s.history.map((h) => ({ x: day(h.date), y: h.pct, label: `${h.score} / ${h.max} (${Math.round(h.pct)}%)` }))} />
                )}
              </div>
            );
          })}
        </div>
      </section>
    </div>
  );
}

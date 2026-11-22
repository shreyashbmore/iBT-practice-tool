"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { forms, type FormSummary } from "@/lib/api";

export default function SectionTests() {
  const [list, setList] = useState<FormSummary[]>([]);
  useEffect(() => {
    forms.list().then(setList).catch(() => setList([]));
  }, []);
  if (list.length === 0) return null;
  return (
    <>
    <div className="card flex flex-wrap items-center justify-between gap-3 border-indigo-200 bg-indigo-50/50">
      <div>
        <h2 className="font-semibold">Full mock test</h2>
        <p className="text-sm text-slate-600">All four sections in the 2026 order, with estimated 1–6 bands, CEFR and a comparable 0–120 total.</p>
      </div>
      <Link href="/mock/mock-01" className="btn-primary">Start mock test</Link>
    </div>
    <div className="card">
      <h2 className="font-semibold">Adaptive section tests</h2>
      <p className="text-sm text-slate-600">Module 1, then an easier or harder module 2 — like the real Reading and Listening sections.</p>
      <div className="mt-3 flex flex-wrap gap-2">
        {list.map((f) => (
          <Link key={f.id} href={`/test/${f.id}`} className="btn-ghost">{f.title} · ~{f.est_minutes} min</Link>
        ))}
      </div>
    </div>
    </>
  );
}

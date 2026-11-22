"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useEffect, useState } from "react";
import { practice, type SetSummary } from "@/lib/api";
import { findTask } from "@/lib/tasks";

export default function TaskSets() {
  const { task } = useParams<{ task: string }>();
  const def = findTask(task);
  const [sets, setSets] = useState<SetSummary[] | null>(null);
  const [err, setErr] = useState<string | null>(null);

  useEffect(() => {
    practice.listSets(task).then(setSets).catch((e: Error) => setErr(e.message));
  }, [task]);

  return (
    <div className="space-y-6">
      <div>
        <Link href="/" className="text-sm text-slate-500 hover:underline">← All tasks</Link>
        <h1 className="mt-1 text-2xl font-semibold">{def?.name ?? task}</h1>
        {def && <p className="text-sm text-slate-600">Scoring: {def.scoring}</p>}
      </div>
      {err && <div className="card border-red-200 bg-red-50 text-sm text-red-800">{err}</div>}
      {sets && sets.length === 0 && <p className="text-sm text-slate-500">No practice sets yet for this task.</p>}
      <div className="grid gap-3 sm:grid-cols-2">
        {sets?.map((s) => (
          <Link key={s.id} href={`/practice/${task}/${s.id}`} className="card block hover:border-indigo-300">
            <div className="font-medium">{s.title}</div>
            <div className="mt-1 text-xs text-slate-500">
              {s.n_items} item{s.n_items > 1 ? "s" : ""} · {Math.round(s.time_limit_s / 60)} min
            </div>
          </Link>
        ))}
      </div>
    </div>
  );
}

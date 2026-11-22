"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { practice, type SavedResponse } from "@/lib/api";
import { taskName } from "@/lib/tasks";

export default function History() {
  const [rows, setRows] = useState<SavedResponse[] | null>(null);
  const [err, setErr] = useState<string | null>(null);
  useEffect(() => {
    practice.responses().then(setRows).catch((e: Error) => setErr(e.message));
  }, []);

  return (
    <div className="space-y-4">
      <h1 className="text-2xl font-semibold">History</h1>
      {err && <div className="card border-red-200 bg-red-50 text-sm text-red-800">{err}</div>}
      {rows && rows.length === 0 && <p className="text-sm text-slate-500">No responses yet. <Link className="underline" href="/">Start practising</Link>.</p>}
      {rows && rows.length > 0 && (
        <table className="w-full overflow-hidden rounded-xl border border-slate-200 bg-white text-sm">
          <thead className="bg-slate-50 text-left text-slate-500">
            <tr>
              <th className="p-3">When</th><th className="p-3">Task</th><th className="p-3">Set</th>
              <th className="p-3">Time</th><th className="p-3">Score</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((r) => (
              <tr key={r.id} className="border-t border-slate-100">
                <td className="p-3">
                  <Link href={`/report/${r.id}`} className="text-indigo-700 hover:underline">
                    {new Date(r.created_at).toLocaleString()}
                  </Link>
                </td>
                <td className="p-3">{taskName(r.task)}</td>
                <td className="p-3">{r.set_id}</td>
                <td className="p-3">
                  {r.time_spent_s != null ? `${Math.round(r.time_spent_s)} s` : "—"}
                  {r.timed_out && <span className="ml-1 text-amber-700">(timed out)</span>}
                </td>
                <td className="p-3">{r.score != null ? (String(r.task) === "mock-test" ? `band ${r.score.toFixed(1)}` : `${r.score} / ${r.max_score}`) : <span className="text-slate-400">pending</span>}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  );
}

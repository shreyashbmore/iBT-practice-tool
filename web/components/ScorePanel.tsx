"use client";

import Link from "next/link";
import { useCallback, useEffect, useRef, useState } from "react";
import { scoring, type WritingScore } from "@/lib/api";
import FeedbackReport from "./FeedbackReport";

/** Runs (or shows existing) rubric scoring for a saved writing response. */
export default function ScorePanel({ responseId, text, initial, auto = true }: {
  responseId: string;
  text: string;
  initial?: WritingScore | null;
  auto?: boolean;
}) {
  const [score, setScore] = useState<WritingScore | null>(initial ?? null);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  const started = useRef(false);

  const run = useCallback(async () => {
    setBusy(true);
    setErr(null);
    try {
      setScore(await scoring.score(responseId));
    } catch (e) {
      setErr((e as Error).message);
    } finally {
      setBusy(false);
    }
  }, [responseId]);

  useEffect(() => {
    if (auto && !initial && !started.current) {
      started.current = true;
      run();
    }
  }, [auto, initial, run]);

  if (score) {
    return (
      <div className="space-y-2">
        <FeedbackReport score={score} text={text} />
        <button className="btn-ghost" onClick={run} disabled={busy}>{busy ? "Re-scoring…" : "Re-score"}</button>
      </div>
    );
  }
  return (
    <div className="card space-y-2 text-sm">
      {busy && <p className="animate-pulse text-slate-600">Scoring against the rubric… (usually 10–40 s)</p>}
      {err && (
        <>
          <p className="text-red-700">{err}</p>
          <div className="flex gap-2">
            <button className="btn-primary" onClick={run}>Try again</button>
            <Link href="/settings" className="btn-ghost">Settings</Link>
          </div>
        </>
      )}
      {!busy && !err && <button className="btn-primary" onClick={run}>Score this response</button>}
    </div>
  );
}

"use client";

import Link from "next/link";
import { useEffect, useRef, useState } from "react";
import { speaking, type PracticeSet, type SpeakingItem, type SpeakingOut } from "@/lib/api";
import { beep, openMic, playBlob, record } from "@/lib/mic";
import SpeakingResultCard from "./SpeakingResultCard";

type Phase = "intro" | "preparing" | "listening" | "recording" | "saving" | "done" | "error";

export default function SpeakingRunner({ set, items, onDone }: {
  set: PracticeSet; items: SpeakingItem[]; onDone?: (responseIds: string[]) => void;
}) {
  const [phase, setPhase] = useState<Phase>("intro");
  const [idx, setIdx] = useState(0);
  const [remaining, setRemaining] = useState(0);
  const [results, setResults] = useState<(SpeakingOut | null)[]>([]);
  const [err, setErr] = useState<string | null>(null);
  const stopRef = useRef<(() => void) | null>(null);
  const cancelled = useRef(false);
  const isLR = set.task === "listen-and-repeat";

  useEffect(() => {
    cancelled.current = false; // React strict mode mounts twice in dev
    return () => {
      cancelled.current = true;
      stopRef.current?.();
    };
  }, []);

  const run = async () => {
    setErr(null);
    setPhase("preparing");
    let stream: MediaStream;
    let audio: Blob[];
    try {
      stream = await openMic();
    } catch {
      setErr("Microphone access was blocked. Allow the microphone for this site and try again.");
      setPhase("error");
      return;
    }
    try {
      audio = await Promise.all(items.map((i) => speaking.itemAudio(set.id, i.id)));
    } catch (e) {
      stream.getTracks().forEach((t) => t.stop());
      setErr(`Could not load the audio: ${(e as Error).message}`);
      setPhase("error");
      return;
    }

    const attemptId = crypto.randomUUID();
    const uploads: Promise<SpeakingOut | null>[] = [];
    for (let k = 0; k < items.length && !cancelled.current; k++) {
      const item = items[k];
      setIdx(k);
      setPhase("listening");
      await playBlob(audio[k]);
      if (cancelled.current) break;
      await beep();
      setPhase("recording");
      const rec = record(stream);
      const started = performance.now();
      await new Promise<void>((resolve) => {
        const tick = setInterval(() => {
          const left = item.response_time_s - (performance.now() - started) / 1000;
          setRemaining(Math.max(0, left));
          if (left <= 0) finish();
        }, 100);
        const finish = () => {
          clearInterval(tick);
          rec.stop();
          stopRef.current = null;
          resolve();
        };
        stopRef.current = finish;
      });
      const blob = await rec.done;
      const spent = Math.round((performance.now() - started) / 100) / 10;
      uploads.push(
        speaking.submit(set.id, item.id, blob, attemptId, spent).catch((e: Error) => {
          setErr(`Upload failed for question ${k + 1}: ${e.message}`);
          return null;
        }),
      );
      setPhase("saving");
      await new Promise((r) => setTimeout(r, 1200)); // short gap before the next item, like the real test
    }
    stream.getTracks().forEach((t) => t.stop());
    setPhase("saving");
    const done = await Promise.all(uploads);
    if (onDone) {
      onDone(done.filter((r): r is SpeakingOut => !!r).map((r) => r.response_id));
      return;
    }
    setResults(done);
    setPhase("done");
  };

  if (phase === "intro" || phase === "error") {
    return (
      <div className="card space-y-4">
        <h1 className="text-xl font-semibold">{set.title}</h1>
        {set.scene && <p className="rounded-lg bg-indigo-50 p-3 text-indigo-900">{set.scene}</p>}
        <p className="text-slate-700">{set.directions}</p>
        <ul className="list-disc pl-5 text-sm text-slate-600">
          <li>{items.length} {isLR ? "sentences" : "questions"}; each is played once.</li>
          <li>Recording starts after the beep and stops automatically
            {isLR ? "" : " (you can also finish early)"}.</li>
          <li>Use headphones and a quiet room. <Link className="underline" href="/mic-check">Test your mic first</Link>.</li>
        </ul>
        {err && <p className="text-sm text-red-700">{err} <Link href="/settings" className="underline">Settings</Link></p>}
        <button className="btn-primary" onClick={run}>{phase === "error" ? "Try again" : "Start"}</button>
      </div>
    );
  }

  if (phase === "done") {
    const lrScores = results.map((r) => r?.listen_repeat?.score).filter((s): s is number => s != null);
    return (
      <div className="space-y-4">
        <div className="card flex items-center justify-between">
          <div>
            <div className="text-sm text-slate-500">{set.title}</div>
            {isLR ? (
              <div className="text-3xl font-semibold">
                {lrScores.reduce((a, b) => a + b, 0)}
                <span className="text-lg text-slate-400"> / {items.length * 5}</span>
              </div>
            ) : (
              <div className="text-lg font-medium">Each answer is scored below (0–5).</div>
            )}
          </div>
          <button className="btn-ghost" onClick={() => window.location.reload()}>Practise again</button>
        </div>
        {err && <p className="text-sm text-red-700">{err}</p>}
        {results.map((r, i) => r && <SpeakingResultCard key={r.response_id} out={r} index={i} />)}
      </div>
    );
  }

  const item = items[idx];
  const pct = phase === "recording" ? (remaining / item.response_time_s) * 100 : 100;
  return (
    <div className="space-y-4">
      <div className="text-sm text-slate-600">{isLR ? "Sentence" : "Question"} {idx + 1} of {items.length}</div>
      {set.scene && <div className="card text-slate-700">{set.scene}</div>}
      <div className="card flex flex-col items-center gap-4 py-10">
        {phase === "preparing" && <p className="animate-pulse text-slate-600">Preparing audio and microphone…</p>}
        {phase === "listening" && <p className="text-lg">🔊 Listen…</p>}
        {phase === "recording" && (
          <>
            <p className="flex items-center gap-2 text-lg font-medium text-red-700">
              <span className="inline-block h-3 w-3 animate-pulse rounded-full bg-red-600" /> Recording — speak now
            </p>
            <div className="h-2 w-72 overflow-hidden rounded bg-slate-200">
              <div className="h-full bg-red-500 transition-[width] duration-100" style={{ width: `${pct}%` }} />
            </div>
            <p className="font-mono text-sm tabular-nums text-slate-600">{Math.ceil(remaining)} s</p>
            {!isLR && <button className="btn-ghost" onClick={() => stopRef.current?.()}>Finish answer</button>}
          </>
        )}
        {phase === "saving" && <p className="text-slate-600">Saved ✓</p>}
      </div>
    </div>
  );
}

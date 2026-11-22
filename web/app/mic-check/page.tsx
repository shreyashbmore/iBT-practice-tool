"use client";

import { useEffect, useState } from "react";
import { api, type TranscribeOut } from "@/lib/api";
import { useRecorder } from "@/lib/useRecorder";

const SAMPLE = "The library will be closed on Friday afternoon for scheduled maintenance.";

export default function MicCheck() {
  const rec = useRecorder();
  const [ttsText, setTtsText] = useState(SAMPLE);
  const [ttsUrl, setTtsUrl] = useState<string | null>(null);
  const [recUrl, setRecUrl] = useState<string | null>(null);
  const [result, setResult] = useState<TranscribeOut | null>(null);
  const [busy, setBusy] = useState<"tts" | "stt" | null>(null);
  const [err, setErr] = useState<string | null>(null);

  useEffect(() => {
    if (!rec.blob) return;
    const u = URL.createObjectURL(rec.blob);
    setRecUrl(u);
    return () => URL.revokeObjectURL(u);
  }, [rec.blob]);

  const speak = async () => {
    setBusy("tts");
    setErr(null);
    try {
      const b = await api.tts(ttsText);
      if (ttsUrl) URL.revokeObjectURL(ttsUrl);
      const u = URL.createObjectURL(b);
      setTtsUrl(u);
      new Audio(u).play().catch(() => {});
    } catch (e) {
      setErr((e as Error).message);
    } finally {
      setBusy(null);
    }
  };

  const transcribe = async () => {
    if (!rec.blob) return;
    setBusy("stt");
    setErr(null);
    try {
      setResult(await api.transcribe(rec.blob, true));
    } catch (e) {
      setErr((e as Error).message);
    } finally {
      setBusy(null);
    }
  };

  const f = result?.features;

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-semibold">Mic check</h1>
        <p className="mt-1 text-sm text-slate-600">
          Checks Deepgram text-to-speech and speech-to-text, plus the delivery measures used for Speaking scoring.
        </p>
      </div>
      {err && <div className="card border-red-200 bg-red-50 text-sm text-red-800">{err}</div>}

      <section className="card space-y-3">
        <h2 className="font-semibold">1 · Listen (text-to-speech)</h2>
        <textarea className="input h-20" value={ttsText} onChange={(e) => setTtsText(e.target.value)} />
        <div className="flex items-center gap-3">
          <button className="btn-primary" onClick={speak} disabled={busy !== null || !ttsText.trim()}>
            {busy === "tts" ? "Generating…" : "Play"}
          </button>
          {ttsUrl && <audio controls src={ttsUrl} className="h-9" />}
        </div>
      </section>

      <section className="card space-y-3">
        <h2 className="font-semibold">2 · Repeat it (speech-to-text)</h2>
        <p className="text-sm text-slate-600">Record yourself repeating the sentence above, like a Listen and Repeat item.</p>
        <div className="flex items-center gap-3">
          {rec.state !== "recording" ? (
            <button className="btn-primary" onClick={rec.start} disabled={busy !== null}>● Record</button>
          ) : (
            <button className="btn-ghost" onClick={rec.stop}>■ Stop</button>
          )}
          {rec.state === "recording" && (
            <>
              <div className="h-2 w-40 overflow-hidden rounded bg-slate-200">
                <div className="h-full bg-emerald-500 transition-[width]"
                  style={{ width: `${Math.min(100, rec.level * 160)}%` }} />
              </div>
              <span className="text-sm tabular-nums text-slate-600">{rec.elapsed.toFixed(1)} s</span>
            </>
          )}
          {recUrl && rec.state === "stopped" && <audio controls src={recUrl} className="h-9" />}
          {rec.blob && (
            <button className="btn-ghost" onClick={transcribe} disabled={busy !== null}>
              {busy === "stt" ? "Transcribing…" : "Transcribe"}
            </button>
          )}
        </div>
        {rec.error && <p className="text-sm text-red-700">{rec.error}</p>}

        {result && (
          <div className="space-y-4 pt-2">
            <div>
              <p className="label">Transcript (low-confidence words underlined)</p>
              <p className="rounded-lg bg-slate-50 p-3 leading-7">
                {result.transcript.words.length === 0 && <span className="text-slate-500">(no speech detected)</span>}
                {result.transcript.words.map((w, i) => (
                  <span key={i}
                    title={`confidence ${w.confidence.toFixed(2)} · ${w.start.toFixed(2)}–${w.end.toFixed(2)} s`}
                    className={w.confidence < 0.6 ? "underline decoration-red-400 decoration-wavy" : ""}>
                    {(w.punctuated ?? w.word) + " "}
                  </span>
                ))}
              </p>
            </div>
            {f && (
              <dl className="grid grid-cols-2 gap-3 text-sm sm:grid-cols-4">
                {[
                  ["Words", f.word_count],
                  ["Speaking rate", `${f.wpm} wpm`],
                  ["Articulation rate", `${f.articulation_rate_wpm} wpm`],
                  ["Pauses > 1 s", f.pauses_over_1s],
                  ["Longest pause", `${f.longest_pause_s} s`],
                  ["Fillers", `${f.filler_count} (${f.fillers_per_min}/min)`],
                  ["Mean confidence", f.mean_confidence.toFixed(2)],
                  ["Model", result.transcript.model ?? "—"],
                ].map(([k, v]) => (
                  <div key={String(k)} className="rounded-lg border border-slate-200 p-3">
                    <dt className="text-xs text-slate-500">{k}</dt>
                    <dd className="font-medium">{v}</dd>
                  </div>
                ))}
              </dl>
            )}
          </div>
        )}
      </section>
    </div>
  );
}

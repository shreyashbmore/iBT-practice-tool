"use client";

import { useState } from "react";
import { speaking, type SpeakingOut, type WritingScore } from "@/lib/api";
import ScorePanel from "@/components/ScorePanel";
import LRDiff from "./LRDiff";

export default function SpeakingResultCard({ out: initial, index, autoScore = true, initialScore }: {
  out: SpeakingOut;
  index?: number;
  autoScore?: boolean;
  initialScore?: WritingScore | null;
}) {
  const [out, setOut] = useState(initial);
  const [busy, setBusy] = useState(false);
  const lr = out.listen_repeat;
  const f = out.features;

  const retry = async () => {
    setBusy(true);
    try {
      setOut(await speaking.process(out.response_id));
    } catch (e) {
      setOut({ ...out, error: (e as Error).message });
    } finally {
      setBusy(false);
    }
  };

  const plain = out.transcript?.words.length
    ? out.transcript.words.map((w) => w.punctuated ?? w.word).join(" ")
    : out.transcript?.text ?? "";

  return (
    <div className="card space-y-3">
      <div className="flex items-start justify-between gap-4">
        <div>
          <div className="text-xs uppercase tracking-wide text-slate-500">
            {index != null && `${index + 1}. `}{out.task === "listen-and-repeat" ? "Sentence" : "Question"}
          </div>
          <div className="font-medium">{out.prompt_text}</div>
        </div>
        {lr && (
          <div className="shrink-0 text-right">
            <div className="text-2xl font-semibold">{lr.score}<span className="text-sm text-slate-400"> / 5</span></div>
          </div>
        )}
      </div>

      <audio controls src={speaking.audioUrl(out.response_id)} className="h-9 w-full max-w-md" />

      {out.error && (
        <div className="flex items-center gap-3 text-sm text-red-700">
          <span>{out.error}</span>
          <button className="btn-ghost" onClick={retry} disabled={busy}>{busy ? "Retrying…" : "Retry transcription"}</button>
        </div>
      )}

      {lr && (
        <>
          <LRDiff tokens={lr.tokens} />
          <p className="text-sm text-slate-600">{lr.reasons.join(" ")}</p>
          <p className="text-xs text-slate-500">Heard: “{lr.transcript || "(nothing)"}”</p>
        </>
      )}

      {out.task === "take-an-interview" && out.transcript && (
        <>
          <div>
            <div className="label">Transcript</div>
            <p className="rounded-lg bg-slate-50 p-3 leading-7">
              {out.transcript.words.length === 0 && <span className="text-slate-500">(no speech detected)</span>}
              {out.transcript.words.map((w, i) => (
                <span key={i} className={w.confidence < 0.6 ? "underline decoration-red-400 decoration-wavy" : ""}
                  title={`confidence ${w.confidence.toFixed(2)}`}>{(w.punctuated ?? w.word) + " "}</span>
              ))}
            </p>
          </div>
          {f && (
            <div className="flex flex-wrap gap-2 text-xs">
              {[
                [`${f.speaking_time_s}s speaking`],
                [`${f.wpm} wpm`],
                [`${f.pauses_over_1s} pause${f.pauses_over_1s === 1 ? "" : "s"} > 1s`],
                [`longest pause ${f.longest_pause_s}s`],
                [`${f.filler_count} filler${f.filler_count === 1 ? "" : "s"}`],
                [`${f.low_confidence_words.length} unclear word${f.low_confidence_words.length === 1 ? "" : "s"}`],
              ].map(([t]) => <span key={t} className="rounded-full bg-slate-100 px-2 py-1 text-slate-600">{t}</span>)}
            </div>
          )}
          <ScorePanel responseId={out.response_id} text={plain} initial={initialScore} auto={autoScore} />
        </>
      )}
    </div>
  );
}

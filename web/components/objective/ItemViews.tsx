"use client";

import { useEffect, useRef, useState } from "react";
import { speaking, type Answers, type CWItem, type ListeningItemPub, type QuestionPub, type ReadingItemPub } from "@/lib/api";
import { playBlob } from "@/lib/mic";

type SetAns = (qid: string, v: number | string) => void;

export function Questions({ qs, answers, onAnswer }: {
  qs: QuestionPub[]; answers: Answers[string] | undefined; onAnswer: SetAns;
}) {
  return (
    <div className="space-y-5">
      {qs.map((q, n) => (
        <fieldset key={q.id} className="space-y-2">
          <legend className="font-medium">{n + 1}. {q.prompt}</legend>
          {q.options.map((o, k) => (
            <label key={k} className={`flex cursor-pointer items-start gap-2 rounded-lg border px-3 py-2 text-sm ${
              answers?.[q.id] === k ? "border-indigo-400 bg-indigo-50" : "border-slate-200 hover:bg-slate-50"}`}>
              <input type="radio" name={q.id} className="mt-0.5" checked={answers?.[q.id] === k}
                onChange={() => onAnswer(q.id, k)} />
              <span>{o}</span>
            </label>
          ))}
        </fieldset>
      ))}
    </div>
  );
}

export function CompleteWordsView({ item, answers, onAnswer }: {
  item: CWItem; answers: Answers[string] | undefined; onAnswer: SetAns;
}) {
  return (
    <div className="card space-y-3">
      {item.title && <h2 className="font-semibold">{item.title}</h2>}
      <p className="leading-[2.6rem] text-[17px]">
        {item.segments.map((s, i) => s.type === "text" ? <span key={i}>{s.text}</span> : (
          <span key={i} className="whitespace-nowrap">
            {s.prefix}
            <input aria-label={`gap ${s.id}`} value={(answers?.[s.id] as string) ?? ""} maxLength={s.length}
              onChange={(e) => onAnswer(s.id, e.target.value.replace(/\s/g, ""))}
              spellCheck={false} autoComplete="off" autoCorrect="off" autoCapitalize="off"
              style={{ width: `${s.length * 0.75 + 0.9}rem` }}
              placeholder={"_".repeat(s.length)}
              className="mx-px rounded border-b-2 border-indigo-400 bg-indigo-50/60 px-1 font-mono text-[16px] tracking-wider outline-none focus:bg-indigo-100" />
          </span>
        ))}
      </p>
    </div>
  );
}

export function ReadingView({ item, answers, onAnswer }: {
  item: ReadingItemPub; answers: Answers[string] | undefined; onAnswer: SetAns;
}) {
  return (
    <div className="grid gap-4 lg:grid-cols-2">
      <div className="card max-h-[70vh] overflow-auto">
        {item.genre && <div className="text-xs uppercase tracking-wide text-slate-500">{item.genre}</div>}
        {item.title && <h2 className="mb-2 text-lg font-semibold">{item.title}</h2>}
        <div className="whitespace-pre-wrap leading-7">{item.text}</div>
      </div>
      <div className="card"><Questions qs={item.questions} answers={answers} onAnswer={onAnswer} /></div>
    </div>
  );
}

/** Plays the recording once (as in the test), then shows the questions. */
export function ListeningView({ setId, item, answers, onAnswer, played, onPlayed }: {
  setId: string; item: ListeningItemPub; answers: Answers[string] | undefined; onAnswer: SetAns;
  played: boolean; onPlayed: () => void;
}) {
  const [state, setState] = useState<"idle" | "loading" | "playing" | "error">("idle");
  const [err, setErr] = useState<string | null>(null);
  const started = useRef(false);

  const play = async () => {
    if (started.current) return;
    started.current = true;
    setState("loading");
    try {
      const blob = await speaking.itemAudio(setId, item.id);
      setState("playing");
      await playBlob(blob);
      onPlayed();
      setState("idle");
    } catch (e) {
      started.current = false;
      setErr((e as Error).message);
      setState("error");
    }
  };

  useEffect(() => {
    if (!played) play();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [item.id]);

  return (
    <div className="space-y-4">
      {item.context && <div className="card text-slate-700">{item.context}</div>}
      {!played ? (
        <div className="card flex flex-col items-center gap-3 py-10">
          {state === "loading" && <p className="animate-pulse text-slate-600">Loading audio…</p>}
          {state === "playing" && <p className="text-lg">🔊 Listen carefully — you will hear this only once.</p>}
          {state === "error" && (
            <>
              <p className="text-sm text-red-700">{err}</p>
              <button className="btn-primary" onClick={play}>Try again</button>
            </>
          )}
        </div>
      ) : (
        <div className="card"><Questions qs={item.questions} answers={answers} onAnswer={onAnswer} /></div>
      )}
    </div>
  );
}

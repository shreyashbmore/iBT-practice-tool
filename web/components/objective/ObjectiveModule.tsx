"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import type { CWItem, ListeningItemPub, ObjectiveItem, PracticeSet, ReadingItemPub, SetAnswers } from "@/lib/api";
import { useCountdown } from "@/lib/useCountdown";
import Timer from "@/components/Timer";
import { CompleteWordsView, ListeningView, ReadingView } from "./ItemViews";

/** Runs one or more Reading/Listening sets as a single timed module, one item per page. */
export default function ObjectiveModule({ sets, timeLimit, label, onSubmit }: {
  sets: PracticeSet[];
  timeLimit: number;
  label?: string;
  onSubmit: (answers: SetAnswers, elapsed: number, timedOut: boolean) => Promise<void> | void;
}) {
  const pages = sets.flatMap((s) => (s.items as ObjectiveItem[]).map((item) => ({ set: s, item })));
  const [idx, setIdx] = useState(0);
  const [answers, setAnswers] = useState<SetAnswers>({});
  const [played, setPlayed] = useState<Record<string, boolean>>({});
  const [submitting, setSubmitting] = useState(false);
  const ref = useRef(answers);
  ref.current = answers;

  const submit = useCallback(async (timedOut: boolean) => {
    setSubmitting(true);
    timer.stop();
    try {
      await onSubmit(ref.current, timer.elapsed(), timedOut);
    } finally {
      setSubmitting(false);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [onSubmit]);
  const timer = useCountdown(timeLimit, () => submit(true));
  useEffect(() => {
    timer.start();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const { set, item } = pages[idx];
  const isListening = set.section === "listening";
  const setAns = (qid: string, v: number | string) =>
    setAnswers((a) => ({
      ...a, [set.id]: { ...(a[set.id] ?? {}), [item.id]: { ...(a[set.id]?.[item.id] ?? {}), [qid]: v } },
    }));
  const itemAns = answers[set.id]?.[item.id];
  const key = `${set.id}/${item.id}`;
  const canGoBack = !isListening && idx > 0;
  const waitingForAudio = isListening && !played[key];

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <span className="text-sm text-slate-600">
          {label && <b className="mr-2">{label}</b>}{set.title} · {idx + 1} / {pages.length}
        </span>
        <Timer remaining={timer.remaining} total={timeLimit} />
      </div>
      <p className="text-sm text-slate-600">{set.directions}</p>

      {item.task === "complete-the-words" && <CompleteWordsView item={item as CWItem} answers={itemAns} onAnswer={setAns} />}
      {(item.task === "read-daily-life" || item.task === "read-academic-passage") &&
        <ReadingView item={item as ReadingItemPub} answers={itemAns} onAnswer={setAns} />}
      {isListening && (
        <ListeningView key={key} setId={set.id} item={item as ListeningItemPub} answers={itemAns} onAnswer={setAns}
          played={!!played[key]} onPlayed={() => setPlayed((p) => ({ ...p, [key]: true }))} />
      )}

      <div className="flex justify-between">
        <button className="btn-ghost" onClick={() => setIdx(idx - 1)} disabled={!canGoBack || submitting}>← Back</button>
        {idx < pages.length - 1 ? (
          <button className="btn-primary" onClick={() => setIdx(idx + 1)} disabled={waitingForAudio}>Next →</button>
        ) : (
          <button className="btn-primary" onClick={() => submit(false)} disabled={submitting || waitingForAudio}>
            {submitting ? "Submitting…" : "Submit"}
          </button>
        )}
      </div>
    </div>
  );
}

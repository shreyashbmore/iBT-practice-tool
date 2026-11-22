"use client";

import { useCallback, useEffect, useRef, useState } from "react";

/** Countdown that calls onExpire once. `elapsed()` gives seconds since start (for time_spent_s). */
export function useCountdown(totalSeconds: number, onExpire: () => void) {
  const [remaining, setRemaining] = useState(totalSeconds);
  const [running, setRunning] = useState(false);
  const startedAt = useRef<number | null>(null);
  const fired = useRef(false);
  const cb = useRef(onExpire);
  cb.current = onExpire;

  const start = useCallback(() => {
    startedAt.current = performance.now();
    fired.current = false;
    setRemaining(totalSeconds);
    setRunning(true);
  }, [totalSeconds]);

  const stop = useCallback(() => setRunning(false), []);

  const elapsed = useCallback(
    () => (startedAt.current == null ? 0 : Math.round((performance.now() - startedAt.current) / 100) / 10),
    [],
  );

  useEffect(() => {
    if (!running) return;
    const id = setInterval(() => {
      const left = Math.max(0, totalSeconds - (performance.now() - (startedAt.current ?? 0)) / 1000);
      setRemaining(left);
      if (left <= 0 && !fired.current) {
        fired.current = true;
        setRunning(false);
        cb.current();
      }
    }, 250);
    return () => clearInterval(id);
  }, [running, totalSeconds]);

  return { remaining, running, start, stop, elapsed };
}

"use client";

import { useCallback, useEffect, useRef, useState } from "react";

export type RecorderState = "idle" | "recording" | "stopped";

function pickMime(): string {
  const prefs = ["audio/webm;codecs=opus", "audio/webm", "audio/mp4", "audio/ogg;codecs=opus"];
  if (typeof MediaRecorder === "undefined") return "";
  return prefs.find((m) => MediaRecorder.isTypeSupported(m)) ?? "";
}

/** Microphone recorder with a live input level (0–1) and elapsed seconds. */
export function useRecorder() {
  const [state, setState] = useState<RecorderState>("idle");
  const [blob, setBlob] = useState<Blob | null>(null);
  const [level, setLevel] = useState(0);
  const [elapsed, setElapsed] = useState(0);
  const [error, setError] = useState<string | null>(null);

  const rec = useRef<MediaRecorder | null>(null);
  const stream = useRef<MediaStream | null>(null);
  const raf = useRef<number | null>(null);
  const ctx = useRef<AudioContext | null>(null);
  const started = useRef(0);

  const cleanup = useCallback(() => {
    if (raf.current) cancelAnimationFrame(raf.current);
    stream.current?.getTracks().forEach((t) => t.stop());
    ctx.current?.close().catch(() => {});
    raf.current = null;
    stream.current = null;
    ctx.current = null;
    setLevel(0);
  }, []);

  useEffect(() => cleanup, [cleanup]);

  const start = useCallback(async () => {
    setError(null);
    setBlob(null);
    try {
      const s = await navigator.mediaDevices.getUserMedia({
        audio: { echoCancellation: true, noiseSuppression: true, channelCount: 1 },
      });
      stream.current = s;
      const mimeType = pickMime();
      const r = new MediaRecorder(s, mimeType ? { mimeType } : undefined);
      const chunks: BlobPart[] = [];
      r.ondataavailable = (e) => e.data.size && chunks.push(e.data);
      r.onstop = () => {
        setBlob(new Blob(chunks, { type: r.mimeType || "audio/webm" }));
        setState("stopped");
        cleanup();
      };
      rec.current = r;

      // input level meter
      const ac = new AudioContext();
      ctx.current = ac;
      const analyser = ac.createAnalyser();
      analyser.fftSize = 512;
      ac.createMediaStreamSource(s).connect(analyser);
      const buf = new Uint8Array(analyser.fftSize);
      const tick = () => {
        analyser.getByteTimeDomainData(buf);
        let peak = 0;
        for (const v of buf) peak = Math.max(peak, Math.abs(v - 128) / 128);
        setLevel(peak);
        setElapsed((performance.now() - started.current) / 1000);
        raf.current = requestAnimationFrame(tick);
      };
      started.current = performance.now();
      r.start(250);
      setState("recording");
      tick();
    } catch (e) {
      cleanup();
      setError(
        (e as Error).name === "NotAllowedError"
          ? "Microphone permission denied. Allow mic access in your browser settings."
          : `Could not start recording: ${(e as Error).message}`,
      );
    }
  }, [cleanup]);

  const stop = useCallback(() => {
    if (rec.current && rec.current.state !== "inactive") rec.current.stop();
  }, []);

  const reset = useCallback(() => {
    setBlob(null);
    setElapsed(0);
    setState("idle");
  }, []);

  return { state, blob, level, elapsed, error, start, stop, reset };
}

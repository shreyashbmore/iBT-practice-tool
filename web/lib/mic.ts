"use client";

/** Session-level microphone helpers: ask permission once, record many answers. */
export async function openMic(): Promise<MediaStream> {
  return navigator.mediaDevices.getUserMedia({
    audio: { echoCancellation: true, noiseSuppression: true, channelCount: 1 },
  });
}

function pickMime(): string {
  const prefs = ["audio/webm;codecs=opus", "audio/webm", "audio/mp4", "audio/ogg;codecs=opus"];
  return prefs.find((m) => typeof MediaRecorder !== "undefined" && MediaRecorder.isTypeSupported(m)) ?? "";
}

export function record(stream: MediaStream): { stop: () => void; done: Promise<Blob> } {
  const mimeType = pickMime();
  const rec = new MediaRecorder(stream, mimeType ? { mimeType } : undefined);
  const chunks: BlobPart[] = [];
  const done = new Promise<Blob>((resolve) => {
    rec.ondataavailable = (e) => e.data.size && chunks.push(e.data);
    rec.onstop = () => resolve(new Blob(chunks, { type: rec.mimeType || "audio/webm" }));
  });
  rec.start(250);
  return { stop: () => rec.state !== "inactive" && rec.stop(), done };
}

/** Short 880 Hz beep that marks the start of the response window. */
export async function beep(ms = 300): Promise<void> {
  const ctx = new AudioContext();
  const osc = ctx.createOscillator();
  const gain = ctx.createGain();
  osc.frequency.value = 880;
  gain.gain.value = 0.15;
  osc.connect(gain).connect(ctx.destination);
  osc.start();
  await new Promise((r) => setTimeout(r, ms));
  osc.stop();
  await ctx.close();
}

/** Play an audio blob and resolve when it ends (or fails — the test must not get stuck). */
export function playBlob(blob: Blob): Promise<void> {
  return new Promise((resolve) => {
    const url = URL.createObjectURL(blob);
    const a = new Audio(url);
    const finish = () => {
      URL.revokeObjectURL(url);
      resolve();
    };
    a.onended = finish;
    a.onerror = () => setTimeout(finish, 800);
    a.play().catch(() => setTimeout(finish, 800));
  });
}

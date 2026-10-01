"use client";

import { useEffect, useRef } from "react";

import type { VoiceState } from "@/lib/useInterview";

const COLORS: Record<VoiceState, [string, string]> = {
  loading: ["#52525b", "#27272a"],
  idle: ["#34d399", "#065f46"],
  listening: ["#f87171", "#7f1d1d"],
  transcribing: ["#38bdf8", "#0c4a6e"],
  thinking: ["#fbbf24", "#78350f"],
  speaking: ["#fb923c", "#7c2d12"],
  "rate-limited": ["#fde047", "#713f12"],
  done: ["#a1a1aa", "#3f3f46"],
  error: ["#ef4444", "#450a0a"],
};

const ANIMATION: Partial<Record<VoiceState, string>> = {
  thinking: "animate-orb-spin",
  speaking: "animate-orb-pulse",
  transcribing: "animate-orb-pulse",
  "rate-limited": "animate-orb-breathe",
  idle: "animate-orb-breathe",
  loading: "animate-orb-breathe",
};

interface Props {
  state: VoiceState;
  /** Returns the live mic level in [0, 1] while listening. */
  level: () => number;
}

/** The interviewer's "face": a glowing orb whose colour and motion track the state. */
export function InterviewerOrb({ state, level }: Props) {
  const coreRef = useRef<HTMLDivElement>(null);
  const [inner, outer] = COLORS[state];

  useEffect(() => {
    if (state !== "listening") {
      if (coreRef.current) coreRef.current.style.transform = "";
      return;
    }
    let frame = 0;
    let smoothed = 0;
    const tick = () => {
      smoothed = smoothed * 0.75 + level() * 0.25;
      if (coreRef.current) coreRef.current.style.transform = `scale(${1 + smoothed * 0.35})`;
      frame = requestAnimationFrame(tick);
    };
    frame = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(frame);
  }, [state, level]);

  return (
    <div
      className="relative flex h-40 w-40 items-center justify-center sm:h-52 sm:w-52"
      aria-hidden
    >
      <div
        className={`absolute inset-0 rounded-full opacity-40 blur-2xl transition-colors duration-500 ${ANIMATION[state] ?? ""}`}
        style={{ background: `radial-gradient(circle, ${inner} 0%, transparent 70%)` }}
      />
      <div
        ref={coreRef}
        className={`relative h-24 w-24 rounded-full shadow-2xl transition-[background] duration-500 sm:h-32 sm:w-32 ${ANIMATION[state] ?? ""}`}
        style={{
          background: `radial-gradient(circle at 35% 30%, ${inner}, ${outer} 75%)`,
          boxShadow: `0 0 60px ${inner}55`,
        }}
      />
    </div>
  );
}

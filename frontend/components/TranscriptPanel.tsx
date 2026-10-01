"use client";

import { useEffect, useRef } from "react";

import type { Turn } from "@/lib/types";

const KIND_LABEL: Partial<Record<Turn["kind"], string>> = {
  follow_up: "Follow-up",
  closing: "Wrap-up",
};

export function TranscriptPanel({ turns, liveCaption }: { turns: Turn[]; liveCaption?: string }) {
  const endRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: "smooth", block: "end" });
  }, [turns.length, liveCaption]);

  return (
    <section
      aria-label="Interview transcript"
      className="flex max-h-[45vh] min-h-48 flex-col gap-3 overflow-y-auto rounded-2xl border border-zinc-800 bg-zinc-950/60 p-4 sm:max-h-[60vh]"
    >
      {turns.length === 0 && (
        <p className="text-sm text-zinc-500">The transcript will appear here.</p>
      )}
      {turns.map((turn, index) => {
        const mine = turn.speaker === "candidate";
        return (
          <div key={index} className={`flex flex-col ${mine ? "items-end" : "items-start"}`}>
            <span className="mb-1 text-[11px] uppercase tracking-wide text-zinc-500">
              {mine
                ? "You"
                : `Interviewer${KIND_LABEL[turn.kind] ? ` · ${KIND_LABEL[turn.kind]}` : ""}`}
            </span>
            <p
              className={`max-w-[90%] whitespace-pre-wrap rounded-2xl px-4 py-2.5 text-sm leading-relaxed ${
                mine ? "bg-orange-500/15 text-orange-50" : "bg-zinc-800/80 text-zinc-100"
              }`}
            >
              {turn.text}
            </p>
          </div>
        );
      })}
      {liveCaption && (
        <div className="flex flex-col items-end">
          <span className="mb-1 text-[11px] uppercase tracking-wide text-zinc-500">You (live)</span>
          <p className="max-w-[90%] rounded-2xl border border-dashed border-orange-500/40 px-4 py-2.5 text-sm italic text-zinc-300">
            {liveCaption}
          </p>
        </div>
      )}
      <div ref={endRef} />
    </section>
  );
}

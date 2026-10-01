"use client";

import { useEffect } from "react";

import type { InterviewController } from "@/lib/useInterview";

function isTypingTarget(target: EventTarget | null): boolean {
  if (!(target instanceof HTMLElement)) return false;
  return target.isContentEditable || ["INPUT", "TEXTAREA", "SELECT"].includes(target.tagName);
}

/** Push-to-talk button (or hold Space), editable transcript and submit. */
export function AnswerComposer({ interview }: { interview: InterviewController }) {
  const { state, draft, setDraft, startListening, stopListening, submit } = interview;
  const listening = state === "listening";
  const canTalk = state === "idle" || state === "speaking" || listening;
  const canSubmit = state === "idle" && draft.trim().length > 0;

  useEffect(() => {
    const down = (event: KeyboardEvent) => {
      if (event.code !== "Space" || event.repeat || isTypingTarget(event.target)) return;
      event.preventDefault();
      void startListening();
    };
    const up = (event: KeyboardEvent) => {
      if (event.code !== "Space" || isTypingTarget(event.target)) return;
      event.preventDefault();
      void stopListening();
    };
    window.addEventListener("keydown", down);
    window.addEventListener("keyup", up);
    return () => {
      window.removeEventListener("keydown", down);
      window.removeEventListener("keyup", up);
    };
  }, [startListening, stopListening]);

  return (
    <div className="flex flex-col gap-3">
      <div className="flex flex-col items-center gap-2">
        <button
          type="button"
          disabled={!canTalk}
          aria-pressed={listening}
          aria-label={listening ? "Release to stop recording" : "Hold to talk"}
          onPointerDown={(event) => {
            event.currentTarget.setPointerCapture(event.pointerId);
            void startListening();
          }}
          onPointerUp={() => void stopListening()}
          onPointerCancel={() => void stopListening()}
          onKeyDown={(event) => {
            if (event.key === "Enter" && !event.repeat) void startListening();
          }}
          onKeyUp={(event) => {
            if (event.key === "Enter") void stopListening();
          }}
          className={`h-16 w-full max-w-xs touch-none select-none rounded-full text-base font-semibold transition focus:outline-none focus-visible:ring-2 focus-visible:ring-orange-400 focus-visible:ring-offset-2 focus-visible:ring-offset-zinc-950 disabled:cursor-not-allowed disabled:opacity-40 ${
            listening
              ? "scale-105 bg-red-500 text-white shadow-lg shadow-red-500/30"
              : "bg-orange-500 text-zinc-950 hover:bg-orange-400"
          }`}
        >
          {listening ? "Release to stop" : "Hold to talk"}
        </button>
        <p className="text-xs text-zinc-500">
          or hold{" "}
          <kbd className="rounded border border-zinc-700 px-1.5 py-0.5 font-mono">Space</kbd> · max
          2 minutes per recording
        </p>
      </div>

      <form
        className="flex flex-col gap-2"
        onSubmit={(event) => {
          event.preventDefault();
          void submit();
        }}
      >
        <label htmlFor="answer" className="text-xs font-medium text-zinc-400">
          Your answer (edit before sending)
        </label>
        <textarea
          id="answer"
          rows={4}
          value={draft}
          onChange={(event) => setDraft(event.target.value)}
          onKeyDown={(event) => {
            if (event.key === "Enter" && (event.metaKey || event.ctrlKey)) {
              event.preventDefault();
              void submit();
            }
          }}
          placeholder="Speak, or type your answer here…"
          className="w-full resize-y rounded-xl border border-zinc-800 bg-zinc-900 px-4 py-3 text-sm text-zinc-100 placeholder:text-zinc-600 focus:border-orange-500/60 focus:outline-none focus:ring-2 focus:ring-orange-500/30"
        />
        <div className="flex items-center justify-between gap-2">
          <span className="text-xs text-zinc-600">Ctrl/⌘ + Enter to send</span>
          <button
            type="submit"
            disabled={!canSubmit}
            className="rounded-lg bg-zinc-100 px-5 py-2 text-sm font-semibold text-zinc-900 transition hover:bg-white focus:outline-none focus-visible:ring-2 focus-visible:ring-orange-400 disabled:cursor-not-allowed disabled:opacity-40"
          >
            Send answer
          </button>
        </div>
      </form>
    </div>
  );
}

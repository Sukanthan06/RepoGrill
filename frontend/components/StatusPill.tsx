import type { VoiceState } from "@/lib/useInterview";

const LABELS: Record<VoiceState, string> = {
  loading: "Loading…",
  idle: "Your turn",
  listening: "Listening",
  transcribing: "Transcribing…",
  thinking: "Thinking…",
  speaking: "Speaking",
  "rate-limited": "Rate limited, retrying…",
  done: "Interview complete",
  error: "Error",
};

const STYLES: Record<VoiceState, string> = {
  loading: "bg-zinc-800 text-zinc-300",
  idle: "bg-emerald-500/15 text-emerald-300",
  listening: "bg-red-500/15 text-red-300",
  transcribing: "bg-sky-500/15 text-sky-300",
  thinking: "bg-amber-500/15 text-amber-300",
  speaking: "bg-orange-500/15 text-orange-300",
  "rate-limited": "bg-yellow-500/15 text-yellow-200",
  done: "bg-zinc-800 text-zinc-300",
  error: "bg-red-500/15 text-red-300",
};

export function StatusPill({ state, wait }: { state: VoiceState; wait?: number | null }) {
  const label =
    state === "rate-limited" && wait
      ? `Rate limited, retrying in ${Math.round(wait)}s…`
      : LABELS[state];
  return (
    <span
      role="status"
      aria-live="polite"
      className={`inline-flex items-center gap-2 rounded-full px-3 py-1 text-xs font-medium ${STYLES[state]}`}
    >
      <span className="h-1.5 w-1.5 rounded-full bg-current" aria-hidden />
      {label}
    </span>
  );
}

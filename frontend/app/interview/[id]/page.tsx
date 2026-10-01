"use client";

import Link from "next/link";
import { use } from "react";

import { AnswerComposer } from "@/components/AnswerComposer";
import { InterviewerOrb } from "@/components/InterviewerOrb";
import { StatusPill } from "@/components/StatusPill";
import { TranscriptPanel } from "@/components/TranscriptPanel";
import { useInterview } from "@/lib/useInterview";

export default function InterviewPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = use(params);
  const interview = useInterview(id);
  const { state, current, repo, error } = interview;

  if (state === "error") {
    return (
      <main className="mx-auto flex min-h-screen max-w-xl flex-col items-center justify-center gap-4 px-6 text-center">
        <h1 className="text-2xl font-semibold">Interview unavailable</h1>
        <p className="text-zinc-400">{error}</p>
        <Link href="/" className="rounded-lg bg-orange-500 px-4 py-2 font-semibold text-zinc-950">
          Start a new interview
        </Link>
      </main>
    );
  }

  return (
    <main className="mx-auto flex min-h-screen w-full max-w-6xl flex-col gap-6 px-4 py-6 sm:px-6">
      <header className="flex flex-wrap items-center justify-between gap-3">
        <div className="min-w-0">
          <Link href="/" className="text-sm font-semibold text-orange-400 hover:text-orange-300">
            RepoGrill
          </Link>
          <h1 className="truncate text-lg font-semibold">{repo?.full_name ?? "Loading…"}</h1>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <StatusPill state={state} wait={interview.rateLimitWait} />
          <label className="flex cursor-pointer items-center gap-2 rounded-lg border border-zinc-800 px-3 py-1.5 text-xs text-zinc-300">
            <input
              type="checkbox"
              checked={interview.voiceEnabled}
              onChange={(event) => interview.setVoice(event.target.checked)}
              className="accent-orange-500"
            />
            Interviewer voice
          </label>
          {state !== "done" && (
            <button
              type="button"
              onClick={() => void interview.endEarly()}
              className="rounded-lg border border-zinc-700 px-3 py-1.5 text-xs text-zinc-300 hover:border-red-500/60 hover:text-red-300 focus:outline-none focus-visible:ring-2 focus-visible:ring-orange-400"
            >
              End early
            </button>
          )}
        </div>
      </header>

      <div className="grid flex-1 gap-6 lg:grid-cols-[minmax(0,5fr)_minmax(0,6fr)]">
        <section
          className="flex flex-col items-center gap-5 text-center"
          aria-label="Current question"
        >
          <InterviewerOrb state={state} level={interview.level} />
          {current && (
            <p className="text-xs font-medium uppercase tracking-wider text-zinc-500">
              Question {current.question_number} of {current.total_questions} · {current.topic}
            </p>
          )}
          <p
            className="min-h-16 max-w-xl text-lg leading-relaxed text-zinc-100 sm:text-xl"
            aria-live="polite"
          >
            {current?.text ?? ""}
          </p>
          <div className="flex gap-2">
            {state === "speaking" ? (
              <button
                type="button"
                onClick={interview.skipSpeaking}
                className="rounded-lg border border-zinc-700 px-3 py-1.5 text-xs text-zinc-300 hover:bg-zinc-800 focus:outline-none focus-visible:ring-2 focus-visible:ring-orange-400"
              >
                Skip speaking
              </button>
            ) : (
              state === "idle" &&
              interview.voiceEnabled && (
                <button
                  type="button"
                  onClick={interview.replay}
                  className="rounded-lg border border-zinc-800 px-3 py-1.5 text-xs text-zinc-400 hover:bg-zinc-800 focus:outline-none focus-visible:ring-2 focus-visible:ring-orange-400"
                >
                  Replay question
                </button>
              )
            )}
          </div>
        </section>

        <section className="flex min-w-0 flex-col gap-4">
          <TranscriptPanel turns={interview.transcript} liveCaption={interview.liveCaption} />
          {error && (
            <p
              role="alert"
              className="rounded-lg border border-red-500/30 bg-red-500/10 px-3 py-2 text-sm text-red-200"
            >
              {error}
            </p>
          )}
          {state === "done" ? (
            <div className="flex flex-col items-center gap-3 rounded-2xl border border-zinc-800 bg-zinc-900/60 p-6 text-center">
              <p className="text-zinc-300">That&apos;s a wrap. Let&apos;s see how you did.</p>
              <Link
                href={`/report/${id}`}
                className="rounded-lg bg-orange-500 px-5 py-2.5 font-semibold text-zinc-950 hover:bg-orange-400 focus:outline-none focus-visible:ring-2 focus-visible:ring-orange-300"
              >
                See your scorecard
              </Link>
            </div>
          ) : (
            <AnswerComposer interview={interview} />
          )}
        </section>
      </div>
    </main>
  );
}

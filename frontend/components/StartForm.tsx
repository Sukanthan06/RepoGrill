"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";

import { ApiError, createSession, getDossier, ingestRepo, withRateLimitRetry } from "@/lib/api";
import { parseRepo } from "@/lib/repoUrl";
import type { Difficulty, InterviewLength } from "@/lib/types";

import { Segmented } from "./Segmented";

type Step = "idle" | "reading" | "dossier" | "starting";

const STEPS: { key: Exclude<Step, "idle">; label: string }[] = [
  { key: "reading", label: "Reading the repository" },
  { key: "dossier", label: "Studying the code and drafting questions" },
  { key: "starting", label: "Starting the interview" },
];

export const EXAMPLE_REPO = "https://github.com/fastapi/full-stack-fastapi-template";

/** Paste a repo, pick length and difficulty, and kick off an interview. */
export function StartForm() {
  const router = useRouter();
  const [repoUrl, setRepoUrl] = useState("");
  const [touched, setTouched] = useState(false);
  const [length, setLength] = useState<InterviewLength>(8);
  const [difficulty, setDifficulty] = useState<Difficulty>("medium");
  const [step, setStep] = useState<Step>("idle");
  const [notice, setNotice] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const parsed = parseRepo(repoUrl);
  const invalid = touched && repoUrl.trim() !== "" && parsed === null;
  const busy = step !== "idle";

  const onRateLimited = (wait: number) =>
    setNotice(`Rate limited by the AI provider, retrying in ${Math.round(wait)}s…`);

  async function start() {
    setTouched(true);
    if (!parsed) return;
    setError(null);
    setNotice(null);
    try {
      setStep("reading");
      const repo = await withRateLimitRetry(() => ingestRepo(repoUrl.trim()), onRateLimited, 1);
      setStep("dossier");
      setNotice(null);
      await withRateLimitRetry(() => getDossier(repo.repo_id), onRateLimited);
      setStep("starting");
      setNotice(null);
      const session = await withRateLimitRetry(
        () => createSession(repo.repo_id, length, difficulty),
        onRateLimited,
      );
      router.push(`/interview/${session.session_id}`);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Something went wrong. Try again.");
      setStep("idle");
      setNotice(null);
    }
  }

  return (
    <form
      noValidate
      className="flex flex-col gap-5 rounded-3xl border border-zinc-800 bg-zinc-900/50 p-5 shadow-2xl shadow-black/40 sm:p-7"
      onSubmit={(event) => {
        event.preventDefault();
        void start();
      }}
    >
      <div className="flex flex-col gap-2">
        <div className="flex items-baseline justify-between gap-2">
          <label htmlFor="repo-url" className="text-sm font-medium text-zinc-300">
            Public GitHub repository
          </label>
          <button
            type="button"
            disabled={busy}
            onClick={() => {
              setRepoUrl(EXAMPLE_REPO);
              setTouched(false);
            }}
            className="rounded text-xs text-orange-300 underline-offset-2 hover:underline focus:outline-none focus-visible:ring-2 focus-visible:ring-orange-400 disabled:opacity-50"
          >
            Try an example repo
          </button>
        </div>
        <input
          id="repo-url"
          type="url"
          inputMode="url"
          autoComplete="off"
          spellCheck={false}
          disabled={busy}
          value={repoUrl}
          onChange={(event) => setRepoUrl(event.target.value)}
          onBlur={() => setTouched(true)}
          aria-invalid={invalid}
          aria-describedby="repo-help"
          placeholder="https://github.com/you/your-project"
          className={`rounded-xl border bg-zinc-950 px-4 py-3 font-mono text-sm text-zinc-100 placeholder:text-zinc-600 focus:outline-none focus:ring-2 ${
            invalid
              ? "border-red-500/60 focus:ring-red-500/30"
              : "border-zinc-800 focus:border-orange-500/60 focus:ring-orange-500/30"
          }`}
        />
        <p id="repo-help" className={`text-xs ${invalid ? "text-red-300" : "text-zinc-500"}`}>
          {invalid
            ? "Use a URL like https://github.com/owner/repo"
            : parsed
              ? `Ready to read ${parsed}`
              : "Any public repo works: your side project, hackathon entry or portfolio piece."}
        </p>
      </div>

      <div className="grid gap-4 sm:grid-cols-2">
        <Segmented
          label="Questions"
          value={length}
          onChange={setLength}
          disabled={busy}
          options={[
            { value: 5, label: "5", hint: "~10 min" },
            { value: 8, label: "8", hint: "~15 min" },
            { value: 12, label: "12", hint: "~25 min" },
          ]}
        />
        <Segmented
          label="Difficulty"
          value={difficulty}
          onChange={setDifficulty}
          disabled={busy}
          options={[
            { value: "easy", label: "Easy" },
            { value: "medium", label: "Medium" },
            { value: "hard", label: "Hard" },
          ]}
        />
      </div>

      <button
        type="submit"
        disabled={busy}
        className="rounded-xl bg-orange-500 px-5 py-3.5 text-base font-semibold text-zinc-950 shadow-lg shadow-orange-500/20 transition hover:bg-orange-400 focus:outline-none focus-visible:ring-2 focus-visible:ring-orange-300 focus-visible:ring-offset-2 focus-visible:ring-offset-zinc-950 disabled:cursor-wait disabled:opacity-70"
      >
        {busy ? "Preparing your interview…" : "Start the interview"}
      </button>

      {busy && (
        <ol className="flex flex-col gap-1.5 text-sm" aria-live="polite">
          {STEPS.map((item, index) => {
            const current = STEPS.findIndex((s) => s.key === step);
            const state = index < current ? "done" : index === current ? "active" : "todo";
            return (
              <li
                key={item.key}
                className={`flex items-center gap-2 ${state === "todo" ? "text-zinc-600" : "text-zinc-300"}`}
              >
                <span
                  aria-hidden
                  className={`h-2 w-2 rounded-full ${
                    state === "done"
                      ? "bg-emerald-400"
                      : state === "active"
                        ? "animate-pulse bg-orange-400"
                        : "bg-zinc-700"
                  }`}
                />
                {item.label}
                {state === "done" && <span className="sr-only">(done)</span>}
              </li>
            );
          })}
        </ol>
      )}
      {notice && <p className="text-sm text-yellow-200">{notice}</p>}
      {error && (
        <p
          role="alert"
          className="rounded-lg border border-red-500/30 bg-red-500/10 px-3 py-2 text-sm text-red-200"
        >
          {error}
        </p>
      )}
    </form>
  );
}

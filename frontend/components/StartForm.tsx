"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";

import { ApiError, createSession, getDossier, ingestRepo, withRateLimitRetry } from "@/lib/api";
import type { Difficulty, InterviewLength } from "@/lib/types";

type Step = "idle" | "reading" | "dossier" | "starting";

const STEP_LABEL: Record<Step, string> = {
  idle: "",
  reading: "Reading the repository…",
  dossier: "Studying your code and drafting questions…",
  starting: "Starting the interview…",
};

/** Paste a repo, pick length and difficulty, and kick off an interview. */
export function StartForm() {
  const router = useRouter();
  const [repoUrl, setRepoUrl] = useState("");
  const [length, setLength] = useState<InterviewLength>(8);
  const [difficulty, setDifficulty] = useState<Difficulty>("medium");
  const [step, setStep] = useState<Step>("idle");
  const [notice, setNotice] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const onRateLimited = (wait: number) =>
    setNotice(`Rate limited, retrying in ${Math.round(wait)}s…`);

  async function start() {
    setError(null);
    setNotice(null);
    try {
      setStep("reading");
      const repo = await withRateLimitRetry(() => ingestRepo(repoUrl.trim()), onRateLimited, 1);
      setStep("dossier");
      await withRateLimitRetry(() => getDossier(repo.repo_id), onRateLimited);
      setStep("starting");
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

  const busy = step !== "idle";
  return (
    <form
      className="flex flex-col gap-4"
      onSubmit={(event) => {
        event.preventDefault();
        void start();
      }}
    >
      <label htmlFor="repo-url" className="text-sm font-medium text-zinc-300">
        Public GitHub repository
      </label>
      <input
        id="repo-url"
        type="text"
        required
        value={repoUrl}
        onChange={(event) => setRepoUrl(event.target.value)}
        placeholder="https://github.com/you/your-project"
        className="rounded-xl border border-zinc-800 bg-zinc-900 px-4 py-3 text-zinc-100 placeholder:text-zinc-600 focus:border-orange-500/60 focus:outline-none focus:ring-2 focus:ring-orange-500/30"
      />
      <div className="flex flex-wrap gap-4">
        <label className="flex items-center gap-2 text-sm text-zinc-400">
          Questions
          <select
            value={length}
            onChange={(event) => setLength(Number(event.target.value) as InterviewLength)}
            className="rounded-lg border border-zinc-800 bg-zinc-900 px-2 py-1.5 text-zinc-100"
          >
            <option value={5}>5</option>
            <option value={8}>8</option>
            <option value={12}>12</option>
          </select>
        </label>
        <label className="flex items-center gap-2 text-sm text-zinc-400">
          Difficulty
          <select
            value={difficulty}
            onChange={(event) => setDifficulty(event.target.value as Difficulty)}
            className="rounded-lg border border-zinc-800 bg-zinc-900 px-2 py-1.5 text-zinc-100"
          >
            <option value="easy">Easy</option>
            <option value="medium">Medium</option>
            <option value="hard">Hard</option>
          </select>
        </label>
      </div>
      <button
        type="submit"
        disabled={busy || !repoUrl.trim()}
        className="rounded-xl bg-orange-500 px-5 py-3 font-semibold text-zinc-950 hover:bg-orange-400 disabled:opacity-50"
      >
        {busy ? STEP_LABEL[step] : "Start interview"}
      </button>
      {notice && <p className="text-sm text-yellow-200">{notice}</p>}
      {error && (
        <p role="alert" className="text-sm text-red-300">
          {error}
        </p>
      )}
    </form>
  );
}

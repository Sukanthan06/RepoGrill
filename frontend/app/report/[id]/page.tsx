"use client";

import Link from "next/link";
import { use } from "react";

import { BluffList, ClaimItem } from "@/components/report/BluffList";
import { PrepList } from "@/components/report/PrepList";
import { QuestionCard } from "@/components/report/QuestionCard";
import { useReport } from "@/lib/useReport";

export default function ReportPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = use(params);
  const { report, error, stageText, rateLimitWait } = useReport(id);

  if (error) {
    return (
      <main className="mx-auto flex min-h-screen max-w-xl flex-col items-center justify-center gap-4 px-6 text-center">
        <h1 className="text-2xl font-semibold">Scorecard unavailable</h1>
        <p className="text-zinc-400">{error}</p>
        <Link href="/" className="rounded-lg bg-orange-500 px-4 py-2 font-semibold text-zinc-950">
          Start a new interview
        </Link>
      </main>
    );
  }

  if (!report) {
    return (
      <main className="mx-auto flex min-h-screen max-w-xl flex-col items-center justify-center gap-3 px-6 text-center">
        <div className="h-10 w-10 animate-spin rounded-full border-2 border-zinc-700 border-t-orange-400" />
        <p className="text-zinc-300" aria-live="polite">
          {rateLimitWait ? `Rate limited, retrying in ${Math.round(rateLimitWait)}s…` : stageText}
        </p>
      </main>
    );
  }

  const verified = report.claims.filter((claim) => claim.status === "verified");
  return (
    <main className="mx-auto flex w-full max-w-4xl flex-col gap-8 px-4 py-8 sm:px-6">
      <header className="flex flex-col gap-2">
        <Link href="/" className="text-sm font-semibold text-orange-400">
          RepoGrill
        </Link>
        <h1 className="text-2xl font-bold">Scorecard: {report.repo_meta.full_name}</h1>
        <p className="text-5xl font-bold text-orange-300">
          {report.overall_score}
          <span className="text-xl text-zinc-500">/100</span>
        </p>
        <p className="text-zinc-300">{report.summary}</p>
      </header>

      <BluffList bluffs={report.bluffs} repo={report.repo_meta} />

      {report.strengths.length > 0 && (
        <section>
          <h2 className="mb-3 text-lg font-semibold">Strengths</h2>
          <ul className="list-disc space-y-1 pl-5 text-zinc-300">
            {report.strengths.map((strength, index) => (
              <li key={index}>{strength}</li>
            ))}
          </ul>
        </section>
      )}

      <section className="flex flex-col gap-3">
        <h2 className="text-lg font-semibold">Answers</h2>
        {report.questions.map((question) => (
          <QuestionCard key={question.question_number} question={question} />
        ))}
      </section>

      {verified.length > 0 && (
        <section className="flex flex-col gap-3">
          <h2 className="text-lg font-semibold">Claims backed by your code ({verified.length})</h2>
          <ul className="flex flex-col gap-3">
            {verified.map((claim, index) => (
              <ClaimItem key={index} claim={claim} repo={report.repo_meta} />
            ))}
          </ul>
        </section>
      )}

      <section className="flex flex-col gap-3">
        <h2 className="text-lg font-semibold">Top 5 questions to prep</h2>
        <PrepList items={report.prep} repo={report.repo_meta} />
      </section>
    </main>
  );
}

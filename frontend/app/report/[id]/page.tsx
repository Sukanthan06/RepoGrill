"use client";

import Link from "next/link";
import { use } from "react";

import { BluffList, ClaimItem } from "@/components/report/BluffList";
import { CopyMarkdownButton } from "@/components/report/CopyMarkdownButton";
import { PrepList } from "@/components/report/PrepList";
import { QuestionCard } from "@/components/report/QuestionCard";
import { ScoreRing } from "@/components/report/ScoreRing";
import { useReport } from "@/lib/useReport";

function CenteredMessage({ children }: { children: React.ReactNode }) {
  return (
    <main className="mx-auto flex min-h-screen max-w-xl flex-col items-center justify-center gap-4 px-6 text-center">
      {children}
    </main>
  );
}

export default function ReportPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = use(params);
  const { report, error, stageText, rateLimitWait } = useReport(id);

  if (error) {
    return (
      <CenteredMessage>
        <h1 className="text-2xl font-semibold">Scorecard unavailable</h1>
        <p className="text-zinc-400">{error}</p>
        <Link
          href="/"
          className="rounded-lg bg-orange-500 px-4 py-2 font-semibold text-zinc-950 hover:bg-orange-400"
        >
          Start a new interview
        </Link>
      </CenteredMessage>
    );
  }

  if (!report) {
    return (
      <CenteredMessage>
        <div
          className="h-12 w-12 animate-spin rounded-full border-2 border-zinc-800 border-t-orange-400"
          aria-hidden
        />
        <h1 className="text-lg font-semibold">Building your scorecard</h1>
        <p className="text-zinc-400" role="status" aria-live="polite">
          {rateLimitWait ? `Rate limited, retrying in ${Math.round(rateLimitWait)}s…` : stageText}
        </p>
      </CenteredMessage>
    );
  }

  const verified = report.claims.filter((claim) => claim.status === "verified");
  return (
    <main className="mx-auto flex w-full max-w-4xl flex-col gap-10 px-4 py-8 sm:px-6 sm:py-12">
      <nav className="flex items-center justify-between gap-3">
        <Link href="/" className="text-sm font-semibold text-orange-400 hover:text-orange-300">
          RepoGrill
        </Link>
        <div className="flex gap-2">
          <CopyMarkdownButton report={report} />
          <Link
            href="/"
            className="rounded-lg bg-orange-500 px-3 py-1.5 text-sm font-semibold text-zinc-950 hover:bg-orange-400 focus:outline-none focus-visible:ring-2 focus-visible:ring-orange-300"
          >
            New interview
          </Link>
        </div>
      </nav>

      <header className="flex flex-col items-center gap-6 sm:flex-row sm:items-center">
        <ScoreRing score={report.overall_score} />
        <div className="flex flex-col gap-2 text-center sm:text-left">
          <p className="text-xs uppercase tracking-wider text-zinc-500">
            Scorecard
            {report.ended_early ? " · ended early" : ""}
          </p>
          <h1 className="text-2xl font-bold">
            <a
              href={report.repo_meta.html_url}
              target="_blank"
              rel="noreferrer"
              className="hover:underline"
            >
              {report.repo_meta.full_name}
            </a>
          </h1>
          <p className="leading-relaxed text-zinc-300">{report.summary}</p>
        </div>
      </header>

      <BluffList bluffs={report.bluffs} repo={report.repo_meta} />

      {report.strengths.length > 0 && (
        <section aria-labelledby="strengths-heading">
          <h2 id="strengths-heading" className="mb-3 text-lg font-semibold">
            Strengths
          </h2>
          <ul className="grid grid-cols-1 gap-2 sm:grid-cols-2">
            {report.strengths.map((strength, index) => (
              <li
                key={index}
                className="rounded-xl border border-emerald-500/20 bg-emerald-500/5 px-4 py-3 text-sm text-emerald-100"
              >
                {strength}
              </li>
            ))}
          </ul>
        </section>
      )}

      <section aria-labelledby="answers-heading" className="flex flex-col gap-3">
        <h2 id="answers-heading" className="text-lg font-semibold">
          Your answers
        </h2>
        {report.questions.map((question) => (
          <QuestionCard
            key={question.question_number}
            question={question}
            claims={report.claims.filter((c) => c.question_number === question.question_number)}
          />
        ))}
      </section>

      {verified.length > 0 && (
        <section aria-labelledby="verified-heading" className="flex flex-col gap-3">
          <h2 id="verified-heading" className="text-lg font-semibold">
            Claims backed by your code ({verified.length})
          </h2>
          <ul className="flex flex-col gap-3">
            {verified.map((claim, index) => (
              <ClaimItem key={index} claim={claim} repo={report.repo_meta} />
            ))}
          </ul>
        </section>
      )}

      <section aria-labelledby="prep-heading" className="flex flex-col gap-3">
        <h2 id="prep-heading" className="text-lg font-semibold">
          Top {report.prep.length} questions to prep
        </h2>
        <PrepList items={report.prep} repo={report.repo_meta} />
      </section>
    </main>
  );
}

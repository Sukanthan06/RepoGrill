import type { ClaimCheck, QuestionReport, ScoreLine } from "@/lib/types";

const STATUS_DOT: Record<ClaimCheck["status"], string> = {
  verified: "bg-emerald-400",
  unverified: "bg-amber-400",
  contradicted: "bg-red-500",
};

function scoreColor(score: number): string {
  if (score >= 75) return "text-emerald-300";
  if (score >= 50) return "text-amber-300";
  return "text-red-300";
}

function Dimension({ label, line }: { label: string; line: ScoreLine }) {
  return (
    <div className="rounded-lg bg-zinc-950/60 p-3">
      <div className="flex items-center justify-between text-xs uppercase tracking-wide text-zinc-500">
        <span>{label}</span>
        <span className="font-mono text-sm text-zinc-200">{line.score}/5</span>
      </div>
      <div className="mt-1.5 flex gap-0.5" aria-hidden>
        {[1, 2, 3, 4, 5].map((n) => (
          <span
            key={n}
            className={`h-1 flex-1 rounded-full ${n <= line.score ? "bg-orange-400" : "bg-zinc-800"}`}
          />
        ))}
      </div>
      <p className="mt-2 text-sm text-zinc-300">{line.feedback}</p>
    </div>
  );
}

export function QuestionCard({
  question,
  claims,
}: {
  question: QuestionReport;
  claims: ClaimCheck[];
}) {
  return (
    <details className="group rounded-2xl border border-zinc-800 bg-zinc-900/60 open:border-zinc-700">
      <summary className="flex cursor-pointer list-none items-start justify-between gap-3 rounded-2xl p-5 focus:outline-none focus-visible:ring-2 focus-visible:ring-orange-400 [&::-webkit-details-marker]:hidden">
        <div className="min-w-0">
          <p className="text-xs uppercase tracking-wide text-zinc-500">
            Q{question.question_number} · {question.topic}
          </p>
          <h3 className="mt-1 font-medium text-zinc-100">{question.question}</h3>
          {claims.length > 0 && (
            <p className="mt-2 flex items-center gap-1.5 text-xs text-zinc-500">
              {claims.map((claim, index) => (
                <span
                  key={index}
                  className={`h-2 w-2 rounded-full ${STATUS_DOT[claim.status]}`}
                  title={`${claim.status}: ${claim.claim}`}
                />
              ))}
              <span className="ml-1">
                {claims.length} claim{claims.length === 1 ? "" : "s"} checked
              </span>
            </p>
          )}
        </div>
        <div className="flex shrink-0 items-center gap-3">
          <span className={`font-mono text-2xl font-semibold ${scoreColor(question.score)}`}>
            {question.score}
          </span>
          <svg
            viewBox="0 0 20 20"
            className="h-4 w-4 text-zinc-500 transition group-open:rotate-180"
            aria-hidden
          >
            <path d="M5 8l5 5 5-5" fill="none" stroke="currentColor" strokeWidth="2" />
          </svg>
        </div>
      </summary>
      <div className="flex flex-col gap-4 px-5 pb-5">
        <div className="grid grid-cols-1 gap-2 sm:grid-cols-3">
          <Dimension label="Depth" line={question.depth} />
          <Dimension label="Accuracy" line={question.accuracy} />
          <Dimension label="Clarity" line={question.clarity} />
        </div>
        <div className="flex flex-col gap-2 border-t border-zinc-800 pt-4">
          <h4 className="text-xs font-semibold uppercase tracking-wide text-zinc-500">
            Transcript
          </h4>
          {question.exchanges.map((turn, index) => (
            <p key={index} className="text-sm leading-relaxed">
              <span
                className={`font-semibold ${turn.speaker === "candidate" ? "text-orange-300" : "text-zinc-400"}`}
              >
                {turn.speaker === "candidate" ? "You" : "Interviewer"}:
              </span>{" "}
              <span className="text-zinc-300">{turn.text}</span>
            </p>
          ))}
        </div>
      </div>
    </details>
  );
}

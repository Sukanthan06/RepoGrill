import type { QuestionReport, ScoreLine } from "@/lib/types";

function Dimension({ label, line }: { label: string; line: ScoreLine }) {
  return (
    <div className="rounded-lg bg-zinc-950/60 p-3">
      <div className="flex items-center justify-between text-xs uppercase tracking-wide text-zinc-500">
        <span>{label}</span>
        <span className="font-mono text-sm text-zinc-200">{line.score}/5</span>
      </div>
      <p className="mt-1 text-sm text-zinc-300">{line.feedback}</p>
    </div>
  );
}

export function QuestionCard({ question }: { question: QuestionReport }) {
  return (
    <article className="rounded-2xl border border-zinc-800 bg-zinc-900/60 p-5">
      <header className="flex items-start justify-between gap-3">
        <div>
          <p className="text-xs uppercase tracking-wide text-zinc-500">
            Q{question.question_number} · {question.topic}
          </p>
          <h3 className="mt-1 font-medium text-zinc-100">{question.question}</h3>
        </div>
        <span className="shrink-0 font-mono text-lg font-semibold text-orange-300">
          {question.score}
        </span>
      </header>
      <div className="mt-4 grid gap-2 sm:grid-cols-3">
        <Dimension label="Depth" line={question.depth} />
        <Dimension label="Accuracy" line={question.accuracy} />
        <Dimension label="Clarity" line={question.clarity} />
      </div>
    </article>
  );
}

import { StartForm } from "@/components/StartForm";

const STEPS = [
  {
    title: "It reads your code",
    body: "Ranks the files that matter, maps the stack and architecture, and drafts questions only your project could raise.",
  },
  {
    title: "It interviews you out loud",
    body: "A sharp senior engineer asks one question at a time and pushes back when your answer gets hand-wavy.",
  },
  {
    title: "It catches your bluffs",
    body: "Every technical claim you make is checked against the repo. Say Redis when there's no Redis and it will show up in red.",
  },
];

export default function Home() {
  return (
    <main className="relative mx-auto flex min-h-screen w-full max-w-5xl flex-col gap-14 px-4 py-10 sm:px-6 sm:py-16">
      <div
        aria-hidden
        className="pointer-events-none absolute inset-x-0 top-0 -z-10 h-96 bg-[radial-gradient(ellipse_at_top,rgba(249,115,22,0.18),transparent_65%)]"
      />
      <header className="flex items-center gap-2 text-sm font-semibold text-orange-400">
        <span
          aria-hidden
          className="h-3 w-3 rounded-full bg-gradient-to-br from-orange-300 to-orange-600"
        />
        RepoGrill
      </header>

      <section className="grid items-start gap-10 lg:grid-cols-[1.05fr_1fr]">
        <div className="flex flex-col gap-5 lg:pt-6">
          <h1 className="text-4xl font-bold leading-tight tracking-tight sm:text-5xl">
            Get grilled on <span className="text-orange-400">your own code</span>.
          </h1>
          <p className="max-w-xl text-lg leading-relaxed text-zinc-400">
            Paste a GitHub repo. A voice interviewer reads it, asks the questions a senior engineer
            would, and hands you a scorecard that flags every claim your code doesn&apos;t back up.
          </p>
          <ul className="flex flex-wrap gap-2 text-xs text-zinc-400">
            {[
              "Voice or text answers",
              "Adaptive follow-ups",
              "Bluff detection with file evidence",
            ].map((item) => (
              <li key={item} className="rounded-full border border-zinc-800 px-3 py-1">
                {item}
              </li>
            ))}
          </ul>
        </div>
        <StartForm />
      </section>

      <section aria-labelledby="how-heading" className="flex flex-col gap-5">
        <h2
          id="how-heading"
          className="text-sm font-semibold uppercase tracking-wider text-zinc-500"
        >
          How it works
        </h2>
        <ol className="grid gap-4 sm:grid-cols-3">
          {STEPS.map((step, index) => (
            <li key={step.title} className="rounded-2xl border border-zinc-800 bg-zinc-900/40 p-5">
              <span className="font-mono text-sm text-orange-400">0{index + 1}</span>
              <h3 className="mt-2 font-semibold text-zinc-100">{step.title}</h3>
              <p className="mt-1 text-sm leading-relaxed text-zinc-400">{step.body}</p>
            </li>
          ))}
        </ol>
      </section>

      <footer className="text-xs text-zinc-600">
        Works best in Chrome. Your audio is only used to transcribe your answers.
      </footer>
    </main>
  );
}

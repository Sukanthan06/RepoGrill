import type { ClaimCheck, RepoMeta } from "@/lib/types";

import { EvidenceLink } from "./EvidenceLink";

const BADGE: Record<ClaimCheck["status"], string> = {
  contradicted: "bg-red-500/20 text-red-200 ring-red-500/40",
  unverified: "bg-amber-500/15 text-amber-200 ring-amber-500/30",
  verified: "bg-emerald-500/15 text-emerald-200 ring-emerald-500/30",
};

export function ClaimItem({ claim, repo }: { claim: ClaimCheck; repo: RepoMeta }) {
  return (
    <li className="flex flex-col gap-2 rounded-xl border border-zinc-800 bg-zinc-900/60 p-4">
      <div className="flex flex-wrap items-start justify-between gap-2">
        <p className="font-medium text-zinc-100">&ldquo;{claim.claim}&rdquo;</p>
        <span
          className={`shrink-0 rounded-full px-2.5 py-0.5 text-xs font-semibold capitalize ring-1 ${BADGE[claim.status]}`}
        >
          {claim.status}
        </span>
      </div>
      <p className="text-sm text-zinc-400">
        Q{claim.question_number} · {claim.explanation}
      </p>
      {claim.evidence.length > 0 && (
        <div className="grid grid-cols-1 gap-2 sm:grid-cols-2">
          {claim.evidence.map((evidence) => (
            <EvidenceLink
              key={`${evidence.file}:${evidence.line}`}
              repo={repo}
              evidence={evidence}
            />
          ))}
        </div>
      )}
    </li>
  );
}

export function BluffList({ bluffs, repo }: { bluffs: ClaimCheck[]; repo: RepoMeta }) {
  return (
    <section
      aria-labelledby="bluffs-heading"
      className="rounded-2xl border border-red-500/40 bg-red-950/30 p-5"
    >
      <h2 id="bluffs-heading" className="text-lg font-semibold text-red-200">
        Bluffs caught ({bluffs.length})
      </h2>
      <p className="mt-1 text-sm text-red-200/70">
        Claims the code contradicts, or named technologies with no trace in the repo.
      </p>
      {bluffs.length === 0 ? (
        <p className="mt-4 text-sm text-zinc-300">None. Everything you claimed held up.</p>
      ) : (
        <ul className="mt-4 flex flex-col gap-3">
          {bluffs.map((claim, index) => (
            <ClaimItem key={index} claim={claim} repo={repo} />
          ))}
        </ul>
      )}
    </section>
  );
}

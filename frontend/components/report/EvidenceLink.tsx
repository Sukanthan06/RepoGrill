import { blobUrl } from "@/lib/github";
import type { Evidence, RepoMeta } from "@/lib/types";

export function EvidenceLink({ repo, evidence }: { repo: RepoMeta; evidence: Evidence }) {
  const label = evidence.line ? `${evidence.file}:${evidence.line}` : evidence.file;
  return (
    <a
      href={blobUrl(repo, evidence.file, evidence.line)}
      target="_blank"
      rel="noreferrer"
      className="group block rounded-lg border border-zinc-800 bg-zinc-950/70 px-3 py-2 hover:border-zinc-600 focus:outline-none focus-visible:ring-2 focus-visible:ring-orange-400"
    >
      <span className="font-mono text-xs text-sky-300 group-hover:underline">{label}</span>
      {evidence.snippet && (
        <code className="mt-1 block truncate font-mono text-xs text-zinc-400">
          {evidence.snippet}
        </code>
      )}
    </a>
  );
}

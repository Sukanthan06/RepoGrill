import type { RepoMeta } from "./types";

/** Permalink to a file (and optional line) at the exact commit that was analysed. */
export function blobUrl(repo: RepoMeta, path: string, line?: number | null): string {
  const encoded = path.split("/").map(encodeURIComponent).join("/");
  return `${repo.html_url}/blob/${repo.sha}/${encoded}${line ? `#L${line}` : ""}`;
}

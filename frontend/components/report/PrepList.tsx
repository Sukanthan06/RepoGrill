import { blobUrl } from "@/lib/github";
import type { PrepItem, RepoMeta } from "@/lib/types";

export function PrepList({ items, repo }: { items: PrepItem[]; repo: RepoMeta }) {
  return (
    <ol className="flex flex-col gap-3">
      {items.map((item, index) => (
        <li key={index} className="rounded-2xl border border-zinc-800 bg-zinc-900/60 p-5">
          <p className="font-medium text-zinc-100">
            <span className="mr-2 font-mono text-orange-300">{index + 1}.</span>
            {item.question}
          </p>
          {item.why && <p className="mt-1 text-sm text-zinc-400">{item.why}</p>}
          <ul className="mt-3 list-disc space-y-1 pl-5 text-sm text-zinc-300">
            {item.talking_points.map((point, i) => (
              <li key={i}>{point}</li>
            ))}
          </ul>
          {item.files.length > 0 && (
            <div className="mt-3 flex flex-wrap gap-2">
              {item.files.map((file) => (
                <a
                  key={file}
                  href={blobUrl(repo, file)}
                  target="_blank"
                  rel="noreferrer"
                  className="rounded-md bg-zinc-800 px-2 py-1 font-mono text-xs text-sky-300 hover:bg-zinc-700"
                >
                  {file}
                </a>
              ))}
            </div>
          )}
        </li>
      ))}
    </ol>
  );
}

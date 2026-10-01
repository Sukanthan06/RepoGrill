"use client";

import { useState } from "react";

import { reportToMarkdown } from "@/lib/reportMarkdown";
import type { Report } from "@/lib/types";

export function CopyMarkdownButton({ report }: { report: Report }) {
  const [state, setState] = useState<"idle" | "copied" | "failed">("idle");

  async function copy() {
    try {
      await navigator.clipboard.writeText(reportToMarkdown(report));
      setState("copied");
    } catch {
      setState("failed");
    }
    setTimeout(() => setState("idle"), 2000);
  }

  return (
    <button
      type="button"
      onClick={() => void copy()}
      className="rounded-lg border border-zinc-700 px-3 py-1.5 text-sm text-zinc-200 hover:bg-zinc-800 focus:outline-none focus-visible:ring-2 focus-visible:ring-orange-400"
    >
      <span aria-live="polite">
        {state === "copied" ? "Copied!" : state === "failed" ? "Copy failed" : "Copy as Markdown"}
      </span>
    </button>
  );
}

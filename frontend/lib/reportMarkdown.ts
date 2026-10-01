import { blobUrl } from "./github";
import type { ClaimCheck, Report } from "./types";

function claimLine(report: Report, claim: ClaimCheck): string {
  const evidence = claim.evidence
    .map(
      (e) =>
        `[${e.line ? `${e.file}:${e.line}` : e.file}](${blobUrl(report.repo_meta, e.file, e.line)})`,
    )
    .join(", ");
  return `- **${claim.status.toUpperCase()}**: "${claim.claim}" (Q${claim.question_number}). ${claim.explanation}${evidence ? `. Evidence: ${evidence}` : ""}`;
}

/** Render the scorecard as Markdown for sharing or note-taking. */
export function reportToMarkdown(report: Report): string {
  const lines = [
    `# RepoGrill scorecard: ${report.repo_meta.full_name}`,
    "",
    `**Overall score: ${report.overall_score}/100**${report.ended_early ? " (ended early)" : ""}`,
    "",
    report.summary,
    "",
    "## Bluffs caught",
    "",
    ...(report.bluffs.length ? report.bluffs.map((c) => claimLine(report, c)) : ["None."]),
    "",
  ];
  if (report.strengths.length) {
    lines.push("## Strengths", "", ...report.strengths.map((s) => `- ${s}`), "");
  }
  lines.push("## Answers", "");
  for (const q of report.questions) {
    lines.push(
      `### Q${q.question_number}. ${q.topic} (${q.score}/100)`,
      "",
      `> ${q.question}`,
      "",
      `- Depth ${q.depth.score}/5: ${q.depth.feedback}`,
      `- Accuracy ${q.accuracy.score}/5: ${q.accuracy.feedback}`,
      `- Clarity ${q.clarity.score}/5: ${q.clarity.feedback}`,
      "",
    );
  }
  const verified = report.claims.filter((c) => c.status === "verified");
  if (verified.length) {
    lines.push(
      "## Claims backed by the code",
      "",
      ...verified.map((c) => claimLine(report, c)),
      "",
    );
  }
  lines.push("## Top questions to prep", "");
  report.prep.forEach((item, index) => {
    lines.push(`${index + 1}. **${item.question}**${item.why ? `: ${item.why}` : ""}`);
    item.talking_points.forEach((point) => lines.push(`   - ${point}`));
    if (item.files.length)
      lines.push(`   - Files: ${item.files.map((f) => `\`${f}\``).join(", ")}`);
  });
  return lines.join("\n") + "\n";
}

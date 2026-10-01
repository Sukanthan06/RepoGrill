const NAME = "[A-Za-z0-9][A-Za-z0-9._-]{0,99}";
const PATTERNS = [
  new RegExp(`^(?:https?://)?(?:www\.)?github\.com/(${NAME})/(${NAME})(?:[/?#].*)?$`, "i"),
  new RegExp(`^(?:ssh://)?git@github\.com[:/](${NAME})/(${NAME})$`, "i"),
  new RegExp(`^(${NAME})/(${NAME})$`),
];

/** Return "owner/repo" for a GitHub URL the backend will accept, or null. */
export function parseRepo(input: string): string | null {
  const text = input.trim();
  for (const pattern of PATTERNS) {
    const match = text.match(pattern);
    if (match) return `${match[1]}/${match[2].replace(/\.git$/i, "")}`;
  }
  return null;
}

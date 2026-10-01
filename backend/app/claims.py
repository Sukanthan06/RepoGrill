"""Extract technical claims from answers and check them against the code."""

import logging

from app.evidence import EvidenceSearcher, Verdict, verify_claim
from app.ingestion import estimate_tokens
from app.llm_client import LLMClient
from app.models import (
    AdjudicationBatch,
    ClaimCheck,
    ClaimExtraction,
    Evidence,
    ExtractedClaim,
    IngestedRepo,
    Session,
)
from app.prompt_loader import render

logger = logging.getLogger(__name__)

EXTRACTION_BATCH_TOKENS = 2500
ANSWER_CHAR_LIMIT = 2000
MAX_CLAIMS_PER_ANSWER = 5
CONTEXT_LINES = 2
EXTRACT_MAX_TOKENS = 3000
ADJUDICATE_MAX_TOKENS = 2500


def collect_answers(session: Session) -> list[tuple[int, int, str, str]]:
    """Return (answer_id, question_number, question_text, answer_text) for each answer."""
    answers = []
    for turn in session.transcript:
        if turn.speaker != "candidate":
            continue
        question = session.plan[min(turn.question_index, len(session.plan) - 1)]
        answers.append((len(answers), turn.question_index + 1, question.question, turn.text))
    return answers


def batch_answers(
    answers: list[tuple[int, int, str, str]], budget: int = EXTRACTION_BATCH_TOKENS
) -> list[list[tuple[int, int, str, str]]]:
    """Group answers so each extraction call stays within the token budget."""
    batches: list[list[tuple[int, int, str, str]]] = [[]]
    used = 0
    for answer in answers:
        cost = estimate_tokens(answer[2]) + min(estimate_tokens(answer[3]), ANSWER_CHAR_LIMIT // 4)
        if batches[-1] and used + cost > budget:
            batches.append([])
            used = 0
        batches[-1].append(answer)
        used += cost
    return [b for b in batches if b]


def _format_answers(batch: list[tuple[int, int, str, str]]) -> str:
    return "\n\n".join(
        f"[answer_id {aid}] Question: {question}\nAnswer: {text[:ANSWER_CHAR_LIMIT]}"
        for aid, _, question, text in batch
    )


def to_check(
    claim: ExtractedClaim, question_number: int, verdict: Verdict, adjudicated: bool = False
) -> ClaimCheck:
    return ClaimCheck(
        claim=claim.claim,
        keywords=claim.keywords,
        kind=claim.kind,
        question_number=question_number,
        status=verdict.status,
        explanation=verdict.explanation,
        evidence=[
            Evidence(file=m.path, line=m.line, snippet=m.snippet, source=m.source)
            for m in verdict.matches
        ],
        adjudicated=adjudicated,
    )


def _context(repo: IngestedRepo, evidence: Evidence) -> str:
    text = repo.index.contents.get(evidence.file)
    if not text or evidence.line is None:
        return f"{evidence.file}: {evidence.snippet or '(file exists)'}"
    lines = text.splitlines()
    start = max(0, evidence.line - 1 - CONTEXT_LINES)
    window = lines[start : evidence.line + CONTEXT_LINES]
    numbered = "\n".join(f"  {start + i + 1}: {line[:160]}" for i, line in enumerate(window))
    return f"{evidence.file}:\n{numbered}"


class ClaimChecker:
    def __init__(self, llm: LLMClient, fast_model: str) -> None:
        self.llm = llm
        self.fast_model = fast_model

    async def extract(self, session: Session, full_name: str) -> list[tuple[int, ExtractedClaim]]:
        """Return (question_number, claim) pairs for every answer in the session."""
        answers = collect_answers(session)
        question_of = {aid: qnum for aid, qnum, _, _ in answers}
        results: list[tuple[int, ExtractedClaim]] = []
        for batch in batch_answers(answers):
            messages = [
                {"role": "system", "content": render("claims_system")},
                {
                    "role": "user",
                    "content": render(
                        "claims_user", full_name=full_name, answers=_format_answers(batch)
                    ),
                },
            ]
            extraction = await self.llm.chat_json(
                messages,
                ClaimExtraction,
                model=self.fast_model,
                max_tokens=EXTRACT_MAX_TOKENS,
                temperature=0.0,
            )
            for item in extraction.answers:
                if item.answer_id in question_of:
                    for claim in item.claims[:MAX_CLAIMS_PER_ANSWER]:
                        results.append((question_of[item.answer_id], claim))
        return results

    async def check(self, session: Session, repo: IngestedRepo) -> list[ClaimCheck]:
        """Extract claims, verify deterministically, then adjudicate ambiguous ones."""
        claims = await self.extract(session, repo.meta.full_name)
        searcher = EvidenceSearcher(repo.index)
        checks: list[ClaimCheck] = []
        ambiguous: list[int] = []
        for question_number, claim in claims:
            verdict = verify_claim(claim, searcher)
            if verdict.ambiguous:
                ambiguous.append(len(checks))
            checks.append(to_check(claim, question_number, verdict))
        if ambiguous:
            await self._adjudicate(checks, ambiguous, repo)
        logger.info(
            "Checked %d claims (%d adjudicated) for session %s",
            len(checks), len(ambiguous), session.session_id,
        )  # fmt: skip
        return checks

    async def _adjudicate(
        self, checks: list[ClaimCheck], positions: list[int], repo: IngestedRepo
    ) -> None:
        items = []
        for item_id, position in enumerate(positions):
            check = checks[position]
            evidence = "\n".join(_context(repo, e) for e in check.evidence) or "(none)"
            items.append(f"[id {item_id}] Claim: {check.claim}\nEvidence:\n{evidence}")
        messages = [
            {"role": "system", "content": render("adjudicate_system")},
            {
                "role": "user",
                "content": render(
                    "adjudicate_user", full_name=repo.meta.full_name, items="\n\n".join(items)
                ),
            },
        ]
        batch = await self.llm.chat_json(
            messages,
            AdjudicationBatch,
            model=self.fast_model,
            max_tokens=ADJUDICATE_MAX_TOKENS,
            temperature=0.0,
        )
        for verdict in batch.verdicts:
            if 0 <= verdict.id < len(positions) and verdict.status in (
                "verified",
                "unverified",
                "contradicted",
            ):
                check = checks[positions[verdict.id]]
                check.status = verdict.status
                check.explanation = verdict.explanation or check.explanation
                check.adjudicated = True

"""Grade answers, compute the score and assemble the interview report."""

import asyncio
import logging

from app.claims import ClaimChecker
from app.context_pack import skeletonize
from app.dossier import PathResolver
from app.errors import BadRequestError
from app.ingestion import estimate_tokens, truncate_to_tokens
from app.interview import InterviewService, key_files
from app.llm_client import LLMClient
from app.models import (
    ClaimCheck,
    Dossier,
    GradeBatch,
    GradeOut,
    IngestedRepo,
    QuestionReport,
    Report,
    ReportSummary,
    ScoreLine,
    Session,
    Turn,
)
from app.prompt_loader import render
from app.store import TTLStore

logger = logging.getLogger(__name__)

GRADING_BATCH_TOKENS = 3000
GRADE_MAX_TOKENS = 3000
SUMMARY_MAX_TOKENS = 3500
CONTRADICTION_PENALTY = 5
MAX_PENALTY = 20
PREP_COUNT = 5
EXCHANGE_CHAR_LIMIT = 1500
STRUCTURE_FILES = 6
ANSWER_SUMMARY_CHARS = 400
STRUCTURE_TOKENS_PER_FILE = 150
NO_ANSWER = ScoreLine(score=1, feedback="No answer to grade.")


def group_exchanges(session: Session) -> dict[int, list[Turn]]:
    """Map question_number -> turns, keeping only questions the candidate answered."""
    groups: dict[int, list[Turn]] = {}
    for turn in session.transcript:
        if turn.kind == "closing":
            continue
        groups.setdefault(turn.question_index + 1, []).append(turn)
    return {
        number: turns
        for number, turns in groups.items()
        if any(t.speaker == "candidate" for t in turns)
    }


def question_score(grade: GradeOut | None) -> int:
    if grade is None:
        return 0
    total = grade.depth.score + grade.accuracy.score + grade.clarity.score
    return round(total / 15 * 100)


def overall_score(per_question: list[int], checks: list[ClaimCheck]) -> int:
    """Mean question score minus a capped penalty for each contradicted claim."""
    if not per_question:
        return 0
    base = sum(per_question) / len(per_question)
    contradicted = sum(1 for c in checks if c.status == "contradicted")
    penalty = min(MAX_PENALTY, contradicted * CONTRADICTION_PENALTY)
    return max(0, min(100, round(base - penalty)))


def select_bluffs(checks: list[ClaimCheck]) -> list[ClaimCheck]:
    """Contradicted claims, plus unverified claims about named technologies."""
    contradicted = [c for c in checks if c.status == "contradicted"]
    notable = [c for c in checks if c.status == "unverified" and c.kind == "technology"]
    return contradicted + notable


def _format_exchange(turns: list[Turn]) -> str:
    return "\n".join(
        f"{'Interviewer' if t.speaker == 'interviewer' else 'Candidate'}: "
        f"{t.text[:EXCHANGE_CHAR_LIMIT]}"
        for t in turns
    )


def _format_claims(checks: list[ClaimCheck]) -> str:
    if not checks:
        return "(no concrete claims)"
    lines = []
    for check in checks:
        where = f" ({check.evidence[0].file})" if check.evidence else ""
        lines.append(f"- [{check.status}] {check.claim}: {check.explanation}{where}")
    return "\n".join(lines)


def format_question_block(
    session: Session, number: int, turns: list[Turn], checks: list[ClaimCheck]
) -> str:
    question = session.plan[number - 1]
    return (
        f"## Question {number} (topic: {question.topic})\n"
        f"Planned question: {question.question}\n"
        f"A good answer covers: {'; '.join(question.what_good_answer_covers) or '(n/a)'}\n"
        f"Exchange:\n{_format_exchange(turns)}\n"
        f"Claim checks:\n{_format_claims([c for c in checks if c.question_number == number])}"
    )


def batch_blocks(blocks: list[tuple[int, str]], budget: int) -> list[list[tuple[int, str]]]:
    batches: list[list[tuple[int, str]]] = [[]]
    used = 0
    for number, block in blocks:
        cost = estimate_tokens(block)
        if batches[-1] and used + cost > budget:
            batches.append([])
            used = 0
        batches[-1].append((number, block))
        used += cost
    return [b for b in batches if b]


def candidate_answers(questions: list[QuestionReport]) -> str:
    """The candidate's own words per question, clipped, so the summary can't invent praise."""
    lines = []
    for q in questions:
        said = " / ".join(t.text for t in q.exchanges if t.speaker == "candidate")
        lines.append(f"- Q{q.question_number} ({q.topic}): {said[:ANSWER_SUMMARY_CHARS]}")
    return "\n".join(lines) or "(none)"


def prep_structure(
    repo: IngestedRepo, session: Session, questions: list[QuestionReport], dossier: Dossier
) -> str:
    """Skeletons of the files most relevant to weak answers, to ground prep talking points."""
    weakest = sorted(questions, key=lambda q: q.score)
    paths = [f for q in weakest for f in session.plan[q.question_number - 1].related_files]
    paths += key_files(dossier)
    blocks = []
    for path in dict.fromkeys(paths):
        text = repo.index.contents.get(path)
        skeleton = skeletonize(text) if text else ""
        if skeleton:
            cut, _ = truncate_to_tokens(skeleton, STRUCTURE_TOKENS_PER_FILE)
            blocks.append(f"### {path}\n{cut}")
        if len(blocks) >= STRUCTURE_FILES:
            break
    return "\n\n".join(blocks) or "(not available)"


class ReportBuilder:
    def __init__(self, llm: LLMClient, claims: ClaimChecker) -> None:
        self.llm = llm
        self.claims = claims

    async def grade(
        self,
        session: Session,
        repo: IngestedRepo,
        dossier: Dossier,
        groups: dict[int, list[Turn]],
        checks: list[ClaimCheck],
    ) -> dict[int, GradeOut]:
        blocks = [
            (n, format_question_block(session, n, turns, checks))
            for n, turns in sorted(groups.items())
        ]
        grades: dict[int, GradeOut] = {}
        for batch in batch_blocks(blocks, GRADING_BATCH_TOKENS):
            messages = [
                {"role": "system", "content": render("grading_system")},
                {
                    "role": "user",
                    "content": render(
                        "grading_user",
                        full_name=repo.meta.full_name,
                        summary=dossier.summary,
                        questions="\n\n".join(block for _, block in batch),
                    ),
                },
            ]
            result = await self.llm.chat_json(
                messages, GradeBatch, max_tokens=GRADE_MAX_TOKENS, temperature=0.2
            )
            wanted = {n for n, _ in batch}
            grades.update(
                {g.question_number: g for g in result.grades if g.question_number in wanted}
            )
        return grades

    async def summarize(
        self,
        session: Session,
        repo: IngestedRepo,
        dossier: Dossier,
        questions: list[QuestionReport],
        bluffs: list[ClaimCheck],
    ) -> ReportSummary:
        asked = {q.question_number for q in questions}
        asked_text = {session.plan[n - 1].question for n in asked}
        unasked = [q for q in dossier.candidate_questions if q.question not in asked_text]
        files = list(dict.fromkeys(key_files(dossier) + repo.ranked_paths[:25]))
        user = render(
            "summary_user",
            full_name=repo.meta.full_name,
            summary=dossier.summary,
            components="\n".join(
                f"- {c.name}: {c.responsibility} ({', '.join(c.files) or 'n/a'})"
                for c in dossier.architecture.components
            )
            or "(n/a)",
            weak_spots="\n".join(f"- [{w.area}] {w.description}" for w in dossier.likely_weak_spots)
            or "(none)",
            decisions="\n".join(f"- {d.decision}" for d in dossier.key_design_decisions)
            or "(none)",
            results="\n".join(
                f"- Q{q.question_number} {q.topic}: {q.score}/100. "
                f"depth: {q.depth.feedback} accuracy: {q.accuracy.feedback}"
                for q in questions
            ),
            bluffs="\n".join(f"- [{b.status}] {b.claim}: {b.explanation}" for b in bluffs)
            or "(none)",
            unasked="\n".join(f"- ({q.topic}) {q.question}" for q in unasked[:8]) or "(none)",
            answers=candidate_answers(questions),
            files="\n".join(files),
            structure=prep_structure(repo, session, questions, dossier),
        )
        messages = [
            {"role": "system", "content": render("summary_system")},
            {"role": "user", "content": user},
        ]
        result = await self.llm.chat_json(
            messages, ReportSummary, max_tokens=SUMMARY_MAX_TOKENS, temperature=0.3
        )
        resolver = PathResolver(repo.index.paths)
        for item in result.prep:
            item.files = resolver.resolve_all(item.files)
        result.prep = result.prep[:PREP_COUNT]
        return result

    async def build(self, session: Session, repo: IngestedRepo, dossier: Dossier) -> Report:
        groups = group_exchanges(session)
        if not groups:
            raise BadRequestError("Answer at least one question to get a scorecard")
        checks = await self.claims.check(session, repo)
        grades = await self.grade(session, repo, dossier, groups, checks)
        questions = []
        for number, turns in sorted(groups.items()):
            grade = grades.get(number)
            planned = session.plan[number - 1]
            questions.append(
                QuestionReport(
                    question_number=number,
                    topic=planned.topic,
                    question=planned.question,
                    exchanges=turns,
                    depth=grade.depth if grade else NO_ANSWER,
                    accuracy=grade.accuracy if grade else NO_ANSWER,
                    clarity=grade.clarity if grade else NO_ANSWER,
                    score=question_score(grade),
                )
            )
        bluffs = select_bluffs(checks)
        summary = await self.summarize(session, repo, dossier, questions, bluffs)
        return Report(
            session_id=session.session_id,
            repo_meta=repo.meta,
            overall_score=overall_score([q.score for q in questions], checks),
            summary=summary.summary,
            strengths=summary.strengths,
            questions=questions,
            claims=checks,
            bluffs=bluffs,
            prep=summary.prep,
            ended_early=session.ended_early,
        )


class ReportService:
    def __init__(
        self,
        builder: ReportBuilder,
        interviews: InterviewService,
        cache: TTLStore[str, Report],
    ) -> None:
        self.builder = builder
        self.interviews = interviews
        self.cache = cache
        self._inflight: dict[str, asyncio.Task[Report]] = {}

    async def get_or_create(self, session_id: str) -> Report:
        cached = self.cache.get(session_id)
        if cached:
            return cached
        session = self.interviews.get(session_id)
        if not session.done:
            raise BadRequestError("Finish or end the interview before requesting the scorecard")
        task = self._inflight.get(session_id)
        if task is None:
            task = asyncio.create_task(self._build(session))
            self._inflight[session_id] = task
            task.add_done_callback(lambda _: self._inflight.pop(session_id, None))
        return await asyncio.shield(task)

    async def _build(self, session: Session) -> Report:
        dossier, repo = await self.interviews.context(session)
        report = await self.builder.build(session, repo, dossier)
        self.cache.set(session.session_id, report)
        return report

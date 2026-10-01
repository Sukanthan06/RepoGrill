"""Interview session state machine: questions, adaptive follow-ups and transcript."""

import logging
import secrets

from app.dossier import DossierService
from app.errors import BadRequestError, NotFoundError
from app.ingestion import Ingestor
from app.llm_client import LLMClient
from app.models import (
    Difficulty,
    Dossier,
    InterviewerDecision,
    InterviewLength,
    Session,
    Turn,
    TurnKind,
    TurnOut,
)
from app.prompt_loader import render
from app.question_plan import plan_questions
from app.store import TTLStore

logger = logging.getLogger(__name__)

MAX_FOLLOW_UPS = 2
RECENT_TURNS = 4
MAX_NOTES = 8
TURN_CHAR_LIMIT = 1200
DECISION_MAX_TOKENS = 1500
GREETING = "Hi, thanks for joining. I've read through {name}, so let's dig in. "
CLOSING_EARLY = "Let's stop here. Thanks for your time, your scorecard is coming up next."
CLOSING_DEFAULT = "That's all my questions. Thanks, this was a good conversation."


def turn_out(session: Session, text: str, kind: TurnKind) -> TurnOut:
    return TurnOut(
        text=text,
        kind=kind,
        question_number=session.current + 1,
        total_questions=len(session.plan),
        topic=session.current_question.topic,
    )


def _clip(text: str, limit: int = TURN_CHAR_LIMIT) -> str:
    return text if len(text) <= limit else text[:limit] + " …"


def format_recent(turns: list[Turn]) -> str:
    lines = [
        f"{'Interviewer' if t.speaker == 'interviewer' else 'Candidate'}: {_clip(t.text)}"
        for t in turns[-RECENT_TURNS:]
    ]
    return "\n".join(lines) or "(none)"


def build_decision_messages(
    session: Session, dossier: Dossier, full_name: str, transcript: list[Turn]
) -> list[dict[str, str]]:
    """Compact per-call context: summary, current question, recent turns and notes."""
    question = session.current_question
    has_next = session.current + 1 < len(session.plan)
    if has_next:
        upcoming = session.plan[session.current + 1]
        next_instruction = (
            f"If you move on, the next planned question (topic: {upcoming.topic}) is: "
            f'"{upcoming.question}"'
        )
    else:
        next_instruction = 'This is the final question. If you move on, use "end" and close.'
    limit_hit = session.follow_ups_on_current >= MAX_FOLLOW_UPS
    stack = ", ".join(t.name for t in dossier.tech_stack[:12]) or "unknown"
    user = render(
        "interviewer_turn",
        summary=dossier.summary,
        stack=stack,
        question_number=session.current + 1,
        total_questions=len(session.plan),
        topic=question.topic,
        difficulty=question.difficulty,
        question=question.question,
        covers="; ".join(question.what_good_answer_covers) or "(not specified)",
        files=", ".join(question.related_files) or "(none listed)",
        follow_ups=session.follow_ups_on_current,
        follow_up_rule=" Limit reached: do NOT follow up." if limit_hit else "",
        notes="\n".join(f"- {n}" for n in session.notes[-MAX_NOTES:]) or "(none yet)",
        recent=format_recent(transcript),
        next_instruction=next_instruction,
    )
    return [
        {"role": "system", "content": render("interviewer_system", full_name=full_name)},
        {"role": "user", "content": user},
    ]


def apply_decision(session: Session, decision: InterviewerDecision) -> TurnOut:
    """Enforce interview rules on the model's decision and advance the session."""
    has_next = session.current + 1 < len(session.plan)
    action, utterance = decision.action, decision.utterance.strip()

    if action == "follow_up" and session.follow_ups_on_current >= MAX_FOLLOW_UPS:
        action, utterance = ("next_question", "") if has_next else ("end", "")
    if action == "next_question" and not has_next:
        action, utterance = "end", ""
    if action == "end" and has_next:
        action, utterance = "next_question", ""

    if decision.note:
        session.notes.append(decision.note.strip())

    kind: TurnKind
    if action == "follow_up":
        session.follow_ups_on_current += 1
        kind = "follow_up"
    elif action == "next_question":
        session.current += 1
        session.follow_ups_on_current = 0
        kind = "question"
        utterance = utterance or f"Okay, let's move on. {session.current_question.question}"
    else:
        session.done = True
        kind = "closing"
        utterance = utterance or CLOSING_DEFAULT

    session.transcript.append(
        Turn(speaker="interviewer", kind=kind, text=utterance, question_index=session.current)
    )
    return turn_out(session, utterance, kind)


class InterviewService:
    def __init__(
        self,
        llm: LLMClient,
        ingestor: Ingestor,
        dossiers: DossierService,
        sessions: TTLStore[str, Session],
    ) -> None:
        self.llm = llm
        self.ingestor = ingestor
        self.dossiers = dossiers
        self.sessions = sessions

    def get(self, session_id: str) -> Session:
        session = self.sessions.get(session_id)
        if session is None:
            raise NotFoundError("Interview session not found or expired")
        return session

    async def _context(self, session: Session) -> tuple[Dossier, str]:
        repo = self.ingestor.get(session.repo_id)
        if repo is None:
            raise NotFoundError("The repository for this session has expired; start again")
        return await self.dossiers.get_or_create(repo), repo.meta.full_name

    async def start(
        self, repo_id: str, length: InterviewLength, difficulty: Difficulty
    ) -> tuple[Session, TurnOut]:
        repo = self.ingestor.get(repo_id)
        if repo is None:
            raise NotFoundError("Unknown or expired repo_id; ingest the repository again")
        dossier = await self.dossiers.get_or_create(repo)
        session = Session(
            session_id=secrets.token_urlsafe(12),
            repo_id=repo_id,
            length=length,
            difficulty=difficulty,
            plan=plan_questions(dossier, length, difficulty),
        )
        text = GREETING.format(name=repo.meta.name) + session.current_question.question
        session.transcript.append(
            Turn(speaker="interviewer", kind="opener", text=text, question_index=0)
        )
        self.sessions.set(session.session_id, session)
        return session, turn_out(session, text, "opener")

    async def answer(self, session_id: str, text: str) -> TurnOut:
        session = self.get(session_id)
        answer = text.strip()
        if not answer:
            raise BadRequestError("Answer is empty")
        async with session.lock:
            if session.done:
                raise BadRequestError("This interview has already finished")
            dossier, full_name = await self._context(session)
            candidate_turn = Turn(
                speaker="candidate", kind="answer", text=answer, question_index=session.current
            )
            pending = [*session.transcript, candidate_turn]
            messages = build_decision_messages(session, dossier, full_name, pending)
            decision = await self.llm.chat_json(
                messages, InterviewerDecision, max_tokens=DECISION_MAX_TOKENS, temperature=0.5
            )
            logger.info("Session %s: %s (%s)", session_id, decision.action, decision.reason)
            # Only record the answer once the decision succeeded, so retries don't duplicate it.
            session.transcript.append(candidate_turn)
            return apply_decision(session, decision)

    def end_early(self, session_id: str) -> TurnOut:
        session = self.get(session_id)
        if not session.done:
            session.done = True
            session.ended_early = True
            session.transcript.append(
                Turn(
                    speaker="interviewer",
                    kind="closing",
                    text=CLOSING_EARLY,
                    question_index=session.current,
                )
            )
        return turn_out(session, session.transcript[-1].text, "closing")

    @staticmethod
    def current_turn(session: Session) -> TurnOut | None:
        last = next((t for t in reversed(session.transcript) if t.speaker == "interviewer"), None)
        return turn_out(session, last.text, last.kind) if last else None

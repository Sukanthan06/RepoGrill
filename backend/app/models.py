"""Pydantic schemas for API payloads, internal state and LLM outputs."""

import asyncio
from typing import Literal

from pydantic import BaseModel, Field, PrivateAttr, field_validator

# ---------------------------------------------------------------- ingestion


class RepoMeta(BaseModel):
    owner: str
    name: str
    full_name: str
    description: str = ""
    default_branch: str
    sha: str
    stars: int = 0
    language: str | None = None
    html_url: str
    total_files: int
    tree_truncated: bool = False


class FileSnippet(BaseModel):
    path: str
    content: str
    truncated: bool = False


class EvidenceIndex(BaseModel):
    """Everything we know about the repo, used to verify interview claims."""

    paths: list[str] = Field(default_factory=list)
    # dependency name (lowercase) -> manifest files that declare it
    dependencies: dict[str, list[str]] = Field(default_factory=dict)
    # path -> full fetched text (searchable)
    contents: dict[str, str] = Field(default_factory=dict)


class IngestedRepo(BaseModel):
    repo_id: str
    meta: RepoMeta
    context_files: list[FileSnippet]
    index: EvidenceIndex
    # Non-noise paths ordered by importance (used to show the model real file names)
    ranked_paths: list[str] = Field(default_factory=list)


class IngestRequest(BaseModel):
    repo_url: str = Field(min_length=3, max_length=300)


class IngestResponse(BaseModel):
    repo_id: str
    repo_meta: RepoMeta
    files_analyzed: list[str]
    dependencies: list[str]


# ------------------------------------------------------------------ dossier

WEAK_SPOT_AREAS = ("scaling", "error_handling", "security", "testing", "concurrency", "other")


def _as_list(value: object) -> object:
    """LLMs sometimes return a single string where a list is expected."""
    return [value] if isinstance(value, str) else value


class TechItem(BaseModel):
    name: str
    purpose: str = ""
    evidence_files: list[str] = Field(default_factory=list)


class Component(BaseModel):
    name: str
    responsibility: str
    files: list[str] = Field(default_factory=list)


class Architecture(BaseModel):
    components: list[Component] = Field(default_factory=list)
    data_flow: str = ""


class DesignDecision(BaseModel):
    decision: str
    rationale: str = ""
    files: list[str] = Field(default_factory=list)


class WeakSpot(BaseModel):
    area: str
    description: str
    files: list[str] = Field(default_factory=list)

    @field_validator("area", mode="before")
    @classmethod
    def normalize_area(cls, value: object) -> str:
        area = str(value).strip().lower().replace(" ", "_").replace("-", "_")
        return area if area in WEAK_SPOT_AREAS else "other"


class CandidateQuestion(BaseModel):
    topic: str
    difficulty: int = Field(ge=1, le=3)
    question: str
    what_good_answer_covers: list[str] = Field(default_factory=list)
    related_files: list[str] = Field(default_factory=list)

    @field_validator("what_good_answer_covers", mode="before")
    @classmethod
    def coerce_covers(cls, value: object) -> object:
        return _as_list(value)


class Dossier(BaseModel):
    summary: str
    tech_stack: list[TechItem] = Field(default_factory=list)
    architecture: Architecture = Field(default_factory=Architecture)
    key_design_decisions: list[DesignDecision] = Field(default_factory=list)
    likely_weak_spots: list[WeakSpot] = Field(default_factory=list)
    candidate_questions: list[CandidateQuestion] = Field(min_length=6)


class DossierResponse(BaseModel):
    repo_id: str
    repo_meta: RepoMeta
    dossier: Dossier


# ---------------------------------------------------------------- interview

Difficulty = Literal["easy", "medium", "hard"]
InterviewLength = Literal[5, 8, 12]
TurnKind = Literal["opener", "question", "follow_up", "closing", "answer"]


class Turn(BaseModel):
    speaker: Literal["interviewer", "candidate"]
    kind: TurnKind
    text: str
    question_index: int


class InterviewerDecision(BaseModel):
    """Structured output of the interviewer LLM after each candidate answer."""

    assessment: str = ""
    unsupported_claims: list[str] = Field(default_factory=list)
    action: Literal["follow_up", "next_question", "end"]
    reason: str = ""
    utterance: str = Field(min_length=1)
    note: str = ""

    @field_validator("action", "assessment", mode="before")
    @classmethod
    def normalize_label(cls, value: object) -> object:
        return str(value or "").strip().lower().replace("-", "_").replace(" ", "_")

    @field_validator("unsupported_claims", mode="before")
    @classmethod
    def coerce_claims(cls, value: object) -> object:
        return [] if value is None else _as_list(value)


class Session(BaseModel):
    session_id: str
    repo_id: str
    length: InterviewLength
    difficulty: Difficulty
    plan: list[CandidateQuestion]
    current: int = 0
    follow_ups_on_current: int = 0
    transcript: list[Turn] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)
    done: bool = False
    ended_early: bool = False
    # Serializes answers so a double-submit can't advance the interview twice.
    _lock: asyncio.Lock = PrivateAttr(default_factory=asyncio.Lock)

    @property
    def lock(self) -> asyncio.Lock:
        return self._lock

    @property
    def current_question(self) -> CandidateQuestion:
        return self.plan[self.current]


class SessionRequest(BaseModel):
    repo_id: str
    length: InterviewLength = 8
    difficulty: Difficulty = "medium"


class TurnOut(BaseModel):
    text: str
    kind: TurnKind
    question_number: int
    total_questions: int
    topic: str


class SessionResponse(BaseModel):
    session_id: str
    repo_meta: RepoMeta
    first_turn: TurnOut


class AnswerRequest(BaseModel):
    text: str = Field(min_length=1, max_length=6000)


class AnswerResponse(BaseModel):
    next_turn: TurnOut
    done: bool


class SessionState(BaseModel):
    session_id: str
    repo_meta: RepoMeta
    length: InterviewLength
    difficulty: Difficulty
    transcript: list[Turn]
    current_turn: TurnOut | None
    done: bool


# ------------------------------------------------------------------- speech


class TranscriptionResponse(BaseModel):
    text: str


# ---------------------------------------------------------------- scorecard

ClaimStatus = Literal["verified", "unverified", "contradicted"]
EvidenceSource = Literal["dependency", "path", "content"]


class ExtractedClaim(BaseModel):
    claim: str
    keywords: list[str] = Field(default_factory=list)
    kind: str = "other"  # technology | implementation | file | other

    @field_validator("keywords", mode="before")
    @classmethod
    def coerce_keywords(cls, value: object) -> object:
        return [] if value is None else _as_list(value)


class AnswerClaims(BaseModel):
    answer_id: int
    claims: list[ExtractedClaim] = Field(default_factory=list)


class ClaimExtraction(BaseModel):
    answers: list[AnswerClaims] = Field(default_factory=list)


class Evidence(BaseModel):
    file: str
    line: int | None = None
    snippet: str = ""
    source: EvidenceSource = "content"


class ClaimCheck(BaseModel):
    claim: str
    keywords: list[str] = Field(default_factory=list)
    kind: str = "other"
    question_number: int
    status: ClaimStatus
    explanation: str = ""
    evidence: list[Evidence] = Field(default_factory=list)
    adjudicated: bool = False


class Adjudication(BaseModel):
    id: int
    status: ClaimStatus
    explanation: str = ""

    @field_validator("status", mode="before")
    @classmethod
    def normalize_status(cls, value: object) -> object:
        return str(value).strip().lower()


class AdjudicationBatch(BaseModel):
    verdicts: list[Adjudication] = Field(default_factory=list)


class ScoreLine(BaseModel):
    score: int = Field(ge=1, le=5)
    feedback: str = ""


class GradeOut(BaseModel):
    question_number: int
    depth: ScoreLine
    accuracy: ScoreLine
    clarity: ScoreLine


class GradeBatch(BaseModel):
    grades: list[GradeOut] = Field(default_factory=list)


class PrepItem(BaseModel):
    question: str
    why: str = ""
    talking_points: list[str] = Field(default_factory=list)
    files: list[str] = Field(default_factory=list)

    @field_validator("talking_points", "files", mode="before")
    @classmethod
    def coerce_lists(cls, value: object) -> object:
        return [] if value is None else _as_list(value)


class ReportSummary(BaseModel):
    summary: str
    strengths: list[str] = Field(default_factory=list)
    prep: list[PrepItem] = Field(default_factory=list)


class QuestionReport(BaseModel):
    question_number: int
    topic: str
    question: str
    exchanges: list[Turn]
    depth: ScoreLine
    accuracy: ScoreLine
    clarity: ScoreLine
    score: int  # 0-100 for this question


class Report(BaseModel):
    session_id: str
    repo_meta: RepoMeta
    overall_score: int
    summary: str
    strengths: list[str]
    questions: list[QuestionReport]
    claims: list[ClaimCheck]
    bluffs: list[ClaimCheck]
    prep: list[PrepItem]
    ended_early: bool = False

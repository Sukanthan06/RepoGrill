"""Pydantic schemas for API payloads, internal state and LLM outputs."""

from pydantic import BaseModel, Field, field_validator

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

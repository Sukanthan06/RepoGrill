"""Pydantic schemas for API payloads, internal state and LLM outputs."""

from pydantic import BaseModel, Field

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

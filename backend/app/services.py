"""Long-lived clients and stores shared by the request handlers."""

from dataclasses import dataclass, field

from fastapi import Request

from app.config import Settings
from app.github_client import GitHubClient
from app.ingestion import Ingestor
from app.llm_client import LLMClient
from app.models import IngestedRepo
from app.store import TTLStore


@dataclass
class Services:
    settings: Settings
    llm: LLMClient
    github: GitHubClient
    ingestor: Ingestor
    stores: list[TTLStore] = field(default_factory=list)

    @classmethod
    def create(cls, settings: Settings) -> "Services":
        repos: TTLStore[str, IngestedRepo] = TTLStore(settings.session_ttl_seconds)
        github = GitHubClient(settings)
        return cls(
            settings=settings,
            llm=LLMClient(settings),
            github=github,
            ingestor=Ingestor(github, repos),
            stores=[repos],
        )

    async def aclose(self) -> None:
        await self.llm.aclose()
        await self.github.aclose()


def get_services(request: Request) -> Services:
    return request.app.state.services  # type: ignore[no-any-return]

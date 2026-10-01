from typing import Annotated

from fastapi import APIRouter, Depends

from app.models import IngestRequest, IngestResponse
from app.services import Services, get_services

router = APIRouter(prefix="/api", tags=["ingest"])


@router.post("/ingest")
async def ingest(
    body: IngestRequest, services: Annotated[Services, Depends(get_services)]
) -> IngestResponse:
    repo = await services.ingestor.ingest(body.repo_url)
    return IngestResponse(
        repo_id=repo.repo_id,
        repo_meta=repo.meta,
        files_analyzed=[f.path for f in repo.context_files],
        dependencies=sorted(repo.index.dependencies),
    )

from typing import Annotated

from fastapi import APIRouter, Depends

from app.errors import NotFoundError
from app.models import DossierResponse
from app.services import Services, get_services

router = APIRouter(prefix="/api", tags=["dossier"])


@router.get("/dossier/{repo_id}")
async def get_dossier(
    repo_id: str, services: Annotated[Services, Depends(get_services)]
) -> DossierResponse:
    repo = services.ingestor.get(repo_id)
    if repo is None:
        raise NotFoundError("Unknown or expired repo_id; ingest the repository again")
    dossier = await services.dossiers.get_or_create(repo)
    return DossierResponse(repo_id=repo.repo_id, repo_meta=repo.meta, dossier=dossier)

from typing import Annotated

from fastapi import APIRouter, Depends

from app.errors import NotFoundError
from app.models import (
    AnswerRequest,
    AnswerResponse,
    Report,
    SessionRequest,
    SessionResponse,
    SessionState,
)
from app.services import Services, get_services

router = APIRouter(prefix="/api/session", tags=["session"])
ServicesDep = Annotated[Services, Depends(get_services)]


@router.post("")
async def create_session(body: SessionRequest, services: ServicesDep) -> SessionResponse:
    session, first_turn = await services.interviews.start(
        body.repo_id, body.length, body.difficulty
    )
    repo = services.ingestor.get(session.repo_id)
    assert repo is not None
    return SessionResponse(
        session_id=session.session_id, repo_meta=repo.meta, first_turn=first_turn
    )


@router.get("/{session_id}")
async def get_session(session_id: str, services: ServicesDep) -> SessionState:
    session = services.interviews.get(session_id)
    repo = services.ingestor.get(session.repo_id)
    if repo is None:
        raise NotFoundError("The repository for this session has expired; start again")
    return SessionState(
        session_id=session.session_id,
        repo_meta=repo.meta,
        length=session.length,
        difficulty=session.difficulty,
        transcript=session.transcript,
        current_turn=services.interviews.current_turn(session),
        done=session.done,
    )


@router.post("/{session_id}/answer")
async def answer(session_id: str, body: AnswerRequest, services: ServicesDep) -> AnswerResponse:
    next_turn = await services.interviews.answer(session_id, body.text)
    return AnswerResponse(next_turn=next_turn, done=next_turn.kind == "closing")


@router.post("/{session_id}/end")
async def end_session(session_id: str, services: ServicesDep) -> AnswerResponse:
    return AnswerResponse(next_turn=services.interviews.end_early(session_id), done=True)


@router.get("/{session_id}/report")
async def get_report(session_id: str, services: ServicesDep) -> Report:
    return await services.reports.get_or_create(session_id)

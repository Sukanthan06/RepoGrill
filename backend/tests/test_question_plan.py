from app.models import CandidateQuestion, Dossier
from app.question_plan import OPENER_TEXT, plan_questions, target_difficulties


def make_dossier() -> Dossier:
    questions = [
        CandidateQuestion(topic=f"topic{i % 6}", difficulty=1 + i % 3, question=f"q{i}")
        for i in range(12)
    ]
    return Dossier(summary="s", candidate_questions=questions)


def test_targets_ramp_up() -> None:
    assert target_difficulties(3, "medium") == [1.0, 2.0, 3.0]
    hard = target_difficulties(4, "hard")
    assert hard[0] == 2.0 and hard[-1] == 3.0


def test_plan_starts_with_opener_and_has_requested_length() -> None:
    plan = plan_questions(make_dossier(), 8, "medium")
    assert len(plan) == 8
    assert plan[0].question == OPENER_TEXT
    assert len({q.question for q in plan}) == 8


def test_plan_balances_topics() -> None:
    plan = plan_questions(make_dossier(), 8, "medium")[1:]
    topics = [q.topic for q in plan]
    assert len(set(topics)) == 6  # all six topics before any repeats


def test_hard_level_avoids_easy_questions() -> None:
    plan = plan_questions(make_dossier(), 5, "hard")[1:]
    assert all(q.difficulty >= 2 for q in plan)


def test_easy_level_starts_easy() -> None:
    plan = plan_questions(make_dossier(), 5, "easy")[1:]
    assert plan[0].difficulty == 1
    assert all(q.difficulty <= 2 for q in plan)


def test_short_pool_returns_what_exists() -> None:
    dossier = make_dossier()
    dossier.candidate_questions = dossier.candidate_questions[:6]
    assert len(plan_questions(dossier, 12, "medium")) == 7

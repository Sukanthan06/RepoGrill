from app.claims import batch_answers, collect_answers
from app.models import CandidateQuestion, ClaimCheck, GradeOut, ScoreLine, Session, Turn
from app.scoring import group_exchanges, overall_score, question_score, select_bluffs


def make_session() -> Session:
    plan = [CandidateQuestion(topic=f"t{i}", difficulty=1, question=f"Q{i}?") for i in range(3)]
    transcript = [
        Turn(speaker="interviewer", kind="opener", text="Q0?", question_index=0),
        Turn(speaker="candidate", kind="answer", text="answer zero", question_index=0),
        Turn(speaker="interviewer", kind="follow_up", text="more?", question_index=0),
        Turn(speaker="candidate", kind="answer", text="answer zero b", question_index=0),
        Turn(speaker="interviewer", kind="question", text="Q1?", question_index=1),
        Turn(speaker="interviewer", kind="closing", text="bye", question_index=1),
    ]
    return Session(
        session_id="s", repo_id="r", length=5, difficulty="easy", plan=plan, transcript=transcript
    )


def check(status: str, kind: str = "technology") -> ClaimCheck:
    return ClaimCheck(claim="c", question_number=1, status=status, kind=kind)  # type: ignore[arg-type]


def grade(d: int, a: int, c: int) -> GradeOut:
    return GradeOut(
        question_number=1,
        depth=ScoreLine(score=d),
        accuracy=ScoreLine(score=a),
        clarity=ScoreLine(score=c),
    )


def test_group_exchanges_keeps_only_answered_questions() -> None:
    groups = group_exchanges(make_session())
    assert list(groups) == [1]
    assert len(groups[1]) == 4


def test_collect_answers_maps_to_question_numbers() -> None:
    answers = collect_answers(make_session())
    assert [(a[0], a[1], a[3]) for a in answers] == [
        (0, 1, "answer zero"),
        (1, 1, "answer zero b"),
    ]


def test_batch_answers_splits_on_budget() -> None:
    answers = [(i, 1, "q", "word " * 400) for i in range(5)]
    batches = batch_answers(answers, budget=250)
    assert len(batches) == 5
    assert sum(len(b) for b in batches) == 5


def test_question_score_scales_to_100() -> None:
    assert question_score(grade(5, 5, 5)) == 100
    assert question_score(grade(3, 3, 3)) == 60
    assert question_score(None) == 0


def test_overall_score_penalizes_contradictions_with_cap() -> None:
    assert overall_score([80, 60], []) == 70
    assert overall_score([80, 60], [check("contradicted")]) == 65
    assert overall_score([80, 60], [check("contradicted")] * 10) == 50
    assert overall_score([], []) == 0


def test_bluffs_are_contradictions_then_unverified_technologies() -> None:
    checks = [
        check("verified"),
        check("unverified", kind="implementation"),
        check("unverified"),
        check("contradicted"),
    ]
    assert [c.status for c in select_bluffs(checks)] == ["contradicted", "unverified"]

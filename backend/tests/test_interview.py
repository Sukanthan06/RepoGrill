from app.interview import apply_decision, build_decision_messages, is_non_answer
from app.models import (
    CandidateQuestion,
    Dossier,
    EvidenceIndex,
    IngestedRepo,
    InterviewerDecision,
    RepoMeta,
    Session,
    Turn,
)


def make_session(n_questions: int = 3) -> Session:
    plan = [
        CandidateQuestion(topic=f"t{i}", difficulty=1, question=f"Question {i}?")
        for i in range(n_questions)
    ]
    return Session(session_id="s", repo_id="r", length=5, difficulty="medium", plan=plan)


def decide(action: str, utterance: str = "Model says something.") -> InterviewerDecision:
    return InterviewerDecision(action=action, utterance=utterance, note="n")


def test_follow_up_stays_on_question() -> None:
    session = make_session()
    out = apply_decision(session, decide("follow_up"))
    assert out.kind == "follow_up"
    assert session.current == 0 and session.follow_ups_on_current == 1


def test_follow_ups_capped_at_two() -> None:
    session = make_session()
    apply_decision(session, decide("follow_up"))
    apply_decision(session, decide("follow_up"))
    out = apply_decision(session, decide("follow_up"))
    assert out.kind == "question"
    assert session.current == 1 and session.follow_ups_on_current == 0
    assert "Question 1?" in out.text  # templated move-on, not the stale follow-up


def test_next_question_on_last_becomes_end() -> None:
    session = make_session(2)
    apply_decision(session, decide("next_question"))
    out = apply_decision(session, decide("next_question"))
    assert out.kind == "closing" and session.done


def test_premature_end_is_coerced_to_next_question() -> None:
    session = make_session()
    out = apply_decision(session, decide("end"))
    assert out.kind == "question" and not session.done
    assert session.current == 1


def test_notes_and_transcript_recorded() -> None:
    session = make_session()
    apply_decision(session, decide("next_question", "Got it. Question 1?"))
    assert session.notes == ["n"]
    assert session.transcript[-1].speaker == "interviewer"
    assert session.transcript[-1].question_index == 1


def test_context_uses_only_recent_turns() -> None:
    session = make_session()
    transcript = [
        Turn(speaker="candidate" if i % 2 else "interviewer", kind="answer", text=f"turn-{i}",
             question_index=0)
        for i in range(10)
    ]  # fmt: skip
    dossier = Dossier(
        summary="A todo app",
        candidate_questions=[CandidateQuestion(topic="x", difficulty=1, question="q")] * 6,
    )
    repo = IngestedRepo(
        repo_id="r",
        meta=RepoMeta(owner="o", name="r", full_name="o/r", default_branch="main", sha="x",
                      html_url="u", total_files=1),
        context_files=[],
        index=EvidenceIndex(dependencies={"flask": ["requirements.txt"]}),
    )  # fmt: skip
    messages = build_decision_messages(session, dossier, repo, transcript)
    user = messages[1]["content"]
    assert "turn-9" in user and "turn-6" in user
    assert "turn-5" not in user
    assert "Question 1?" in user  # next planned question is offered
    assert "A todo app" in user
    assert "flask" in user  # dependencies let the interviewer challenge made-up tech


def test_non_answers_detected() -> None:
    assert is_non_answer("ok")
    assert is_non_answer("I don't know.")
    assert is_non_answer("no idea")
    assert not is_non_answer("We cache results in Redis keyed by user id.")


def test_repeated_non_answer_moves_on() -> None:
    session = make_session()
    apply_decision(session, decide("follow_up"), "I don't know")
    out = apply_decision(session, decide("follow_up"), "no idea")
    assert out.kind == "question" and session.current == 1


def test_assessment_is_normalized() -> None:
    decision = InterviewerDecision(
        assessment="Contradicts Code", action="follow_up", utterance="x", unsupported_claims=None
    )
    assert decision.assessment == "contradicts_code"
    assert decision.unsupported_claims == []

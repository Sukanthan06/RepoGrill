"""Pick and order dossier questions for an interview of a given length and level."""

from app.models import CandidateQuestion, Difficulty, Dossier

OPENER_TEXT = "Walk me through this project and what you built."

# Difficulty ramps (start, end) per chosen level, on the dossier's 1-3 scale.
DIFFICULTY_RAMPS: dict[Difficulty, tuple[float, float]] = {
    "easy": (1.0, 2.0),
    "medium": (1.0, 3.0),
    "hard": (2.0, 3.0),
}


def target_difficulties(count: int, level: Difficulty) -> list[float]:
    """Evenly spaced difficulty targets that ramp up over the interview."""
    start, end = DIFFICULTY_RAMPS[level]
    if count <= 1:
        return [end if level == "hard" else start]
    step = (end - start) / (count - 1)
    return [start + i * step for i in range(count)]


def opener(dossier: Dossier) -> CandidateQuestion:
    components = [c.name for c in dossier.architecture.components[:4]]
    covers = ["what problem it solves and for whom", "their personal role and contributions"]
    if components:
        covers.append("how the main parts fit together: " + ", ".join(components))
    return CandidateQuestion(
        topic="Project overview",
        difficulty=1,
        question=OPENER_TEXT,
        what_good_answer_covers=covers,
    )


def _pick(pool: list[CandidateQuestion], target: float, used_topics: set[str]) -> CandidateQuestion:
    def cost(item: tuple[int, CandidateQuestion]) -> tuple[float, int]:
        order, question = item
        repeat_penalty = 1.5 if question.topic.strip().lower() in used_topics else 0.0
        return abs(question.difficulty - target) + repeat_penalty, order

    _, best = min(enumerate(pool), key=cost)
    return best


def plan_questions(dossier: Dossier, length: int, level: Difficulty) -> list[CandidateQuestion]:
    """Return `length` questions: the fixed opener followed by balanced dossier picks."""
    pool = list(dossier.candidate_questions)
    picks: list[CandidateQuestion] = []
    used_topics: set[str] = set()
    for target in target_difficulties(length - 1, level):
        if not pool:
            break
        choice = _pick(pool, target, used_topics)
        pool.remove(choice)
        used_topics.add(choice.topic.strip().lower())
        picks.append(choice)
    return [opener(dossier), *picks]

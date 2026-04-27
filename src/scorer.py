from __future__ import annotations


def clamp_score(value: float) -> float:
    if value < 0:
        return 0.0
    if value > 1:
        return 1.0
    return float(value)


def combine_scores(
    person_match_score: float,
    employment_evidence_score: float,
    llm_confidence: float,
) -> float:
    score = (
        0.55 * clamp_score(person_match_score)
        + 0.25 * clamp_score(employment_evidence_score)
        + 0.20 * clamp_score(llm_confidence)
    )
    return round(clamp_score(score), 4)
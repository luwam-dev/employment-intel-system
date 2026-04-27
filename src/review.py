from __future__ import annotations


def decide_review(
    person_match_score: float,
    employment_evidence_score: float,
    final_score: float,
    has_source_url: bool,
    has_employment_fields: bool,
) -> tuple[str, str]:
    if not has_source_url:
        return "manual_review", "no_candidate_found"

    if person_match_score < 0.50:
        return "manual_review", "weak_person_match"

    if final_score < 0.50:
        return "manual_review", "low_final_score"

    if has_source_url and not has_employment_fields and employment_evidence_score < 0.15:
        return "manual_review", "profile_found_but_no_employment_evidence"

    if has_source_url and not has_employment_fields:
        return "manual_review", "profile_found_no_employer"

    return "", ""


def decide_status(
    has_source_url: bool,
    has_employment_fields: bool,
    final_score: float,
) -> str:
    if not has_source_url:
        return "not_found"

    if has_employment_fields and final_score >= 0.65:
        return "employment_found"

    if has_source_url and not has_employment_fields:
        return "profile_found_no_employer"

    return "profile_found"
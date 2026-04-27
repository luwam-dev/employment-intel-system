from __future__ import annotations

from dataclasses import dataclass
import re

from src.discovery import CandidatePage, Student, normalize_text


ROLE_KEYWORDS = [
    "data engineer",
    "data analyst",
    "data scientist",
    "software engineer",
    "software developer",
    "machine learning engineer",
    "analytics engineer",
    "business analyst",
    "researcher",
    "consultant",
    "manager",
    "intern",
    "reader",
    "lecturer",
]


LOCATION_PATTERNS = [
    r"location:\s*([A-Za-z0-9,\-\.\s]+)",
    r"([A-Z][A-Za-z\-\s]+,\s*[A-Z][A-Za-z\-\s]+,\s*[A-Z][A-Za-z\-\s]+)",
    r"([A-Z][A-Za-z\-\s]+,\s*[A-Z][A-Za-z\-\s]+)",
]


@dataclass
class MatchResult:
    matched_name: str = ""
    source_url: str = ""
    source_title: str = ""
    page_type: str = ""
    person_match_score: float = 0.0
    employment_evidence_score: float = 0.0
    final_score: float = 0.0
    company: str = ""
    role: str = ""
    location: str = ""
    evidence: str = ""
    confidence: float = 0.0
    employment_status: str = "not_found"
    review_flag: str = "manual_review"
    review_reason: str = "no_candidate_found"
    match_status: str = "not_found"


def clean_text(value: str) -> str:
    return re.sub(r"\s+", " ", (value or "").strip())


def split_title_parts(title: str) -> list[str]:
    if not title:
        return []
    parts = re.split(r"\s+[|\-–·]\s+", title)
    return [clean_text(p) for p in parts if clean_text(p)]


def normalize_name_tokens(value: str) -> list[str]:
    return re.findall(r"[a-z]+", normalize_text(value))


def token_overlap_score(student: Student, text: str) -> float:
    student_tokens = set(normalize_name_tokens(student.full_name))
    text_tokens = set(normalize_name_tokens(text))
    if not student_tokens:
        return 0.0
    overlap = len(student_tokens & text_tokens)
    return overlap / max(len(student_tokens), 1)


def compute_person_match(student: Student, candidate: CandidatePage) -> float:
    blob = clean_text(f"{candidate.title} {candidate.snippet} {candidate.text} {candidate.url}")
    blob_norm = normalize_text(blob)

    full_name = normalize_text(student.full_name)
    first_name = normalize_text(student.first_name)
    last_name = normalize_text(student.last_name)

    score = 0.0

    if full_name and full_name in blob_norm:
        score += 0.70

    if first_name and first_name in blob_norm:
        score += 0.15

    if last_name and last_name in blob_norm:
        score += 0.20

    if first_name and last_name and first_name in blob_norm and last_name in blob_norm:
        score += 0.15

    score += 0.40 * token_overlap_score(student, blob)

    university = normalize_text(student.university or "Brunel University London")
    if university and university in blob_norm:
        score += 0.15
    elif "brunel university" in blob_norm:
        score += 0.10

    url_lower = (candidate.url or "").lower()
    if "/pub/dir/" in url_lower:
        score -= 0.25

    if any(x in url_lower for x in ["/posts/", "/pulse/", "/advice/"]):
        score -= 0.35

    return round(min(max(score, 0.0), 1.0), 4)


def extract_role(blob: str) -> str:
    blob_clean = clean_text(blob)

    for role in ROLE_KEYWORDS:
        match = re.search(rf"\b({re.escape(role)})\b", blob_clean, flags=re.I)
        if match:
            return clean_text(match.group(1))

    for role in ["Reader", "Lecturer", "Researcher", "Consultant", "Manager", "Engineer", "Analyst"]:
        if re.search(rf"\b{re.escape(role)}\b", blob_clean, flags=re.I):
            return role

    return ""


def extract_company_from_title(title: str, student: Student) -> str:
    parts = split_title_parts(title)
    if len(parts) >= 2:
        name_part = normalize_text(parts[0])
        if normalize_text(student.first_name) in name_part or normalize_text(student.last_name) in name_part:
            company_candidate = clean_text(parts[1])
            if company_candidate and "linkedin" not in company_candidate.lower():
                return company_candidate
    return ""


def extract_company_from_snippet(snippet: str) -> str:
    snippet = clean_text(snippet)

    patterns = [
        r"Experience:\s*([^·|]+)",
        r"works at\s+([^·|,.]+)",
        r"at\s+([A-Z][A-Za-z0-9&,\-.\' ]{1,60})",
    ]

    for pattern in patterns:
        match = re.search(pattern, snippet, flags=re.I)
        if match:
            value = clean_text(match.group(1))
            value = re.sub(r"^(the\s+)", "", value, flags=re.I)
            if value and len(value) >= 2:
                return value

    return ""


def extract_location(blob: str) -> str:
    blob_clean = clean_text(blob)

    for pattern in LOCATION_PATTERNS:
        match = re.search(pattern, blob_clean, flags=re.I)
        if match:
            location = clean_text(match.group(1))
            if len(location) <= 80:
                return location

    for sep in ["· Location:", "Location:"]:
        if sep.lower() in blob_clean.lower():
            idx = blob_clean.lower().find(sep.lower())
            part = blob_clean[idx:].split("·", 2)
            if part:
                value = re.sub(r"(?i)^.*location:\s*", "", part[0]).strip()
                if value:
                    return clean_text(value)

    return ""


def extract_employment_fields(student: Student, candidate: CandidatePage) -> tuple[str, str, str, str]:
    title = clean_text(candidate.title)
    snippet = clean_text(candidate.snippet)
    text = clean_text(candidate.text)
    blob = clean_text(f"{title} {snippet} {text}")

    company = extract_company_from_title(title, student)
    if not company:
        company = extract_company_from_snippet(snippet)
    if not company and candidate.page_type == "brunel_page" and "brunel" in normalize_text(blob):
        company = "Brunel University London"

    role = extract_role(blob)
    location = extract_location(blob)

    evidence_parts = []
    if title:
        evidence_parts.append(f"title={title}")
    if snippet:
        evidence_parts.append(f"snippet={snippet[:220]}")
    elif text:
        evidence_parts.append(f"text={text[:220]}")

    evidence = " | ".join(evidence_parts)
    return company, role, location, evidence


def compute_employment_evidence(candidate: CandidatePage, company: str, role: str, location: str) -> float:
    blob = normalize_text(f"{candidate.title} {candidate.snippet} {candidate.text}")
    score = 0.0

    if company:
        score += 0.45
    if role:
        score += 0.30
    if location:
        score += 0.10

    if "experience:" in blob:
        score += 0.20

    if candidate.page_type == "linkedin_profile":
        score += 0.15

    if candidate.page_type == "brunel_page":
        score += 0.20

    url_lower = (candidate.url or "").lower()
    if "/pub/dir/" in url_lower:
        score -= 0.15

    if any(x in url_lower for x in ["/posts/", "/pulse/", "/advice/"]):
        score -= 0.25

    return round(min(max(score, 0.0), 1.0), 4)


def match_candidate(student: Student, candidate: CandidatePage) -> MatchResult:
    company, role, location, evidence = extract_employment_fields(student, candidate)
    person_match_score = compute_person_match(student, candidate)
    employment_evidence_score = compute_employment_evidence(candidate, company, role, location)

    final_score = round(
        min(
            1.0,
            (person_match_score * 0.60)
            + (employment_evidence_score * 0.30)
            + (candidate.discovery_score * 0.10),
        ),
        4,
    )

    if final_score >= 0.80:
        employment_status = "matched"
        review_flag = "auto"
        review_reason = ""
        match_status = "matched"
    elif final_score >= 0.55:
        employment_status = "possible_match"
        review_flag = "manual_review"
        review_reason = "needs_human_check"
        match_status = "possible_match"
    elif person_match_score >= 0.45:
        employment_status = "profile_found_no_employer"
        review_flag = "manual_review"
        review_reason = "weak_employment_evidence"
        match_status = "profile_found_no_employer"
    else:
        employment_status = "not_found"
        review_flag = "manual_review"
        review_reason = "weak_person_match"
        match_status = "not_found"

    return MatchResult(
        matched_name=student.full_name,
        source_url=candidate.url,
        source_title=candidate.title,
        page_type=candidate.page_type,
        person_match_score=person_match_score,
        employment_evidence_score=employment_evidence_score,
        final_score=final_score,
        company=company,
        role=role,
        location=location,
        evidence=evidence,
        confidence=final_score,
        employment_status=employment_status,
        review_flag=review_flag,
        review_reason=review_reason,
        match_status=match_status,
    )


def select_best_match(student: Student, candidates: list[CandidatePage]) -> MatchResult:
    if not candidates:
        return MatchResult()

    scored = [match_candidate(student, candidate) for candidate in candidates]
    scored.sort(key=lambda item: item.final_score, reverse=True)
    return scored[0]
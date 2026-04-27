from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional


@dataclass
class Student:
    first_name: str
    last_name: str
    full_name: str
    university: str = ""
    course: str = ""
    graduation_year: str = ""
    student_id: str = ""


@dataclass
class CandidatePage:
    url: str
    title: str = ""
    snippet: str = ""
    text: str = ""
    final_url: Optional[str] = None
    page_type: str = "generic"
    discovery_source: str = "unknown"
    discovery_score: float = 0.0
    status_code: int = 0
    content_type: str = ""


@dataclass
class MatchResult:
    person_match_score: float
    employment_evidence_score: float
    final_score: float
    page_type: str
    keep: bool
    review_flag: bool
    review_reason: str
    matched_signals: List[str] = field(default_factory=list)
    evidence_snippets: List[str] = field(default_factory=list)
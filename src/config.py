from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Settings:
    input_file: Path = Path("data/Trial_1.xlsx")
    output_file: Path = Path("outputs/enriched.xlsx")

    use_llm: bool = True
    ollama_model: str = "gemma3:1b"

    request_timeout: int = 20
    min_text_length: int = 120
    max_text_for_llm: int = 6000

    max_candidate_urls: int = 8
    max_candidates_to_extract: int = 5

    min_person_match_score: float = 0.50
    min_employment_evidence_score: float = 0.15
    min_final_score_for_profile: float = 0.50
    min_final_score_for_employment: float = 0.65
    min_llm_confidence_for_accept: float = 0.40


SETTINGS = Settings()
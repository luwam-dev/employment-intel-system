from __future__ import annotations

import shutil
import tempfile
from pathlib import Path
from typing import Any

import pandas as pd
from fastapi import FastAPI, File, Form, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel

from src.discovery import Student, discover_candidates
import src.matcher as matcher_module


app = FastAPI(title="Employment Intel API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

PROJECT_ROOT = Path(__file__).resolve().parent.parent
UPLOADS_DIR = PROJECT_ROOT / "uploads"
OUTPUTS_DIR = PROJECT_ROOT / "outputs"

UPLOADS_DIR.mkdir(parents=True, exist_ok=True)
OUTPUTS_DIR.mkdir(parents=True, exist_ok=True)

OUTPUT_TEXT_COLUMNS = [
    "matched_name",
    "source_url",
    "source_title",
    "company",
    "role",
    "location",
    "match_status",
]

OUTPUT_NUMERIC_COLUMNS = [
    "person_match_score",
    "employment_evidence_score",
    "final_score",
]


class PersonRequest(BaseModel):
    first_name: str
    last_name: str
    university: str | None = "Brunel University London"


def clean_string(value: Any) -> str:
    if value is None:
        return ""
    try:
        if pd.isna(value):
            return ""
    except TypeError:
        pass
    return str(value).strip()


def normalize_col_name(name: str) -> str:
    return (
        str(name)
        .strip()
        .lower()
        .replace("\n", " ")
        .replace("-", " ")
        .replace("_", " ")
    )


def build_column_lookup(df: pd.DataFrame) -> dict[str, str]:
    lookup: dict[str, str] = {}
    for col in df.columns:
        lookup[normalize_col_name(col)] = col
    return lookup


def find_first_matching_column(df: pd.DataFrame, candidates: list[str]) -> str | None:
    lookup = build_column_lookup(df)

    for candidate in candidates:
        key = normalize_col_name(candidate)
        if key in lookup:
            return lookup[key]

    for normalized, original in lookup.items():
        for candidate in candidates:
            candidate_key = normalize_col_name(candidate)
            if candidate_key in normalized or normalized in candidate_key:
                return original

    return None


def get_row_value(row: pd.Series, column_name: str | None) -> str:
    if not column_name:
        return ""
    if column_name not in row.index:
        return ""
    return clean_string(row[column_name])


def split_full_name(full_name: str) -> tuple[str, str]:
    parts = [part for part in full_name.split() if part.strip()]
    if not parts:
        return "", ""
    if len(parts) == 1:
        return parts[0], ""
    return parts[0], parts[-1]


def detect_columns(df: pd.DataFrame) -> dict[str, str | None]:
    return {
        "full_name": find_first_matching_column(
            df,
            ["full name", "student name", "name", "candidate name"],
        ),
        "first_name": find_first_matching_column(
            df,
            ["first name", "firstname", "given name", "forename"],
        ),
        "last_name": find_first_matching_column(
            df,
            ["last name", "lastname", "surname", "family name"],
        ),
        "course": find_first_matching_column(
            df,
            ["course", "programme", "program", "degree"],
        ),
        "graduation_year": find_first_matching_column(
            df,
            ["graduation year", "grad year", "year", "completion year"],
        ),
        "student_id": find_first_matching_column(
            df,
            ["student id", "id", "student number"],
        ),
        "university": find_first_matching_column(
            df,
            ["university", "institution", "school"],
        ),
    }


def build_student_from_row(
    row: pd.Series,
    row_index: int,
    detected: dict[str, str | None],
    default_university: str,
) -> Student:
    full_name = get_row_value(row, detected["full_name"])
    first_name = get_row_value(row, detected["first_name"])
    last_name = get_row_value(row, detected["last_name"])

    if full_name and not (first_name or last_name):
        first_name, last_name = split_full_name(full_name)

    if not full_name and (first_name or last_name):
        full_name = " ".join(part for part in [first_name, last_name] if part).strip()

    if not full_name:
        full_name = f"Row {row_index + 1}"

    course = get_row_value(row, detected["course"])
    graduation_year = get_row_value(row, detected["graduation_year"])
    student_id = get_row_value(row, detected["student_id"])
    university = get_row_value(row, detected["university"]) or default_university

    return Student(
        first_name=first_name,
        last_name=last_name,
        full_name=full_name,
        course=course,
        graduation_year=graduation_year,
        student_id=student_id,
        university=university,
    )


def ensure_output_columns(df: pd.DataFrame) -> pd.DataFrame:
    for col in OUTPUT_TEXT_COLUMNS:
        if col not in df.columns:
            df[col] = ""
        df[col] = df[col].astype("object")

    for col in OUTPUT_NUMERIC_COLUMNS:
        if col not in df.columns:
            df[col] = None
        df[col] = df[col].astype("object")

    return df


def safe_getattr(obj: Any, attr: str, default: Any = "") -> Any:
    return getattr(obj, attr, default) if obj is not None else default


def call_matcher(student: Student, candidates: list[Any]) -> Any:
    possible_function_names = [
        "find_best_match",
        "match_best_candidate",
        "match_candidates",
        "match_student_to_candidates",
        "select_best_match",
    ]

    for fn_name in possible_function_names:
        fn = getattr(matcher_module, fn_name, None)
        if callable(fn):
            result = fn(student, candidates)

            if isinstance(result, list):
                if not result:
                    return None
                return max(result, key=lambda item: safe_getattr(item, "final_score", 0.0))

            if isinstance(result, tuple):
                if not result:
                    return None
                return result[0]

            return result

    raise AttributeError("No supported matcher function found in src.matcher")


def status_from_scores(final_score: float | None) -> str:
    if final_score is None:
        return "no_match"
    if final_score >= 0.80:
        return "matched"
    if final_score >= 0.55:
        return "possible_match"
    return "no_match"


def result_to_dict(student: Student, best_match: Any) -> dict[str, Any]:
    person_score_raw = safe_getattr(best_match, "person_match_score", None)
    employment_score_raw = safe_getattr(best_match, "employment_evidence_score", None)
    final_score_raw = safe_getattr(best_match, "final_score", None)

    person_score = round(float(person_score_raw), 4) if person_score_raw not in ("", None) else None
    employment_score = (
        round(float(employment_score_raw), 4) if employment_score_raw not in ("", None) else None
    )
    final_score = round(float(final_score_raw), 4) if final_score_raw not in ("", None) else None

    matched_name = clean_string(safe_getattr(best_match, "matched_name", student.full_name))
    source_url = clean_string(safe_getattr(best_match, "source_url", safe_getattr(best_match, "url", "")))
    source_title = clean_string(safe_getattr(best_match, "source_title", safe_getattr(best_match, "title", "")))
    company = clean_string(safe_getattr(best_match, "company", ""))
    role = clean_string(safe_getattr(best_match, "role", ""))
    location = clean_string(safe_getattr(best_match, "location", ""))
    match_status = clean_string(safe_getattr(best_match, "employment_status", "")) or status_from_scores(final_score)

    return {
        "input_name": student.full_name,
        "first_name": student.first_name,
        "last_name": student.last_name,
        "university": student.university,
        "matched_name": matched_name,
        "source_url": source_url,
        "source_title": source_title,
        "company": company,
        "role": role,
        "location": location,
        "match_status": match_status,
        "person_match_score": person_score,
        "employment_evidence_score": employment_score,
        "final_score": final_score,
    }


def no_match_dict(student: Student) -> dict[str, Any]:
    return {
        "input_name": student.full_name,
        "first_name": student.first_name,
        "last_name": student.last_name,
        "university": student.university,
        "matched_name": "",
        "source_url": "",
        "source_title": "",
        "company": "",
        "role": "",
        "location": "",
        "match_status": "no_match",
        "person_match_score": None,
        "employment_evidence_score": None,
        "final_score": None,
    }


def apply_result_to_dataframe(df: pd.DataFrame, idx: int, result: dict[str, Any]) -> None:
    df.at[idx, "matched_name"] = result["matched_name"]
    df.at[idx, "source_url"] = result["source_url"]
    df.at[idx, "source_title"] = result["source_title"]
    df.at[idx, "company"] = result["company"]
    df.at[idx, "role"] = result["role"]
    df.at[idx, "location"] = result["location"]
    df.at[idx, "match_status"] = result["match_status"]
    df.at[idx, "person_match_score"] = result["person_match_score"]
    df.at[idx, "employment_evidence_score"] = result["employment_evidence_score"]
    df.at[idx, "final_score"] = result["final_score"]


def process_student(student: Student) -> dict[str, Any]:
    if not clean_string(student.full_name) or student.full_name.startswith("Row "):
        return no_match_dict(student)

    candidates = discover_candidates(
        student,
        max_search_results=5,
        max_candidates=8,
        sleep_seconds=0.2,
    )

    if not candidates:
        return no_match_dict(student)

    best_match = call_matcher(student, candidates)
    if best_match is None:
        return no_match_dict(student)

    return result_to_dict(student, best_match)


@app.get("/api/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/api/enrich-person")
def enrich_person(payload: PersonRequest) -> dict[str, Any]:
    first_name = clean_string(payload.first_name)
    last_name = clean_string(payload.last_name)
    full_name = " ".join(part for part in [first_name, last_name] if part).strip()

    student = Student(
        first_name=first_name,
        last_name=last_name,
        full_name=full_name,
        university=clean_string(payload.university) or "Brunel University London",
    )

    return process_student(student)


@app.post("/api/enrich-xlsx")
async def enrich_xlsx(
    file: UploadFile = File(...),
    university: str = Form("Brunel University London"),
) -> dict[str, Any]:
    input_name = Path(file.filename or "uploaded.xlsx").name
    input_path = UPLOADS_DIR / input_name

    with input_path.open("wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    df = pd.read_excel(input_path, dtype=object)
    df = ensure_output_columns(df)

    detected = detect_columns(df)
    results: list[dict[str, Any]] = []

    for idx, row in df.iterrows():
        student = build_student_from_row(
            row=row,
            row_index=idx,
            detected=detected,
            default_university=clean_string(university) or "Brunel University London",
        )
        result = process_student(student)
        apply_result_to_dataframe(df, idx, result)
        results.append(result)

    output_name = f"enriched_{input_name}"
    output_path = OUTPUTS_DIR / output_name
    df.to_excel(output_path, index=False)

    matches_found = sum(1 for row in results if row["match_status"] == "matched")
    review_count = sum(1 for row in results if row["match_status"] == "possible_match")
    no_match_count = sum(1 for row in results if row["match_status"] == "no_match")

    return {
        "type": "file",
        "rows_processed": len(results),
        "matches_found": matches_found,
        "review_count": review_count,
        "no_match_count": no_match_count,
        "output_name": output_name,
        "download_url": f"http://127.0.0.1:8000/downloads/{output_name}",
        "rows": results,
        "detected_columns": detected,
    }


@app.get("/downloads/{filename}")
def download_file(filename: str):
    file_path = OUTPUTS_DIR / filename
    if not file_path.exists():
        return {"error": "File not found"}

    return FileResponse(
        path=file_path,
        filename=filename,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )
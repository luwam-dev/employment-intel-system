from __future__ import annotations

import os
import sys
import traceback
from pathlib import Path
from typing import Any, Optional

import pandas as pd

from discovery import Student, discover_candidates
import matcher as matcher_module


PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_INPUT_FILE = PROJECT_ROOT / "data" / "Trial_1.xlsx"
DEFAULT_OUTPUT_FILE = PROJECT_ROOT / "outputs" / "enriched.xlsx"


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


def clean_string(value: Any) -> str:
    if value is None:
        return ""
    if pd.isna(value):
        return ""
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


def find_first_matching_column(
    df: pd.DataFrame,
    candidates: list[str],
) -> Optional[str]:
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


def get_row_value(row: pd.Series, column_name: Optional[str]) -> str:
    if not column_name:
        return ""
    if column_name not in row.index:
        return ""
    return clean_string(row[column_name])


def split_full_name(full_name: str) -> tuple[str, str]:
    parts = [p for p in full_name.split() if p.strip()]
    if not parts:
        return "", ""
    if len(parts) == 1:
        return parts[0], ""
    return parts[0], parts[-1]


def detect_columns(df: pd.DataFrame) -> dict[str, Optional[str]]:
    return {
        "full_name": find_first_matching_column(
            df,
            [
                "full name",
                "student name",
                "name",
                "candidate name",
            ],
        ),
        "first_name": find_first_matching_column(
            df,
            [
                "first name",
                "firstname",
                "given name",
                "forename",
            ],
        ),
        "last_name": find_first_matching_column(
            df,
            [
                "last name",
                "lastname",
                "surname",
                "family name",
            ],
        ),
        "course": find_first_matching_column(
            df,
            [
                "course",
                "programme",
                "program",
                "degree",
            ],
        ),
        "graduation_year": find_first_matching_column(
            df,
            [
                "graduation year",
                "grad year",
                "year",
                "completion year",
            ],
        ),
        "student_id": find_first_matching_column(
            df,
            [
                "student id",
                "id",
                "student number",
            ],
        ),
        "university": find_first_matching_column(
            df,
            [
                "university",
                "institution",
                "school",
            ],
        ),
    }


def build_student_from_row(
    row: pd.Series,
    row_index: int,
    detected: dict[str, Optional[str]],
) -> Student:
    full_name = get_row_value(row, detected["full_name"])
    first_name = get_row_value(row, detected["first_name"])
    last_name = get_row_value(row, detected["last_name"])

    if full_name and not (first_name or last_name):
        first_name, last_name = split_full_name(full_name)

    if not full_name and (first_name or last_name):
        full_name = " ".join(part for part in [first_name, last_name] if part).strip()

    course = get_row_value(row, detected["course"])
    graduation_year = get_row_value(row, detected["graduation_year"])
    student_id = get_row_value(row, detected["student_id"])

    if not full_name:
        full_name = f"Row {row_index + 1}"

    return Student(
        first_name=first_name,
        last_name=last_name,
        full_name=full_name,
        course=course,
        graduation_year=graduation_year,
        student_id=student_id,
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
                return max(result, key=lambda x: safe_getattr(x, "final_score", 0.0))

            if isinstance(result, tuple):
                if len(result) == 0:
                    return None
                if len(result) == 1:
                    return result[0]
                if hasattr(result[0], "final_score"):
                    return result[0]

            return result

    raise AttributeError(
        "No supported matcher function found in matcher.py. "
        "Expected one of: find_best_match, match_best_candidate, "
        "match_candidates, match_student_to_candidates, select_best_match"
    )


def update_row_with_match(df: pd.DataFrame, idx: int, best_match: Any) -> None:
    df.at[idx, "matched_name"] = clean_string(
        safe_getattr(best_match, "matched_name", safe_getattr(best_match, "name", ""))
    )
    df.at[idx, "source_url"] = clean_string(
        safe_getattr(best_match, "source_url", safe_getattr(best_match, "url", ""))
    )
    df.at[idx, "source_title"] = clean_string(
        safe_getattr(best_match, "source_title", safe_getattr(best_match, "title", ""))
    )
    df.at[idx, "company"] = clean_string(safe_getattr(best_match, "company", ""))
    df.at[idx, "role"] = clean_string(safe_getattr(best_match, "role", ""))
    df.at[idx, "location"] = clean_string(safe_getattr(best_match, "location", ""))

    person_score = safe_getattr(best_match, "person_match_score", None)
    employment_score = safe_getattr(best_match, "employment_evidence_score", None)
    final_score = safe_getattr(best_match, "final_score", None)

    df.at[idx, "person_match_score"] = (
        round(float(person_score), 4) if person_score not in ("", None) else None
    )
    df.at[idx, "employment_evidence_score"] = (
        round(float(employment_score), 4) if employment_score not in ("", None) else None
    )
    df.at[idx, "final_score"] = (
        round(float(final_score), 4) if final_score not in ("", None) else None
    )

    df.at[idx, "match_status"] = "matched"


def update_row_no_match(df: pd.DataFrame, idx: int, reason: str) -> None:
    df.at[idx, "matched_name"] = ""
    df.at[idx, "source_url"] = ""
    df.at[idx, "source_title"] = ""
    df.at[idx, "company"] = ""
    df.at[idx, "role"] = ""
    df.at[idx, "location"] = ""
    df.at[idx, "person_match_score"] = None
    df.at[idx, "employment_evidence_score"] = None
    df.at[idx, "final_score"] = None
    df.at[idx, "match_status"] = reason


def save_progress(df: pd.DataFrame, output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    df.to_excel(output_path, index=False)
    print(f"   Saved progress to {output_path}")


def get_input_file() -> Path:
    if len(sys.argv) > 1:
        return Path(sys.argv[1]).resolve()

    env_input = os.getenv("INPUT_XLSX")
    if env_input:
        return Path(env_input).resolve()

    return DEFAULT_INPUT_FILE


def main() -> None:
    print("🚀 Starting Employment Intel System...\n")

    input_file = get_input_file()
    output_file = DEFAULT_OUTPUT_FILE

    print(f"Using input file: {input_file}")

    if not input_file.exists():
        raise FileNotFoundError(f"Input file not found: {input_file}")

    df = pd.read_excel(input_file, dtype=object)
    df = ensure_output_columns(df)

    detected = detect_columns(df)

    print("Detected columns:")
    for key, value in detected.items():
        print(f"   {key}: {value}")
    print()

    students: list[tuple[int, Student]] = []
    for idx, row in df.iterrows():
        student = build_student_from_row(row, idx, detected)
        students.append((idx, student))

    print(f"Loaded {len(students)} students.\n")

    for item_number, (idx, student) in enumerate(students, start=1):
        try:
            print(f"🔍 Processing {item_number}: {student.full_name}")

            if not clean_string(student.full_name) or student.full_name.startswith("Row "):
                print("   Skipped: no valid student name found in input row")
                update_row_no_match(df, idx, "missing_name")
                save_progress(df, output_file)
                print()
                continue

            candidates = discover_candidates(
                student,
                max_search_results=5,
                max_candidates=8,
                sleep_seconds=0.2,
            )

            print(f"Loaded {len(candidates)} candidate pages for {student.full_name}")

            if not candidates:
                update_row_no_match(df, idx, "no_candidates")
                save_progress(df, output_file)
                print()
                continue

            best_match = call_matcher(student, candidates)

            if best_match is None:
                print("   No best match returned by matcher")
                update_row_no_match(df, idx, "no_match")
                save_progress(df, output_file)
                print()
                continue

            print(
                f"   best final_score={safe_getattr(best_match, 'final_score', 0.0):.4f} "
                f"person_match_score={safe_getattr(best_match, 'person_match_score', 0.0):.4f} "
                f"employment_evidence_score={safe_getattr(best_match, 'employment_evidence_score', 0.0):.4f}"
            )
            print(f"   company={safe_getattr(best_match, 'company', '')}")
            print(f"   role={safe_getattr(best_match, 'role', '')}")
            print(f"   location={safe_getattr(best_match, 'location', '')}")
            print(f"   source_url={safe_getattr(best_match, 'source_url', safe_getattr(best_match, 'url', ''))}")

            update_row_with_match(df, idx, best_match)
            save_progress(df, output_file)
            print()

        except Exception as exc:
            print(f"   Error processing {student.full_name}: {exc}")
            traceback.print_exc()
            update_row_no_match(df, idx, "error")
            save_progress(df, output_file)
            print()

    print(f"✅ Done! Results saved to {output_file}")


if __name__ == "__main__":
    main()
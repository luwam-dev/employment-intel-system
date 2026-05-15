from __future__ import annotations

from dotenv import load_dotenv
load_dotenv()

from dataclasses import dataclass
from typing import Iterable, List, Optional
from urllib.parse import parse_qs, unquote, urlparse
import os
import re
import time

import requests
from bs4 import BeautifulSoup


BRAVE_WEB_SEARCH_URL = "https://api.search.brave.com/res/v1/web/search"


@dataclass
class Student:
    first_name: str
    last_name: str
    full_name: str
    course: str = ""
    graduation_year: str = ""
    student_id: str = ""
    university: str = ""


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


# ---------------- UTIL ---------------- #

def clean_text(v: str) -> str:
    return re.sub(r"\s+", " ", (v or "").strip())


def normalize_text(v: str) -> str:
    return clean_text(v).lower()


def compact_name(v: str) -> str:
    return re.sub(r"[^a-zA-Z0-9]+", "", v.lower())


def unique_preserve_order(values: Iterable[str]) -> List[str]:
    seen = set()
    out = []
    for v in values:
        v = clean_text(v)
        if v and v not in seen:
            seen.add(v)
            out.append(v)
    return out


# ---------------- QUERY FIX (CRITICAL) ---------------- #

def build_search_queries(student: Student) -> List[str]:
    first = clean_text(student.first_name)
    last = clean_text(student.last_name)
    full = clean_text(student.full_name)
    compact = compact_name(full)

    queries = [
        # 🔥 RELAXED FIRST
        f"{first} {last} linkedin",
        f'"{first} {last}" linkedin',
        f"{first} {last} github",

        # medium
        f"{full} linkedin",

        # strict
        f'site:linkedin.com/in "{full}"',
        f'site:linkedin.com/in "{first} {last}"',

        # fallback
        f"{compact} linkedin",
    ]

    return unique_preserve_order(queries[:8])


# ---------------- FILTER ---------------- #

def is_bad(url: str, title: str, snippet: str) -> bool:
    text = f"{url} {title} {snippet}".lower()

    if "linkedin.com/pub/dir" in text:
        return True
    if any(x in text for x in ["login", "sign in", "directory", "people search"]):
        return True

    return False


def classify(url: str) -> str:
    url = url.lower()
    if "linkedin.com/in/" in url:
        return "linkedin"
    if "github.com/" in url:
        return "github"
    return "generic"


# ---------------- RANKING (SIMPLIFIED) ---------------- #

def rank(student: Student, c: CandidatePage) -> float:
    blob = normalize_text(f"{c.title} {c.snippet} {c.url}")

    score = 0

    if normalize_text(student.full_name) in blob:
        score += 1.5

    if student.first_name.lower() in blob:
        score += 0.3

    if student.last_name.lower() in blob:
        score += 0.5

    if "linkedin.com/in/" in c.url:
        score += 1.0

    if "github.com/" in c.url:
        score += 0.5

    return score


# ---------------- SEARCH ---------------- #

def search_brave(query: str, count: int = 10) -> List[CandidatePage]:
    key = os.getenv("BRAVE_SEARCH_API_KEY", "").strip()
    if not key:
        raise RuntimeError("Missing BRAVE_SEARCH_API_KEY")

    r = requests.get(
        BRAVE_WEB_SEARCH_URL,
        params={"q": query, "count": count},
        headers={"X-Subscription-Token": key},
        timeout=20,
    )
    r.raise_for_status()

    data = r.json()
    out = []

    for item in data.get("web", {}).get("results", []):
        url = item.get("url", "")
        title = item.get("title", "")
        snippet = item.get("description", "")

        if not url or is_bad(url, title, snippet):
            continue

        out.append(
            CandidatePage(
                url=url,
                title=title,
                snippet=snippet,
                page_type=classify(url),
                discovery_source="brave",
                discovery_score=0.5,
            )
        )

    return out


# ---------------- MAIN ---------------- #

def discover_candidates(
    student: Student,
    max_search_results: int = 8,
    max_candidates: int = 10,
    sleep_seconds: float = 0.2,
) -> List[CandidatePage]:

    queries = build_search_queries(student)
    print(f"   Queries: {len(queries)}")

    all_candidates: List[CandidatePage] = []

    for q in queries:
        try:
            print(f"   🔎 {q}")
            results = search_brave(q, count=max_search_results)

            print(f"   hits: {len(results)}")

            all_candidates.extend(results)
            time.sleep(sleep_seconds)

        except Exception as e:
            print(f"   search error: {e}")

    # dedupe
    seen = {}
    for c in all_candidates:
        if c.url not in seen:
            seen[c.url] = c

    candidates = list(seen.values())

    # rank
    for c in candidates:
        c.discovery_score = rank(student, c)

    candidates.sort(key=lambda x: x.discovery_score, reverse=True)

    # 🔥 IMPORTANT FIX: LOWER THRESHOLD
    candidates = [c for c in candidates if c.discovery_score > 0.5][:max_candidates]

    print(f"   FINAL: {len(candidates)}")

    for i, c in enumerate(candidates, 1):
        print(f"   [{i}] {c.discovery_score:.2f} {c.url}")

    return candidates
from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, List, Optional
import os
import re
import time

import requests
from bs4 import BeautifulSoup


DEFAULT_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/123.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "en-GB,en;q=0.9",
}


BLOCKED_HOST_KEYWORDS = {
    "login",
    "signin",
    "account",
    "accounts.google.com",
    "webcache",
    "translate.google",
}


ROLE_HINTS = {
    "software engineer",
    "engineer",
    "developer",
    "data analyst",
    "data scientist",
    "analyst",
    "consultant",
    "manager",
    "researcher",
    "lecturer",
    "scientist",
    "intern",
}


UNWANTED_URL_HINTS = {
    "/pub/dir/",
    "/posts/",
    "/pulse/",
    "/advice/",
    "/jobs/",
    "/feed/",
    "/school/",
    "/company/",
}


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


def normalize_text(value: str) -> str:
    return re.sub(r"\s+", " ", (value or "").strip()).lower()


def slugify_name(value: str) -> str:
    cleaned = re.sub(r"[^a-zA-Z0-9]+", "-", value.strip().lower())
    return cleaned.strip("-")


def compact_name(value: str) -> str:
    return re.sub(r"[^a-zA-Z0-9]+", "", value.strip().lower())


def unique_preserve_order(values: Iterable[str]) -> List[str]:
    seen = set()
    ordered: List[str] = []
    for value in values:
        if not value:
            continue
        if value in seen:
            continue
        seen.add(value)
        ordered.append(value)
    return ordered


def get_name_variants(student: Student) -> List[str]:
    full_name = student.full_name.strip()
    first = student.first_name.strip()
    last = student.last_name.strip()

    variants = [
        compact_name(full_name),
        slugify_name(full_name),
    ]

    if first and last:
        variants.extend(
            [
                compact_name(f"{first}{last}"),
                slugify_name(f"{first} {last}"),
            ]
        )

    if len(last) >= 5:
        variants.extend(
            [
                compact_name(last),
                slugify_name(last),
            ]
        )

    return unique_preserve_order([v for v in variants if v])


def build_search_queries(student: Student) -> List[str]:
    full_name = student.full_name.strip()
    compact_full = compact_name(full_name)
    university = (student.university or "Brunel University London").strip()

    queries = [
        f'"{full_name}" linkedin',
        f'"{full_name}" "{university}"',
        f'"{full_name}" github',
        f'"{compact_full}" linkedin',
    ]

    if student.course:
        queries.append(f'"{full_name}" "{student.course}"')

    return unique_preserve_order(queries[:4])


def guess_profile_urls(student: Student) -> List[CandidatePage]:
    variants = get_name_variants(student)
    pages: List[CandidatePage] = []

    for variant in variants:
        pages.append(
            CandidatePage(
                url=f"https://github.com/{variant}",
                page_type="github_profile",
                discovery_source="heuristic_guess",
                discovery_score=0.20,
            )
        )

    brunel_slug = slugify_name(student.full_name)
    pages.append(
        CandidatePage(
            url=f"https://www.brunel.ac.uk/people/{brunel_slug}",
            page_type="brunel_page",
            discovery_source="heuristic_guess",
            discovery_score=0.28,
        )
    )

    return deduplicate_candidates(pages)


def is_blocked_url(url: str) -> bool:
    lowered = (url or "").lower()
    return any(token in lowered for token in BLOCKED_HOST_KEYWORDS)


def is_unwanted_search_result(url: str, title: str = "", snippet: str = "") -> bool:
    haystack = f"{url} {title} {snippet}".lower()

    if any(token in url.lower() for token in UNWANTED_URL_HINTS):
        return True

    noisy_patterns = [
        r"\b\d+\+\b",
        r"\bprofiles\b",
        r"\bprofile(s)?\b",
        r"\bpeople\b",
        r"\bresults for\b",
    ]

    if "linkedin.com" in haystack:
        for pat in noisy_patterns:
            if re.search(pat, haystack):
                return True

    return False


def classify_page_type(url: str, title: str = "", snippet: str = "") -> str:
    haystack = f"{url} {title} {snippet}".lower()

    if "linkedin.com/in/" in haystack or "linkedin.com/pub/" in haystack:
        return "linkedin_profile"
    if "github.com/" in haystack:
        return "github_profile"
    if "sites.google.com" in haystack:
        return "google_site"
    if "brunel.ac.uk" in haystack:
        return "brunel_page"
    if any(hint in haystack for hint in {"team", "staff", "people", "bio", "profile"}):
        return "people_page"
    if "portfolio" in haystack:
        return "portfolio"
    return "generic"


def rank_candidate(student: Student, candidate: CandidatePage) -> float:
    score = candidate.discovery_score

    full_name = normalize_text(student.full_name)
    first_name = normalize_text(student.first_name)
    last_name = normalize_text(student.last_name)
    university = normalize_text(student.university or "Brunel University London")

    title = normalize_text(candidate.title)
    snippet = normalize_text(candidate.snippet)
    url = normalize_text(candidate.url)
    blob = f"{title} {snippet} {url}"

    if full_name and full_name in blob:
        score += 1.20

    if first_name and first_name in blob:
        score += 0.20

    if last_name and last_name in blob:
        score += 0.25

    if first_name and last_name and first_name in blob and last_name in blob:
        score += 0.35

    if university and university in blob:
        score += 0.60
    elif "brunel university" in blob:
        score += 0.45

    if any(role in blob for role in ROLE_HINTS):
        score += 0.25

    if "experience:" in blob:
        score += 0.35

    if "linkedin.com/in/" in url:
        score += 0.60
    elif "linkedin.com/pub/" in url:
        score += 0.15

    if "github.com/" in url:
        score += 0.10

    if "brunel.ac.uk/people/" in url:
        score += 0.35

    if candidate.discovery_source == "heuristic_guess":
        score -= 0.08

    if is_blocked_url(candidate.url):
        score -= 0.50

    if is_unwanted_search_result(candidate.url, candidate.title, candidate.snippet):
        score -= 0.80

    return round(max(score, 0.0), 4)


def deduplicate_candidates(candidates: Iterable[CandidatePage]) -> List[CandidatePage]:
    best_by_url: dict[str, CandidatePage] = {}

    for candidate in candidates:
        key = candidate.url.strip()
        existing = best_by_url.get(key)
        if existing is None or candidate.discovery_score > existing.discovery_score:
            best_by_url[key] = candidate

    return list(best_by_url.values())


def search_duckduckgo(query: str, timeout: int = 20) -> List[CandidatePage]:
    url = "https://html.duckduckgo.com/html/"
    response = requests.post(
        url,
        data={"q": query},
        headers=DEFAULT_HEADERS,
        timeout=timeout,
    )
    response.raise_for_status()

    soup = BeautifulSoup(response.text, "html.parser")
    results: List[CandidatePage] = []

    for result in soup.select(".result"):
        title_node = result.select_one(".result__title")
        link_node = result.select_one(".result__url") or result.select_one(".result__title a")
        snippet_node = result.select_one(".result__snippet")

        href = ""
        if link_node and link_node.has_attr("href"):
            href = link_node["href"].strip()

        if not href:
            anchor = result.select_one("a[href]")
            if anchor and anchor.has_attr("href"):
                href = anchor["href"].strip()

        title = title_node.get_text(" ", strip=True) if title_node else ""
        snippet = snippet_node.get_text(" ", strip=True) if snippet_node else ""

        if not href or is_unwanted_search_result(href, title, snippet):
            continue

        results.append(
            CandidatePage(
                url=href,
                title=title,
                snippet=snippet,
                page_type=classify_page_type(href, title, snippet),
                discovery_source="search_result",
                discovery_score=0.65,
            )
        )

    return results


def search_serpapi(query: str, timeout: int = 30) -> List[CandidatePage]:
    api_key = os.getenv("SERPAPI_API_KEY", "").strip()
    if not api_key:
        return []

    response = requests.get(
        "https://serpapi.com/search.json",
        params={
            "engine": "google",
            "q": query,
            "api_key": api_key,
            "num": 10,
            "google_domain": "google.com",
            "hl": "en",
            "gl": "uk",
        },
        headers=DEFAULT_HEADERS,
        timeout=timeout,
    )
    response.raise_for_status()
    payload = response.json()

    results: List[CandidatePage] = []
    for item in payload.get("organic_results", []):
        url = (item.get("link") or "").strip()
        title = (item.get("title") or "").strip()
        snippet = (item.get("snippet") or "").strip()

        if not url:
            continue
        if is_unwanted_search_result(url, title, snippet):
            continue

        results.append(
            CandidatePage(
                url=url,
                title=title,
                snippet=snippet,
                page_type=classify_page_type(url, title, snippet),
                discovery_source="serpapi",
                discovery_score=0.90,
            )
        )

    return results


def discover_candidates(
    student: Student,
    max_search_results: int = 5,
    max_candidates: int = 8,
    sleep_seconds: float = 0.5,
) -> List[CandidatePage]:
    candidates: List[CandidatePage] = []
    queries = build_search_queries(student)
    print(f"   Search queries: {len(queries)}")

    use_serpapi = bool(os.getenv("SERPAPI_API_KEY", "").strip())

    for query in queries:
        try:
            if use_serpapi:
                print(f"   SerpApi query: {query}")
                results = search_serpapi(query)
            else:
                print(f"   DDG query: {query}")
                results = search_duckduckgo(query)

            if results:
                print(f"   Search hits: {len(results)}")

            candidates.extend(results[:max_search_results])
            time.sleep(sleep_seconds)

        except requests.HTTPError as exc:
            print(f"   Search error for query={query!r}: {exc}")
        except requests.RequestException as exc:
            print(f"   Search request failed for query={query!r}: {exc}")

    heuristic_candidates = guess_profile_urls(student)
    print(f"   Heuristic guesses: {len(heuristic_candidates)}")
    candidates.extend(heuristic_candidates)

    candidates = deduplicate_candidates(candidates)

    for candidate in candidates:
        candidate.page_type = classify_page_type(candidate.url, candidate.title, candidate.snippet)
        candidate.discovery_score = rank_candidate(student, candidate)

    candidates.sort(key=lambda item: item.discovery_score, reverse=True)
    candidates = [c for c in candidates if c.discovery_score > 0][:max_candidates]

    print(f"   Final candidate pages: {len(candidates)}")
    for index, candidate in enumerate(candidates, start=1):
        print(
            f"   [{index}] score={candidate.discovery_score:.3f} "
            f"source={candidate.discovery_source} type={candidate.page_type} url={candidate.url}"
        )
        if candidate.title:
            print(f"       title={candidate.title}")
        if candidate.snippet:
            print(f"       snippet={candidate.snippet[:180]}")

    return candidates
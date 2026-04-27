from __future__ import annotations

import re

import requests
from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
    "Accept-Language": "en-GB,en;q=0.9",
    "Cache-Control": "no-cache",
    "Pragma": "no-cache",
}

TIMEOUT = 20

REMOVE_TAGS = {"script", "style", "noscript", "svg", "iframe"}

REMOVE_SELECTORS = (
    "[role='navigation']",
    "[role='banner']",
    "[role='contentinfo']",
    ".navbar",
    ".nav",
    ".menu",
    ".footer",
    ".header",
    ".sidebar",
    ".cookie",
    ".cookies",
    ".consent",
    ".popup",
    ".modal",
)

BAD_URL_HINTS = (
    "/login",
    "return_to=",
    "accounts.google.com",
    "ServiceLogin",
    "signin/identifier",
)

BAD_TEXT_HINTS = (
    "sign in",
    "log in",
    "login",
    "page not found",
    "access denied",
    "enable javascript",
)


def _normalize_spaces(value: str) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()


def _clean_text_from_html(raw_html: str, min_length: int = 80) -> str:
    if not raw_html.strip():
        return ""

    soup = BeautifulSoup(raw_html, "html.parser")

    title = soup.title.get_text(" ", strip=True) if soup.title else ""
    print(f"   page_title={title!r}")

    for tag in soup(REMOVE_TAGS):
        tag.decompose()

    for selector in REMOVE_SELECTORS:
        for node in soup.select(selector):
            node.decompose()

    main_candidates = [
        soup.find("main"),
        soup.find("article"),
        soup.find(attrs={"role": "main"}),
        soup.find(id="content"),
        soup.find(id="main"),
    ]
    main_node = next((node for node in main_candidates if node is not None), soup.body or soup)

    text = _normalize_spaces(main_node.get_text(separator=" ", strip=True))
    if not text:
        return ""

    lowered = text.lower()
    if any(hint in lowered for hint in BAD_TEXT_HINTS):
        return ""

    boilerplate = {
        "google sites",
        "report abuse",
        "page details",
        "terms of service",
        "privacy policy",
        "skip to main content",
    }

    parts = []
    for chunk in re.split(r"(?<=[.!?])\s+", text):
        if not any(b in chunk.lower() for b in boilerplate):
            parts.append(chunk)

    cleaned = _normalize_spaces(" ".join(parts))
    if len(cleaned) < min_length:
        return ""

    return cleaned


def _extract_text_with_requests(url: str, min_length: int = 80) -> str:
    try:
        with requests.Session() as session:
            session.headers.update(HEADERS)
            response = session.get(url, timeout=TIMEOUT, allow_redirects=True)
            response.raise_for_status()
    except requests.RequestException as exc:
        print(f"   request failed: {exc}")
        return ""

    final_url = response.url
    content_type = response.headers.get("Content-Type", "").lower()

    print(f"   final_url={final_url}")
    print(f"   status_code={response.status_code}")
    print(f"   content_type={content_type}")

    if any(hint in final_url.lower() for hint in BAD_URL_HINTS):
        print("   blocked by redirect/login page")
        return ""

    if "text/html" not in content_type:
        return ""

    raw_html = response.text
    print(f"   raw_html preview={raw_html[:300]!r}")

    return _clean_text_from_html(raw_html, min_length=min_length)


def _extract_text_with_playwright(url: str, min_length: int = 80) -> str:
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page()
            page.goto(url, wait_until="domcontentloaded", timeout=60000)
            page.wait_for_timeout(2000)

            final_url = page.url
            print(f"   final_url={final_url}")

            if any(hint in final_url.lower() for hint in BAD_URL_HINTS):
                print("   blocked by redirect/login page")
                browser.close()
                return ""

            raw_html = page.content()
            print(f"   raw_html preview={raw_html[:300]!r}")

            browser.close()
    except Exception as exc:
        print(f"   playwright failed: {exc}")
        return ""

    return _clean_text_from_html(raw_html, min_length=min_length)


def extract_text_from_url(url: str, min_length: int = 80) -> str:
    if "sites.google.com" in url.lower():
        return _extract_text_with_playwright(url, min_length=min_length)
    return _extract_text_with_requests(url, min_length=min_length)
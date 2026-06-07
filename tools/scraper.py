import os
import urllib.parse
from typing import Dict, List

import feedparser
import requests
from ddgs import DDGS
from pytrends.request import TrendReq

from config import SUBSTACK_FEEDS
from tools.progress import emit

# Each scraper returns a list of these
ScrapedItem = Dict[str, str]  # keys: title, url, snippet, source

# Stop words that shouldn't count as meaningful keyword matches
_STOP_WORDS = {
    "a", "an", "the", "and", "or", "for", "of", "in", "on", "to",
    "with", "by", "is", "it", "at", "be", "as", "this", "that",
}


def scrape_web_search(topic: str, max_results: int = 8) -> List[ScrapedItem]:
    """DuckDuckGo web search — works for any topic, no API key required."""
    try:
        items = []
        with DDGS() as ddgs:
            results = ddgs.text(topic, max_results=max_results)
            for r in results:
                items.append({
                    "title": r.get("title", ""),
                    "url": r.get("href", ""),
                    "snippet": r.get("body", "")[:300],
                    "source": "Web (DuckDuckGo)",
                })
        return items
    except Exception as e:
        print(f"[scraper] DuckDuckGo search error: {e}")
        return []


def scrape_google_trends(topic: str) -> List[ScrapedItem]:
    try:
        pytrends = TrendReq(hl="en-US", tz=360)
        pytrends.build_payload([topic], timeframe="now 7-d")
        related = pytrends.related_queries()

        items = []
        data = related.get(topic, {})
        top = data.get("top")
        if top is not None and not top.empty:
            for _, row in top.head(5).iterrows():
                items.append({
                    "title": row["query"],
                    "url": f"https://trends.google.com/trends/explore?q={row['query'].replace(' ', '+')}",
                    "snippet": f"Trending query related to '{topic}' — relative value: {row['value']}",
                    "source": "Google Trends",
                })
        return items
    except Exception as e:
        print(f"[scraper] Google Trends error: {e}")
        return []



def scrape_arxiv(topic: str, max_results: int = 5) -> List[ScrapedItem]:
    """Latest papers from Arxiv matching the topic."""
    try:
        query = urllib.parse.quote(topic)
        url = (
            f"http://export.arxiv.org/api/query"
            f"?search_query=all:{query}"
            f"&max_results={max_results}"
            f"&sortBy=submittedDate&sortOrder=descending"
        )
        feed = feedparser.parse(url)
        items = []
        for entry in feed.entries[:max_results]:
            authors = ", ".join(a.get("name", "") for a in entry.get("authors", [])[:3])
            items.append({
                "title": entry.get("title", "").replace("\n", " ").strip(),
                "url": entry.get("link", ""),
                "snippet": (
                    f"Authors: {authors}. "
                    + entry.get("summary", "")[:250].replace("\n", " ").strip()
                ),
                "source": "Arxiv",
            })
        return items
    except Exception as e:
        print(f"[scraper] Arxiv error: {e}")
        return []


def scrape_github(topic: str, max_results: int = 5) -> List[ScrapedItem]:
    """Top GitHub repos matching the topic, sorted by stars."""
    try:
        query = urllib.parse.quote(topic)
        headers = {"Accept": "application/vnd.github.v3+json"}
        if token := os.getenv("GITHUB_TOKEN"):
            headers["Authorization"] = f"Bearer {token}"
        resp = requests.get(
            f"https://api.github.com/search/repositories"
            f"?q={query}&sort=stars&order=desc&per_page={max_results}",
            headers=headers,
            timeout=10,
        )
        if not resp.ok:
            print(f"[scraper] GitHub API {resp.status_code}")
            return []
        items = []
        for repo in resp.json().get("items", []):
            stars = repo.get("stargazers_count", 0)
            lang = repo.get("language") or "unknown"
            desc = (repo.get("description") or "")[:200]
            items.append({
                "title": repo["full_name"],
                "url": repo["html_url"],
                "snippet": f"{desc} | ⭐ {stars:,} stars | {lang}",
                "source": "GitHub",
            })
        return items
    except Exception as e:
        print(f"[scraper] GitHub error: {e}")
        return []


def scrape_substack(topic: str) -> List[ScrapedItem]:
    # Only match articles where at least 2 meaningful keywords appear
    all_kw = [kw.lower() for kw in topic.lower().replace("/", " ").split()]
    keywords = [kw for kw in all_kw if kw not in _STOP_WORDS and len(kw) > 2]
    min_matches = max(1, min(2, len(keywords)))

    items = []
    for feed_url in SUBSTACK_FEEDS:
        try:
            feed = feedparser.parse(feed_url)
            for entry in feed.entries[:15]:
                text = (entry.get("title", "") + " " + entry.get("summary", "")).lower()
                matched = sum(1 for kw in keywords if kw in text)
                if matched >= min_matches:
                    items.append({
                        "title": entry.get("title", ""),
                        "url": entry.get("link", ""),
                        "snippet": entry.get("summary", "")[:300],
                        "source": feed.feed.get("title", "Substack"),
                    })
        except Exception as e:
            print(f"[scraper] Substack {feed_url} error: {e}")

    return items[:6]


def scrape_all(topic: str) -> List[ScrapedItem]:
    emit(f"🌐 Searching the web for <code>{topic}</code>…")
    print(f"[scraper] Web search     — '{topic}'")
    web = scrape_web_search(topic)

    emit("🔍 Checking <b>Google Trends</b>…")
    print(f"[scraper] Google Trends  — '{topic}'")
    trends = scrape_google_trends(topic)

    emit("📰 Checking <b>Substack RSS</b>…")
    print(f"[scraper] Substack RSS   — '{topic}'")
    substack = scrape_substack(topic)

    emit("📄 Fetching <b>Arxiv papers</b>…")
    print(f"[scraper] Arxiv          — '{topic}'")
    arxiv = scrape_arxiv(topic)

    emit("🐙 Searching <b>GitHub repos</b>…")
    print(f"[scraper] GitHub         — '{topic}'")
    github = scrape_github(topic)

    total = web + trends + substack + arxiv + github
    print(
        f"[scraper] Done — {len(total)} items "
        f"(web={len(web)}, trends={len(trends)}, substack={len(substack)}, "
        f"arxiv={len(arxiv)}, github={len(github)})"
    )
    return total

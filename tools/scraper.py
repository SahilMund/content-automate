import urllib.parse
from typing import Dict, List

import requests
from ddgs import DDGS

from tools.progress import emit

ScrapedItem = Dict[str, str]  # keys: title, url, snippet, source


def _ddg_web(query: str, max_results: int = 6) -> List[ScrapedItem]:
    try:
        with DDGS() as ddgs:
            return [
                {
                    "title": r.get("title", ""),
                    "url": r.get("href", ""),
                    "snippet": r.get("body", "")[:500],
                    "source": "Web",
                }
                for r in ddgs.text(query, max_results=max_results)
            ]
    except Exception as e:
        print(f"[scraper] DDG web error ({query!r}): {e}")
        return []


def _ddg_news(query: str, max_results: int = 6) -> List[ScrapedItem]:
    try:
        with DDGS() as ddgs:
            return [
                {
                    "title": r.get("title", ""),
                    "url": r.get("url", ""),
                    "snippet": r.get("body", "")[:500],
                    "source": "News",
                }
                for r in ddgs.news(query, max_results=max_results)
            ]
    except Exception as e:
        print(f"[scraper] DDG news error ({query!r}): {e}")
        return []


def scrape_github(topic: str, max_results: int = 5) -> List[ScrapedItem]:
    try:
        query = urllib.parse.quote(topic)
        resp = requests.get(
            f"https://api.github.com/search/repositories"
            f"?q={query}&sort=stars&order=desc&per_page={max_results}",
            headers={"Accept": "application/vnd.github.v3+json"},
            timeout=10,
        )
        if not resp.ok:
            return []
        return [
            {
                "title": repo["full_name"],
                "url": repo["html_url"],
                "snippet": f"{(repo.get('description') or '')[:200]} | ⭐ {repo.get('stargazers_count', 0):,} stars | {repo.get('language') or 'unknown'}",
                "source": "GitHub",
            }
            for repo in resp.json().get("items", [])
        ]
    except Exception as e:
        print(f"[scraper] GitHub error: {e}")
        return []


def fetch_url_content(url: str) -> str:
    """Fetch and extract readable text from a URL using stdlib only."""
    import urllib.request
    from html.parser import HTMLParser

    class _Extractor(HTMLParser):
        def __init__(self):
            super().__init__()
            self._skip = False
            self._depth = 0
            self.chunks: list[str] = []

        def handle_starttag(self, tag, attrs):
            if tag in ("script", "style", "nav", "header", "footer", "aside"):
                self._skip = True
                self._depth += 1

        def handle_endtag(self, tag):
            if tag in ("script", "style", "nav", "header", "footer", "aside"):
                self._depth -= 1
                if self._depth <= 0:
                    self._skip = False
                    self._depth = 0

        def handle_data(self, data):
            if not self._skip:
                stripped = data.strip()
                if stripped:
                    self.chunks.append(stripped)

    try:
        req = urllib.request.Request(
            url, headers={"User-Agent": "Mozilla/5.0 (compatible; ContentBot/1.0)"}
        )
        with urllib.request.urlopen(req, timeout=20) as resp:
            raw_html = resp.read().decode("utf-8", errors="ignore")
        parser = _Extractor()
        parser.feed(raw_html)
        text = "\n".join(parser.chunks)
        # Collapse excessive blank lines
        text = "\n".join(line for line in text.splitlines() if line.strip())
        return text[:10000]
    except Exception as e:
        print(f"[scraper] fetch_url_content failed for {url}: {e}")
        return ""


def scrape_all(topic: str) -> List[ScrapedItem]:
    # Anchor all queries to software/programming to avoid unrelated homonyms
    dev_topic = f"{topic} programming software developer"

    emit(f"🌐 Searching news for <code>{topic}</code>…")
    print(f"[scraper] News search    — '{topic}'")
    news = _ddg_news(f"{topic} software developer", max_results=6)

    emit("🔍 Searching dev articles…")
    print(f"[scraper] Dev sites      — '{topic}'")
    dev = _ddg_web(
        f"{topic} site:dev.to OR site:medium.com OR site:hackernoon.com OR site:infoq.com",
        max_results=5,
    )

    emit("💡 Searching tips & insights…")
    print(f"[scraper] Tips search    — '{topic}'")
    tips = _ddg_web(f"{dev_topic} tips best practices 2025 2026", max_results=5)

    emit("🐙 Searching GitHub repos…")
    print(f"[scraper] GitHub         — '{topic}'")
    github = scrape_github(topic, max_results=5)

    total = news + dev + tips + github
    seen_urls: set = set()
    unique = []
    for item in total:
        if item["url"] not in seen_urls:
            seen_urls.add(item["url"])
            unique.append(item)

    print(
        f"[scraper] Done — {len(unique)} items "
        f"(news={len(news)}, dev={len(dev)}, tips={len(tips)}, github={len(github)})"
    )
    return unique

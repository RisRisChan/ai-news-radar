#!/usr/bin/env python3
"""AI News Radar - Fetch AI news from RSS feeds, generate HTML, notify via LINE."""

import json
import logging
import os
import re
import sys
import time
import unicodedata
from datetime import datetime, timedelta, timezone
from pathlib import Path

import dotenv
dotenv.load_dotenv()

import feedparser
import requests
from bs4 import BeautifulSoup
from jinja2 import Environment, FileSystemLoader

from config import (
    AI_KEYWORDS_EN,
    AI_KEYWORDS_EN_WORD,
    AI_KEYWORDS_JA,
    CLAUDE_SOURCES,
    FEEDS,
    LINE_MAX_ARTICLES,
    MAX_SEEN_URLS,
    OUTPUT_HTML,
    SEEN_FILE,
    TEMPLATE_FILE,
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger(__name__)

SOURCE_LANG = {name: lang for name, _, _, lang in FEEDS}

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
}


def load_seen(path: str) -> list[str]:
    try:
        with open(path) as f:
            data = json.load(f)
        return data.get("urls", [])
    except (FileNotFoundError, json.JSONDecodeError):
        return []


def save_seen(path: str, seen_list: list[str]) -> None:
    if len(seen_list) > MAX_SEEN_URLS:
        seen_list = seen_list[-MAX_SEEN_URLS:]
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w") as f:
        json.dump({"urls": seen_list, "last_updated": datetime.now(timezone.utc).isoformat()}, f, ensure_ascii=False, indent=2)


def parse_date(entry) -> datetime:
    for attr in ("published_parsed", "updated_parsed"):
        parsed = getattr(entry, attr, None)
        if parsed:
            try:
                return datetime(*parsed[:6], tzinfo=timezone.utc)
            except Exception:
                pass
    return datetime.now(timezone.utc)


def parse_date_str(date_str: str) -> datetime:
    """Parse a date string like 'Apr 10, 2026' or 'March 25, 2026'."""
    for fmt in ("%b %d, %Y", "%B %d, %Y", "%Y-%m-%d"):
        try:
            return datetime.strptime(date_str.strip(), fmt).replace(tzinfo=timezone.utc)
        except ValueError:
            continue
    return datetime.now(timezone.utc)


def clean_html(text: str) -> str:
    text = re.sub(r"<[^>]+>", "", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


# --- RSS Feed fetching ---

def fetch_feed(name: str, url: str) -> list[dict]:
    try:
        feed = feedparser.parse(url)
        if feed.bozo and not feed.entries:
            log.warning("Feed parse error for %s: %s", name, feed.bozo_exception)
            return []
        articles = []
        for entry in feed.entries:
            summary = clean_html(entry.get("summary", "") or entry.get("description", "") or "")
            articles.append({
                "title": entry.get("title", "No Title"),
                "url": entry.get("link", ""),
                "published": parse_date(entry),
                "summary": summary[:300],
                "source": name,
                "lang": SOURCE_LANG.get(name, "en"),
                "category": "international" if SOURCE_LANG.get(name, "en") == "en" else "domestic",
                "title_ja": None,
                "summary_ja": None,
            })
        log.info("Fetched %d articles from %s", len(articles), name)
        return articles
    except Exception as e:
        log.error("Failed to fetch %s: %s", name, e)
        return []


def fetch_all_feeds() -> list[dict]:
    all_articles = []
    for name, url, _is_ai, _lang in FEEDS:
        all_articles.extend(fetch_feed(name, url))
        time.sleep(1)
    return all_articles


# --- Claude / Anthropic scraping ---

def fetch_claude_code_releases() -> list[dict]:
    """Fetch Claude Code releases from GitHub API + CHANGELOG.md."""
    articles = []
    try:
        # Get release dates from GitHub API
        api_resp = requests.get(
            "https://api.github.com/repos/anthropics/claude-code/releases?per_page=15",
            headers={"Accept": "application/vnd.github+json"},
            timeout=30,
        )
        api_resp.raise_for_status()
        releases = {r["tag_name"].lstrip("v"): r["published_at"] for r in api_resp.json()}

        # Get changelog content for summaries
        md_resp = requests.get(
            "https://raw.githubusercontent.com/anthropics/claude-code/main/CHANGELOG.md",
            timeout=30,
        )
        md_resp.raise_for_status()

        # Parse CHANGELOG.md: split by ## version headings
        sections = re.split(r"\n## (\d+\.\d+\.\d+)\s*\n", md_resp.text)
        # sections = ['header', 'version1', 'content1', 'version2', 'content2', ...]
        for i in range(1, len(sections) - 1, 2):
            version = sections[i]
            content = sections[i + 1]

            if version not in releases:
                continue

            date = datetime.fromisoformat(releases[version].replace("Z", "+00:00"))
            bullets = re.findall(r"^- (.+)$", content, re.MULTILINE)
            summary = " / ".join(b.strip() for b in bullets[:4])[:300]

            articles.append({
                "title": f"Claude Code v{version}",
                "url": f"https://github.com/anthropics/claude-code/releases/tag/v{version}",
                "published": date,
                "summary": summary,
                "source": "Claude Code",
                "lang": "en",
                "category": "claude",
                "title_ja": None,
                "summary_ja": None,
            })

        log.info("Fetched %d Claude Code releases", len(articles))
    except Exception as e:
        log.error("Failed to fetch Claude Code releases: %s", e)
    return articles


def scrape_anthropic_page(name: str, url: str) -> list[dict]:
    """Scrape Anthropic news/engineering/research pages."""
    try:
        resp = requests.get(url, headers=HEADERS, timeout=30)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "html.parser")
        articles = []

        # Find article links - Anthropic uses <a> tags with article titles
        for link in soup.find_all("a", href=True):
            href = link["href"]
            # Match article paths like /news/..., /engineering/..., /research/...
            if not re.match(r"^/(news|engineering|research)/[a-z0-9]", href):
                continue

            title = link.get_text(strip=True)
            if not title or len(title) < 10:
                continue

            full_url = f"https://www.anthropic.com{href}" if href.startswith("/") else href

            # Try to find a date near the link
            parent = link.find_parent()
            date = datetime.now(timezone.utc)
            if parent:
                date_text = parent.find(string=re.compile(r"(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\w*\s+\d{1,2},\s+\d{4}"))
                if date_text:
                    date = parse_date_str(date_text.strip())

            # Avoid duplicates within this scrape
            if any(a["url"] == full_url for a in articles):
                continue

            articles.append({
                "title": title,
                "url": full_url,
                "published": date,
                "summary": "",
                "source": name,
                "lang": "en",
                "category": "claude",
                "title_ja": None,
                "summary_ja": None,
            })

        log.info("Scraped %d articles from %s", len(articles), name)
        return articles
    except Exception as e:
        log.error("Failed to scrape %s: %s", name, e)
        return []


def fetch_claude_sources() -> list[dict]:
    """Fetch all Claude/Anthropic specific sources."""
    all_articles = []
    all_articles.extend(fetch_claude_code_releases())
    time.sleep(1)
    for name, url in CLAUDE_SOURCES:
        if "changelog" in url:
            continue  # handled by fetch_claude_code_releases
        all_articles.extend(scrape_anthropic_page(name, url))
        time.sleep(1)
    return all_articles


# --- Filtering ---

def normalize(text: str) -> str:
    return unicodedata.normalize("NFKC", text)


def is_ai_related(article: dict) -> bool:
    text_lower = normalize(f"{article['title']} {article['summary']}").lower()
    for kw in AI_KEYWORDS_EN:
        if kw in text_lower:
            return True
    for pattern in AI_KEYWORDS_EN_WORD:
        if re.search(pattern, text_lower):
            return True
    text_original = normalize(f"{article['title']} {article['summary']}")
    for kw in AI_KEYWORDS_JA:
        if kw in text_original:
            return True
    return False


def filter_articles(articles: list[dict]) -> list[dict]:
    ai_specific_sources = {name for name, _, is_ai, _ in FEEDS if is_ai}
    result = []
    for a in articles:
        if a["source"] in ai_specific_sources or is_ai_related(a):
            result.append(a)
    log.info("Filtered to %d AI-related articles from %d total", len(result), len(articles))
    return result


def deduplicate(articles: list[dict], seen_urls: set[str]) -> list[dict]:
    new_articles = [a for a in articles if a["url"] and a["url"] not in seen_urls]
    log.info("Deduplicated: %d new articles (removed %d seen)", len(new_articles), len(articles) - len(new_articles))
    return new_articles


# --- Translation ---

def translate_articles(articles: list[dict]) -> list[dict]:
    """Translate English article titles and summaries to Japanese using Google Translate."""
    from deep_translator import GoogleTranslator

    en_articles = [a for a in articles if a["lang"] == "en"]
    if not en_articles:
        return articles

    translator = GoogleTranslator(source="en", target="ja")

    batch_size = 30
    for i in range(0, len(en_articles), batch_size):
        batch = en_articles[i:i + batch_size]

        titles = [a["title"] for a in batch]
        try:
            translated_titles = translator.translate_batch(titles)
            for a, t in zip(batch, translated_titles):
                if t:
                    a["title_ja"] = t
        except Exception as e:
            log.error("Title translation failed for batch %d: %s", i, e)

        time.sleep(0.5)

        summaries = [a["summary"][:200] for a in batch if a["summary"]]
        batch_with_summary = [a for a in batch if a["summary"]]
        try:
            translated_summaries = translator.translate_batch(summaries)
            for a, t in zip(batch_with_summary, translated_summaries):
                if t:
                    a["summary_ja"] = t
        except Exception as e:
            log.error("Summary translation failed for batch %d: %s", i, e)

        log.info("Translated batch %d-%d (%d articles)", i, i + len(batch), len(batch))
        if i + batch_size < len(en_articles):
            time.sleep(1)

    return articles


# --- Output ---

def render_html(articles: list[dict]) -> None:
    template_dir = Path(TEMPLATE_FILE).parent
    template_name = Path(TEMPLATE_FILE).name
    env = Environment(loader=FileSystemLoader(str(template_dir)))
    template = env.get_template(template_name)

    claude = [a for a in articles if a.get("category") == "claude"]
    international = [a for a in articles if a.get("category") == "international"][:10]
    domestic = [a for a in articles if a.get("category") == "domestic"][:10]

    def group_by_date(arts):
        grouped = {}
        for a in arts:
            date_key = a["published"].strftime("%Y-%m-%d")
            grouped.setdefault(date_key, []).append(a)
        return grouped

    html = template.render(
        claude=group_by_date(claude),
        international=group_by_date(international),
        domestic=group_by_date(domestic),
        claude_count=len(claude),
        international_count=len(international),
        domestic_count=len(domestic),
        updated_at=datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
        total_count=len(articles),
    )

    Path(OUTPUT_HTML).parent.mkdir(parents=True, exist_ok=True)
    with open(OUTPUT_HTML, "w", encoding="utf-8") as f:
        f.write(html)
    log.info("Generated HTML with %d articles -> %s", len(articles), OUTPUT_HTML)


def send_line_notification(articles: list[dict]) -> None:
    token = os.environ.get("LINE_CHANNEL_ACCESS_TOKEN")
    user_id = os.environ.get("LINE_USER_ID")
    if not token or not user_id:
        log.info("LINE credentials not set, skipping notification")
        return

    claude = [a for a in articles if a.get("category") == "claude"]
    intl = [a for a in articles if a.get("category") == "international"]
    dom = [a for a in articles if a.get("category") == "domestic"]

    lines = [f"AI News Radar - {datetime.now(timezone.utc).strftime('%Y-%m-%d')}", ""]
    for label, group, n in [("-- Claude/Anthropic --", claude, 5), ("-- 国内 --", dom, 3), ("-- 海外 --", intl, 3)]:
        if group:
            lines.append(label)
            for a in group[:n]:
                title = a.get("title_ja") or a["title"]
                lines.append(f"{a['source']}: {title}")
                lines.append(a["url"])
                lines.append("")
    message = "\n".join(lines).strip()

    if len(message) > 5000:
        message = message[:4997] + "..."

    resp = requests.post(
        "https://api.line.me/v2/bot/message/push",
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {token}",
        },
        json={
            "to": user_id,
            "messages": [{"type": "text", "text": message}],
        },
        timeout=30,
    )
    if resp.status_code == 200:
        log.info("LINE notification sent successfully")
    else:
        log.error("LINE notification failed: %s %s", resp.status_code, resp.text)


def main():
    dry_run = "--dry-run" in sys.argv

    seen_list = load_seen(SEEN_FILE)
    seen_urls = set(seen_list)

    cutoff = datetime.now(timezone.utc) - timedelta(days=7)

    # Fetch RSS feeds
    articles = fetch_all_feeds()
    articles = [a for a in articles if a["published"] > cutoff]
    log.info("Filtered to %d articles within last 7 days", len(articles))
    articles = filter_articles(articles)

    # Fetch Claude/Anthropic sources
    claude_articles = fetch_claude_sources()
    claude_articles = [a for a in claude_articles if a["published"] > cutoff]
    log.info("Claude/Anthropic: %d articles within last 7 days", len(claude_articles))

    # Combine and deduplicate
    all_articles = articles + claude_articles
    all_articles = deduplicate(all_articles, seen_urls)
    all_articles.sort(key=lambda a: a["published"], reverse=True)

    if not all_articles:
        log.info("No new articles found")
        render_html([])
        return

    all_articles = translate_articles(all_articles)
    render_html(all_articles)

    if not dry_run:
        send_line_notification(all_articles)
        new_urls = [a["url"] for a in all_articles]
        save_seen(SEEN_FILE, seen_list + new_urls)
    else:
        log.info("Dry run: skipping LINE notification and seen.json update")

    log.info("Done! %d new articles processed", len(all_articles))


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""
Fetch the past 7 days of AI & tech launches from public RSS/Atom feeds,
curate 5-8 notable tools with Gemini 4 Hydrogen (Free Tier compatible),
and update the TOOLS array + date range inside index.html while preserving
the full 3D glassmorphic design.

Environment variables:
  GEMINI_API_KEY   (required) Google AI Studio API key
  HTML_PATH        (optional) Path to index.html (defaults to "index.html")
"""

import datetime as dt
import email.utils
import html
import json
import os
import re
import sys
import time
import urllib.error
import urllib.request
import xml.etree.ElementTree as ET

GEMINI_MODELS = [
    "gemini-4-hydrogen",
    "gemini-3.8-flash",
    "gemini-3.6-flash",
    "gemini-3.5-flash-lite",
]

RSS_FEEDS = [
    ("TechCrunch AI", "https://techcrunch.com/category/artificial-intelligence/feed/"),
    ("Google Blog AI", "https://blog.google/technology/ai/rss/"),
    ("OpenAI News", "https://openai.com/news/rss.xml"),
    ("Hugging Face Blog", "https://huggingface.co/blog/feed.xml"),
    ("The Verge AI", "https://www.theverge.com/rss/ai-artificial-intelligence/index.xml"),
    ("VentureBeat AI", "https://venturebeat.com/category/ai/feed/"),
]

CATEGORY_META = {
    "coding": ("Coding & Models", "from-blue-500/20 to-indigo-500/20"),
    "images-video": ("Images & Worlds", "from-orange-500/20 to-rose-500/20"),
    "productivity": ("Productivity & Writing", "from-emerald-500/20 to-lime-500/20"),
}


def strip_html(raw: str) -> str:
    text = re.sub(r"<[^>]+>", " ", raw or "")
    return re.sub(r"\s+", " ", html.unescape(text)).strip()


def parse_date(date_str: str) -> dt.datetime | None:
    if not date_str:
        return None
    try:
        parsed = email.utils.parsedate_to_datetime(date_str)
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=dt.timezone.utc)
        return parsed.astimezone(dt.timezone.utc)
    except Exception:
        pass
    for fmt in ("%Y-%m-%dT%H:%M:%S%z", "%Y-%m-%dT%H:%M:%SZ", "%Y-%m-%d"):
        try:
            clean = date_str.strip()
            if clean.endswith("Z"):
                clean = clean[:-1] + "+0000"
            parsed = dt.datetime.strptime(clean[:25], fmt)
            if parsed.tzinfo is None:
                parsed = parsed.replace(tzinfo=dt.timezone.utc)
            return parsed.astimezone(dt.timezone.utc)
        except Exception:
            continue
    return None


def fetch_recent_items(days: int = 8) -> list[dict]:
    cutoff = dt.datetime.now(dt.timezone.utc) - dt.timedelta(days=days)
    items: list[dict] = []

    for source_name, feed_url in RSS_FEEDS:
        req = urllib.request.Request(
            feed_url,
            headers={"User-Agent": "AIC-Newsletter-Bot/1.0"},
        )
        try:
            with urllib.request.urlopen(req, timeout=15) as resp:
                xml_bytes = resp.read()
        except Exception as exc:
            print(f"Warning: skipping {source_name} ({exc})", file=sys.stderr)
            continue

        try:
            root = ET.fromstring(xml_bytes)
        except ET.ParseError:
            continue

        # Handle RSS <item> and Atom <entry>
        entries = root.findall(".//item")
        is_atom = False
        if not entries:
            entries = root.findall(".//{http://www.w3.org/2005/Atom}entry")
            is_atom = True

        for entry in entries[:20]:
            if is_atom:
                title_el = entry.find("{http://www.w3.org/2005/Atom}title")
                link_el = entry.find("{http://www.w3.org/2005/Atom}link")
                date_el = entry.find("{http://www.w3.org/2005/Atom}published")
                if date_el is None:
                    date_el = entry.find("{http://www.w3.org/2005/Atom}updated")
                desc_el = entry.find("{http://www.w3.org/2005/Atom}summary")
                if desc_el is None:
                    desc_el = entry.find("{http://www.w3.org/2005/Atom}content")
                link = link_el.attrib.get("href", "") if link_el is not None else ""
            else:
                title_el = entry.find("title")
                link_el = entry.find("link")
                date_el = entry.find("pubDate")
                desc_el = entry.find("description")
                link = (link_el.text or "").strip() if link_el is not None else ""

            title = strip_html(title_el.text if title_el is not None else "")
            summary = strip_html(desc_el.text if desc_el is not None else "")[:320]
            pub_raw = (date_el.text or "").strip() if date_el is not None else ""
            pub_dt = parse_date(pub_raw)

            if pub_dt and pub_dt < cutoff:
                continue
            if title and link.startswith("http"):
                items.append({
                    "source": source_name,
                    "title": title,
                    "date": pub_dt.strftime("%b %d, %Y") if pub_dt else "This week",
                    "summary": summary,
                    "url": link,
                })

    return items[:60]


def curate_with_gemini(api_key: str, feed_items: list[dict]) -> list[dict]:
    prompt = f"""You are curating a weekly AI & tech tools newsletter ("The Monday Drop").
From ONLY the verified articles below, select 6 to 8 of the most notable AI tools, apps, models, or major feature updates from this past week. Put the single most talked-about launch first (`featured: true`, all others `featured: false`).

Return ONLY valid JSON (no markdown fences) as a list of objects with these exact keys:
- "id": short lowercase kebab-case slug
- "name": concise product/model name
- "date": publication date string from the source (e.g. "Nov 23, 2026")
- "category": MUST be one of "coding", "images-video", or "productivity"
- "pricingTier": MUST be "free" (if free or free tier/beta exists) or "paid"
- "pricingBadge": short label like "Free", "Free & Paid", "Free Beta", "Paid", or "Paid API"
- "pricingDetail": 1-2 sentence accurate pricing/access summary based on the source (do not invent prices)
- "oneLine": crisp 1-sentence summary of what it does
- "usefulFor": short audience description (e.g. "Software engineers and QA teams")
- "url": exact URL copied verbatim from the source list below
- "highlight": 1 short sentence on why it matters

Articles:
{json.dumps(feed_items, indent=2)}
"""

    payload = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {
            "responseMimeType": "application/json",
            "temperature": 0.2,
        },
    }

    data = None
    last_err = None
    body_bytes = json.dumps(payload).encode("utf-8")

    for model_name in GEMINI_MODELS:
        endpoint = (
            f"https://generativelanguage.googleapis.com/v1beta/models/"
            f"{model_name}:generateContent"
        )
        for attempt in range(1, 3):
            req = urllib.request.Request(
                endpoint,
                data=body_bytes,
                headers={
                    "Content-Type": "application/json",
                    "x-goog-api-key": api_key,
                },
                method="POST",
            )
            try:
                print(f"Trying {model_name} (attempt {attempt})...")
                with urllib.request.urlopen(req, timeout=60) as resp:
                    data = json.loads(resp.read().decode("utf-8"))
                break
            except urllib.error.HTTPError as err:
                body = err.read().decode("utf-8", errors="replace")
                last_err = RuntimeError(f"{model_name} HTTP {err.code}: {body}")
                if err.code in (429, 500, 503, 504):
                    print(f"Transient {err.code} on {model_name}, retrying...", file=sys.stderr)
                    time.sleep(3 * attempt)
                    continue
                if err.code == 404:
                    break
                raise last_err from err
        if data is not None:
            break

    if data is None:
        raise last_err or RuntimeError("All Gemini models failed.")

    raw_text = data["candidates"][0]["content"]["parts"][0]["text"]
    curated = json.loads(raw_text)

    if not isinstance(curated, list) or len(curated) < 5:
        raise RuntimeError(f"Expected >= 5 curated tools, got {len(curated) if isinstance(curated, list) else type(curated)}")

    allowed_urls = {item["url"] for item in feed_items}
    cleaned = []
    for idx, t in enumerate(curated[:8]):
        cat = t.get("category", "productivity")
        if cat not in CATEGORY_META:
            cat = "productivity"
        cat_label, accent = CATEGORY_META[cat]
        url = t.get("url", "")
        if url not in allowed_urls:
            # Keep only verified URLs from our fetched feeds
            continue
        cleaned.append({
            "id": re.sub(r"[^a-z0-9-]", "-", str(t.get("id", f"tool-{idx+1}")).lower()).strip("-") or f"tool-{idx+1}",
            "name": str(t.get("name", "Untitled Tool")),
            "date": str(t.get("date", "This week")),
            "category": cat,
            "categoryLabel": cat_label,
            "accent": accent,
            "featured": idx == 0,
            "pricingTier": "free" if t.get("pricingTier") == "free" else "paid",
            "pricingBadge": str(t.get("pricingBadge", "Paid")),
            "pricingDetail": str(t.get("pricingDetail", "See official announcement for plan details.")),
            "oneLine": str(t.get("oneLine", "")),
            "usefulFor": str(t.get("usefulFor", "Builders and teams")),
            "url": url,
            "highlight": str(t.get("highlight", "")),
            "initialVotes": max(4, 14 - idx),
        })

    if len(cleaned) < 5:
        raise RuntimeError("Fewer than 5 verified tools remained after URL validation.")
    return cleaned


def update_html_tools(html_path: str, tools: list[dict], date_range_label: str) -> None:
    with open(html_path, "r", encoding="utf-8") as f:
        content = f.read()

    tools_json = json.dumps(tools, indent=6, ensure_ascii=False)
    new_content, count = re.subn(
        r"const TOOLS = \[.*?\];",
        f"const TOOLS = {tools_json};",
        content,
        count=1,
        flags=re.DOTALL,
    )
    if count != 1:
        raise RuntimeError("Could not locate `const TOOLS = [...];` in HTML file.")

    # Update date range labels in title, header, hero, and footer
    new_content = re.sub(
        r"Issue #\d+ · [A-Za-z]+ \d+[–-](?:[A-Za-z]+ )?\d+, \d{4}",
        f"Weekly Edition · {date_range_label}",
        new_content,
    )
    new_content = re.sub(
        r"Weekly Product &amp; Tool Digest · [A-Za-z]+ \d+[–-](?:[A-Za-z]+ )?\d+",
        f"Weekly Product &amp; Tool Digest · {date_range_label}",
        new_content,
    )
    new_content = re.sub(
        r"\([A-Za-z]+ \d+[–-](?:[A-Za-z]+ )?\d+, \d{4}\)",
        f"({date_range_label})",
        new_content,
    )

    # Update category pill counts dynamically
    counts = {
        "all": len(tools),
        "coding": sum(1 for t in tools if t["category"] == "coding"),
        "images-video": sum(1 for t in tools if t["category"] == "images-video"),
        "productivity": sum(1 for t in tools if t["category"] == "productivity"),
    }
    new_content = re.sub(r"All \(\d+\)", f"All ({counts['all']})", new_content)
    new_content = re.sub(r"Coding &amp; Models \(\d+\)", f"Coding &amp; Models ({counts['coding']})", new_content)
    new_content = re.sub(r"Images &amp; Worlds \(\d+\)", f"Images &amp; Worlds ({counts['images-video']})", new_content)
    new_content = re.sub(r"Productivity &amp; Writing \(\d+\)", f"Productivity &amp; Writing ({counts['productivity']})", new_content)

    with open(html_path, "w", encoding="utf-8") as f:
        f.write(new_content)


def main() -> int:
    api_key = os.environ.get("GEMINI_API_KEY", "").strip()
    if not api_key:
        print("Error: GEMINI_API_KEY environment variable is not set.", file=sys.stderr)
        return 1

    html_path = os.environ.get("HTML_PATH", "index.html")
    if not os.path.exists(html_path):
        print(f"Error: {html_path} not found.", file=sys.stderr)
        return 1

    print("Fetching recent AI & tech articles from RSS feeds...")
    items = fetch_recent_items(days=8)
    print(f"Fetched {len(items)} recent items.")
    if len(items) < 5:
        print("Not enough recent items fetched; keeping existing index.html.", file=sys.stderr)
        return 0

    print("Curating top launches with Gemini 4 Hydrogen...")
    tools = curate_with_gemini(api_key, items)

    today = dt.datetime.now(dt.timezone.utc)
    week_ago = today - dt.timedelta(days=7)
    date_label = f"{week_ago.strftime('%b %d')}–{today.strftime('%b %d, %Y')}"

    update_html_tools(html_path, tools, date_label)
    print(f"Updated {html_path} with {len(tools)} tools for {date_label}.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
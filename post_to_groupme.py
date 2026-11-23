#!/usr/bin/env python3
"""
Post the weekly AI tools roundup to a GroupMe chat via the GroupMe Bot API.

Environment variables:
  GROUPME_BOT_ID   (required) Your GroupMe Bot ID from https://dev.groupme.com/bots
  NEWSLETTER_URL   (optional) Public URL where ai_newsletter.html is hosted (e.g. GitHub Pages)
  HTML_PATH        (optional) Path to ai_newsletter.html (defaults to "index.html" or "ai_newsletter.html")
"""

import json
import os
import re
import sys
import time
import urllib.error
import urllib.request

GROUPME_POST_URL = "https://api.groupme.com/v3/bots/post"
MAX_GROUPME_CHARS = 950  # GroupMe bot messages max out at 1,000 characters


def extract_tools_from_html(html_path: str) -> list[dict]:
    """Extract the TOOLS array from ai_newsletter.html without external dependencies."""
    with open(html_path, "r", encoding="utf-8") as f:
        content = f.read()

    match = re.search(r"const TOOLS = (\[.*?\]);", content, re.DOTALL)
    if not match:
        raise ValueError(f"Could not find TOOLS array in {html_path}")

    js_array = match.group(1)
    # Extract key fields per object safely
    tools = []
    for block in re.finditer(r"\{(.*?)\n      \}", js_array, re.DOTALL):
        chunk = block.group(1)
        def grab(key: str) -> str:
            m = re.search(rf"{key}:\s*(['\"])(.*?)\1", chunk)
            return m.group(2) if m else ""

        name = grab("name")
        one_line = grab("oneLine")
        pricing = grab("pricingBadge")
        url = grab("url")
        featured = bool(re.search(r"featured:\s*true", chunk))
        if name and url:
            tools.append({
                "name": name,
                "oneLine": one_line,
                "pricingBadge": pricing,
                "url": url,
                "featured": featured,
            })
    return tools


def build_messages(tools: list[dict], newsletter_url: str = "") -> list[str]:
    """Build one or more GroupMe messages under the 1,000-character limit."""
    header = "📌 The Monday Drop — Weekly AI & Tech Launches\n"
    if newsletter_url:
        header += f"🌐 Interactive 3D Deck: {newsletter_url}\n"

    chunks: list[str] = []
    current = header.strip()

    for idx, tool in enumerate(tools, start=1):
        tag = "🔥 #1: " if tool["featured"] else ""
        entry = (
            f"\n\n{idx}. {tag}{tool['name']} ({tool['pricingBadge']})\n"
            f"{tool['oneLine']}\n"
            f"🔗 {tool['url']}"
        )
        if len(current) + len(entry) > MAX_GROUPME_CHARS:
            chunks.append(current)
            current = f"📌 The Monday Drop (cont.){entry}"
        else:
            current += entry

    footer = "\n\nReply with which one you're trying first!"
    if len(current) + len(footer) <= MAX_GROUPME_CHARS:
        current += footer
    else:
        chunks.append(current)
        current = footer.strip()

    chunks.append(current)
    return chunks


def post_message(bot_id: str, text: str) -> None:
    """Send a single POST request to the GroupMe Bot API."""
    payload = json.dumps({"bot_id": bot_id, "text": text}).encode("utf-8")
    req = urllib.request.Request(
        GROUPME_POST_URL,
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            if resp.status not in (200, 201, 202):
                raise RuntimeError(f"Unexpected HTTP status: {resp.status}")
    except urllib.error.HTTPError as err:
        body = err.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"GroupMe API error {err.code}: {body}") from err


def main() -> int:
    bot_id = os.environ.get("GROUPME_BOT_ID", "").strip()
    if not bot_id:
        print("Error: GROUPME_BOT_ID environment variable is not set.", file=sys.stderr)
        return 1

    newsletter_url = os.environ.get("NEWSLETTER_URL", "").strip()
    html_path = os.environ.get("HTML_PATH", "").strip()
    if not html_path:
        for candidate in ("index.html", "ai_newsletter.html"):
            if os.path.exists(candidate):
                html_path = candidate
                break

    if not html_path or not os.path.exists(html_path):
        print("Error: Could not find index.html or ai_newsletter.html.", file=sys.stderr)
        return 1

    tools = extract_tools_from_html(html_path)
    if not tools:
        print("Error: No tools extracted from HTML.", file=sys.stderr)
        return 1

    messages = build_messages(tools, newsletter_url=newsletter_url)
    for i, msg in enumerate(messages, start=1):
        print(f"Posting part {i}/{len(messages)} ({len(msg)} chars)...")
        post_message(bot_id, msg)
        if i < len(messages):
            time.sleep(1.5)

    print("Successfully posted to GroupMe!")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
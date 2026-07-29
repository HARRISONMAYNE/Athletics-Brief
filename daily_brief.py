#!/usr/bin/env python3
"""Daily Athletics Brief — builds a page and emails it.

Sections, in order: National, Youth & Grassroots, Para, International,
Events to keep an eye on.

Usage:
    python daily_brief.py            # build site + send email
    python daily_brief.py --no-email # build site only
    python daily_brief.py --check    # test every feed URL, send nothing

Email is configured through environment variables, so nothing sensitive
lives in this file:
    SMTP_HOST, SMTP_PORT, SMTP_USER, SMTP_PASS, MAIL_FROM, MAIL_TO
"""

from __future__ import annotations

import argparse
import os
import smtplib
import sys
from datetime import date, datetime, timedelta, timezone
from email.message import EmailMessage
from html import escape
from pathlib import Path

import feedparser
import yaml

ROOT = Path(__file__).parent
DOCS = ROOT / "docs"
WINDOW_HOURS = 26  # slight overlap so nothing falls between runs
EVENTS_SHOWN = 6

# Design tokens. Blue is the track; amber marks a watchlist name.
INK, PAPER, RULE = "#0E1116", "#F5F6F4", "#D6D9D4"
TRACK, MARK, MUTED = "#1B4FD8", "#E8A33D", "#5B6169"
MONO = "ui-monospace,SFMono-Regular,Menlo,monospace"
SANS = "-apple-system,BlinkMacSystemFont,'Segoe UI',Helvetica,Arial,sans-serif"


def load_config() -> dict:
    with open(ROOT / "feeds.yml", encoding="utf-8") as fh:
        return yaml.safe_load(fh)


def entry_time(entry):
    for field in ("published_parsed", "updated_parsed"):
        parsed = getattr(entry, field, None)
        if parsed:
            return datetime(*parsed[:6], tzinfo=timezone.utc)
    return None


def pull(feeds, cutoff, section_key):
    items, failures = [], []
    for feed in feeds:
        try:
            parsed = feedparser.parse(feed["url"])
            if parsed.bozo and not parsed.entries:
                failures.append(feed["name"])
                continue
            for entry in parsed.entries:
                when = entry_time(entry)
                if when and when < cutoff:
                    continue
                items.append({
                    "title": entry.get("title", "").strip(),
                    "link": entry.get("link", ""),
                    "source": feed["name"],
                    "when": when,
                    "section": section_key,
                })
        except Exception as exc:  # a dead feed must never kill the brief
            failures.append(f"{feed['name']} ({exc.__class__.__name__})")
    return items, failures


def reroute(items, routing):
    """Move items into Para or Youth on subject matter, not just source."""
    for item in items:
        haystack = " " + item["title"].lower() + " "
        for key in ("para", "youth"):
            if any(term in haystack for term in routing.get(key, [])):
                item["section"] = key
                break
    return items


def dedupe(items):
    seen, unique = set(), []
    for item in items:
        key = item["title"].lower()[:70]
        if key and key not in seen:
            seen.add(key)
            unique.append(item)
    return unique


def rank(items, watchlist):
    names = [n.lower() for n in watchlist]

    def key(item):
        hit = any(n in item["title"].lower() for n in names)
        when = item["when"] or datetime.min.replace(tzinfo=timezone.utc)
        return (0 if hit else 1, -when.timestamp())

    return sorted(items, key=key)


def render_items(items, watchlist):
    if not items:
        return (f'<p style="margin:0;color:{MUTED};font-size:15px">'
                "Nothing in the last 24 hours. Quiet day, or a feed is down — "
                "check the source log at the foot of the page.</p>")
    names = [n.lower() for n in watchlist]
    rows = []
    for item in items:
        flagged = any(n in item["title"].lower() for n in names)
        bar = MARK if flagged else RULE
        stamp = item["when"].strftime("%H:%M") if item["when"] else "--:--"
        rows.append(
            f'<div style="border-left:3px solid {bar};padding:0 0 0 14px;margin:0 0 18px">'
            f'<div style="font-family:{MONO};font-size:11px;letter-spacing:.08em;'
            f'color:{MUTED};text-transform:uppercase">{stamp} &nbsp;·&nbsp; '
            f'{escape(item["source"])}</div>'
            f'<a href="{escape(item["link"])}" style="color:{INK};text-decoration:none;'
            f'font-size:17px;line-height:1.35;font-weight:600;display:block;margin-top:3px">'
            f'{escape(item["title"])}</a></div>')
    return "".join(rows)


def render_events(events):
    today = date.today()
    upcoming = sorted(
        (e for e in events if e["date"] >= today), key=lambda e: e["date"]
    )[:EVENTS_SHOWN]
    if not upcoming:
        return (f'<p style="margin:0;color:{MUTED};font-size:15px">'
                "No fixtures listed. Top up the <code>events</code> block in "
                "feeds.yml.</p>")
    rows = []
    for event in upcoming:
        days = (event["date"] - today).days
        countdown = "today" if days == 0 else ("tomorrow" if days == 1 else f"in {days} days")
        note = (f'<div style="font-size:14px;color:{MUTED};margin-top:2px">'
                f'{escape(event["note"])}</div>') if event.get("note") else ""
        title = escape(event["name"])
        if event.get("link"):
            title = (f'<a href="{escape(event["link"])}" style="color:{INK};'
                     f'text-decoration:none">{title}</a>')
        rows.append(
            f'<div style="border-left:3px solid {TRACK};padding:0 0 0 14px;margin:0 0 18px">'
            f'<div style="font-family:{MONO};font-size:11px;letter-spacing:.08em;'
            f'color:{TRACK};text-transform:uppercase">'
            f'{event["date"].strftime("%a %d %b")} &nbsp;·&nbsp; {countdown}</div>'
            f'<div style="font-size:17px;font-weight:600;margin-top:3px">{title}</div>'
            f'{note}</div>')
    return "".join(rows)


def section(title, count_label, body):
    return (f'<h2 style="font-size:13px;letter-spacing:.14em;text-transform:uppercase;'
            f'color:{TRACK};margin:36px 0 4px;font-weight:700">{escape(title)}</h2>'
            f'<div style="font-family:{MONO};font-size:11px;color:{MUTED};'
            f'margin:0 0 18px">{count_label}</div>{body}')


def build_html(blocks, events, failures, watchlist):
    today = datetime.now(timezone.utc).strftime("%A %d %B %Y")
    body = "".join(
        section(title, f'{len(items)} item{"" if len(items) == 1 else "s"}',
                render_items(items, watchlist))
        for title, items in blocks
    )
    body += section("Events to keep an eye on", "next up", render_events(events))
    log = (f'Feeds not responding this run: {escape(", ".join(failures))}.'
           if failures else "All feeds responded.")
    return f"""<!doctype html>
<html lang="en-GB"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Daily Athletics Brief — {today}</title></head>
<body style="margin:0;padding:0;background:{PAPER}">
<div style="max-width:640px;margin:0 auto;padding:32px 22px 56px;font-family:{SANS};color:{INK}">

  <div style="border-bottom:2px solid {INK};padding-bottom:14px">
    <div style="font-family:{MONO};font-size:11px;letter-spacing:.18em;
         text-transform:uppercase;color:{TRACK}">Daily Athletics Brief</div>
    <h1 style="font-size:30px;line-height:1.1;margin:8px 0 0;font-weight:800;
        letter-spacing:-.02em">{today}</h1>
  </div>

  {body}

  <div style="border-top:1px solid {RULE};margin-top:40px;padding-top:16px">
    <p style="font-size:12px;color:{MUTED};margin:0">
      Amber bars mark watchlist names. Times are UTC, from the publisher's feed.
      Headlines are links, not verified marks — check any time or distance
      against World Athletics or the meet's own results before you use it on air.</p>
    <p style="font-size:12px;color:{MUTED};margin:8px 0 0">{log}</p>
  </div>
</div></body></html>"""


def send_email(html):
    required = ["SMTP_HOST", "SMTP_USER", "SMTP_PASS", "MAIL_FROM", "MAIL_TO"]
    missing = [k for k in required if not os.environ.get(k)]
    if missing:
        print(f"Email skipped — not configured: {', '.join(missing)}")
        return

    msg = EmailMessage()
    msg["Subject"] = f"Athletics Brief — {datetime.now().strftime('%a %d %b')}"
    msg["From"] = os.environ["MAIL_FROM"]
    msg["To"] = os.environ["MAIL_TO"]
    msg.set_content("This brief is formatted in HTML. Open it in an HTML-capable client.")
    msg.add_alternative(html, subtype="html")

    host, port = os.environ["SMTP_HOST"], int(os.environ.get("SMTP_PORT", 465))
    if port == 587:
        with smtplib.SMTP(host, port) as server:
            server.starttls()
            server.login(os.environ["SMTP_USER"], os.environ["SMTP_PASS"])
            server.send_message(msg)
    else:
        with smtplib.SMTP_SSL(host, port) as server:
            server.login(os.environ["SMTP_USER"], os.environ["SMTP_PASS"])
            server.send_message(msg)
    print(f"Email sent to {os.environ['MAIL_TO']}")


def check_feeds(config):
    bad = 0
    for sec in config["sections"]:
        for feed in sec["feeds"]:
            count = len(feedparser.parse(feed["url"]).entries)
            if not count:
                bad += 1
            print(f"[{'ok ' if count else 'DEAD'}] {sec['key']:<14} "
                  f"{feed['name']:<22} {count:>3} entries")
    return bad


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--no-email", action="store_true")
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()

    config = load_config()
    if args.check:
        return 1 if check_feeds(config) else 0

    cutoff = datetime.now(timezone.utc) - timedelta(hours=WINDOW_HOURS)
    watchlist = config.get("watchlist", [])
    routing = config.get("routing", {})

    all_items, failures = [], []
    for sec in config["sections"]:
        items, failed = pull(sec["feeds"], cutoff, sec["key"])
        all_items += items
        failures += failed

    all_items = dedupe(reroute(all_items, routing))
    blocks = [
        (sec["title"], rank([i for i in all_items if i["section"] == sec["key"]], watchlist))
        for sec in config["sections"]
    ]
    html = build_html(blocks, config.get("events", []), failures, watchlist)

    DOCS.mkdir(exist_ok=True)
    (DOCS / "archive").mkdir(exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    (DOCS / "index.html").write_text(html, encoding="utf-8")
    (DOCS / "archive" / f"{stamp}.html").write_text(html, encoding="utf-8")
    print("Built: " + ", ".join(f"{t} {len(i)}" for t, i in blocks))

    if not args.no_email:
        send_email(html)
    return 0


if __name__ == "__main__":
    sys.exit(main())

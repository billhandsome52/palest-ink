#!/usr/bin/env python3
"""Palest Ink - AliDocs Tab Content Collector

Reads content from open alidocs.dingtalk.com tabs in Chrome using AppleScript.
Because alidocs requires SSO authentication and is a JS-rendered SPA, standard
HTTP fetching fails. This collector reads the already-rendered content directly
from Chrome tabs (which have valid auth sessions), then backfills the content
into matching web_visit records in the JSONL data files.
"""

import json
import os
import re
import subprocess
import tempfile
from datetime import datetime, timedelta, timezone

PALEST_INK_DIR = os.path.expanduser("~/.palest-ink")
CONFIG_FILE = os.path.join(PALEST_INK_DIR, "config.json")
DATA_DIR = os.path.join(PALEST_INK_DIR, "data")

STOP_WORDS = {
    "the", "a", "an", "is", "are", "was", "were", "be", "been", "being",
    "have", "has", "had", "do", "does", "did", "will", "would", "shall",
    "should", "may", "might", "must", "can", "could", "and", "but", "or",
    "nor", "not", "so", "yet", "for", "of", "in", "on", "at", "to", "from",
    "by", "with", "as", "this", "that", "these", "those", "it", "its",
    "的", "了", "在", "是", "我", "有", "和", "就", "不", "人", "都", "一",
    "这", "中", "大", "为", "上", "个", "国", "他", "到", "说", "们", "会",
}

# JavaScript to extract document content from an alidocs page.
# Tries alidocs-specific selectors first, falls back to body.
# Uses single quotes throughout to avoid conflicts with AppleScript double quotes.
_JS_EXTRACT = (
    "(function(){"
    "var s=['.lark-editor-container','.alidoc-editor','.doc-content',"
    "'.editor-content','article','main'];"
    "for(var i=0;i<s.length;i++){"
    "var e=document.querySelector(s[i]);"
    "if(e&&e.innerText&&e.innerText.trim().length>50)"
    "return document.title+'|||'+e.innerText.substring(0,3000);"
    "}"
    "return document.title+'|||'+document.body.innerText.substring(0,3000);"
    "})()"
)


def _build_applescript():
    """Build the AppleScript string.

    _JS_EXTRACT uses only single quotes so it can be safely embedded inside
    an AppleScript double-quoted string without any escaping.
    Returns (script_str, None) — no temp file needed.
    """
    script = (
        'tell application "Google Chrome"\n'
        '    set results to {}\n'
        '    repeat with w in windows\n'
        '        repeat with t in tabs of w\n'
        '            set tURL to URL of t\n'
        '            if tURL contains "alidocs.dingtalk.com/i/nodes/" then\n'
        '                try\n'
        f'                    set tContent to execute t javascript "{_JS_EXTRACT}"\n'
        '                    set end of results to tURL & "~|~" & tContent\n'
        '                on error errMsg\n'
        '                    set end of results to "ERROR~|~" & errMsg\n'
        '                end try\n'
        '            end if\n'
        '        end repeat\n'
        '    end repeat\n'
        "    set AppleScript's text item delimiters to \"\\n\"\n"
        '    return results as text\n'
        'end tell\n'
    )
    return script, None


def extract_keywords(text, max_keywords=10):
    words = re.findall(r'[\w\u4e00-\u9fff]{2,}', text.lower())
    freq = {}
    for w in words:
        if w not in STOP_WORDS and not w.isdigit():
            freq[w] = freq.get(w, 0) + 1
    sorted_words = sorted(freq.items(), key=lambda x: x[1], reverse=True)
    return [w for w, _ in sorted_words[:max_keywords]]


def extract_node_id(url):
    """Extract the node ID from an alidocs URL.

    e.g. https://alidocs.dingtalk.com/i/nodes/ABC123?params -> 'ABC123'
    """
    m = re.search(r'/i/nodes/([A-Za-z0-9]+)', url)
    return m.group(1) if m else None


def get_chrome_alidocs_tabs():
    """Return list of (url, title, content_text) tuples from open Chrome tabs.

    Requires Chrome > View > Developer > Allow JavaScript from Apple Events.
    """
    script, _ = _build_applescript()
    # Run a quick probe first: try JS on any alidocs tab to detect if the
    # Chrome "Allow JavaScript from Apple Events" feature is enabled.
    # The error only appears when JS execution is attempted.
    try:
        result = subprocess.run(
            ["osascript", "-e", script],
            capture_output=True, text=True, timeout=8
        )
    except (subprocess.TimeoutExpired, OSError):
        return []

    if result.returncode != 0 and not result.stdout.strip():
        return []

    raw = result.stdout.strip()
    flag_file = os.path.join(PALEST_INK_DIR, "tmp", "alidocs_js_disabled")

    # Detect Chrome JavaScript-from-AppleEvents disabled (error lines in output)
    js_disabled_keywords = ("Allow JavaScript from Apple Events", "Apple 事件中的 JavaScript")
    if any(kw in raw for kw in js_disabled_keywords):
        if not os.path.exists(flag_file):
            print(
                "[alidocs] Chrome JavaScript from Apple Events is disabled.\n"
                "  To enable: Chrome menu bar > View > Developer > "
                "Allow JavaScript from Apple Events"
            )
            open(flag_file, "w").close()
        return []

    # Clear the flag if JS is now working
    if os.path.exists(flag_file):
        os.unlink(flag_file)

    tabs = []
    for line in raw.splitlines():
        line = line.strip()
        if not line or "~|~" not in line:
            continue
        url_part, rest = line.split("~|~", 1)
        url_part = url_part.strip()
        # Skip error lines recorded by AppleScript
        if url_part == "ERROR":
            continue
        if "|||" in rest:
            title, content = rest.split("|||", 1)
        else:
            title, content = rest, ""
        tabs.append((url_part, title.strip(), content.strip()))
    return tabs


def load_config():
    if os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, "r") as f:
            return json.load(f)
    return {}


def update_datafile(datafile, node_id, title, content_summary, keywords):
    """Scan datafile and update all web_visit records matching node_id."""
    if not os.path.exists(datafile):
        return 0

    with open(datafile, "r") as f:
        lines = f.readlines()

    updated_count = 0
    new_lines = []

    for line in lines:
        stripped = line.strip()
        if not stripped:
            new_lines.append(line)
            continue
        try:
            record = json.loads(stripped)
        except json.JSONDecodeError:
            new_lines.append(line)
            continue

        if record.get("type") == "web_visit":
            rec_url = record.get("data", {}).get("url", "")
            rec_node = extract_node_id(rec_url)
            if rec_node and rec_node == node_id:
                data = record["data"]
                data["content_summary"] = content_summary
                data["content_keywords"] = keywords
                data["content_pending"] = False
                data["content_source"] = "alidocs_tab"
                # Update title if browser history gave a blank/generic one
                if title and (not data.get("title") or data.get("title") in ("文档", "alidocs.dingtalk")):
                    data["title"] = title
                # Clear previous error flag if present
                data.pop("content_error", None)
                new_lines.append(json.dumps(record, ensure_ascii=False) + "\n")
                updated_count += 1
                continue
        new_lines.append(line)

    if updated_count > 0:
        tmp_fd, tmp_path = tempfile.mkstemp(dir=os.path.dirname(datafile), suffix=".tmp")
        try:
            with os.fdopen(tmp_fd, "w") as f:
                f.writelines(new_lines)
            os.replace(tmp_path, datafile)
        except Exception:
            try:
                os.unlink(tmp_path)
            except OSError:
                pass

    return updated_count


def collect():
    config = load_config()
    if not config.get("collectors", {}).get("alidocs", True):
        return

    tabs = get_chrome_alidocs_tabs()
    if not tabs:
        return

    now = datetime.now(timezone.utc)
    dates_to_check = [now, now - timedelta(days=1)]

    summary_max = config.get("content_fetch", {}).get("summary_max_chars", 800)

    total_updated = 0
    seen_node_ids = set()

    for url, title, content in tabs:
        node_id = extract_node_id(url)
        if not node_id or node_id in seen_node_ids:
            continue
        seen_node_ids.add(node_id)

        if not content or len(content.strip()) < 10:
            continue

        summary = content[:summary_max]
        keywords = extract_keywords(content)

        for dt in dates_to_check:
            datafile = os.path.join(
                DATA_DIR, dt.strftime("%Y"), dt.strftime("%m"), f"{dt.strftime('%d')}.jsonl"
            )
            n = update_datafile(datafile, node_id, title, summary, keywords)
            total_updated += n

    if total_updated > 0:
        print(f"[alidocs] Updated content for {total_updated} records ({len(seen_node_ids)} docs)")


if __name__ == "__main__":
    collect()

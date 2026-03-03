#!/usr/bin/env python3
"""Palest Ink - Daily Report Generator

Generates a structured markdown daily report from activity records.

Usage:
    python3 report.py --date today
    python3 report.py --date 2026-03-03
    python3 report.py --week
"""

import argparse
import json
import os
import sys
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

LOCAL_TZ = ZoneInfo("Asia/Shanghai")

DATA_DIR = os.path.expanduser("~/.palest-ink/data")
REPORTS_DIR = os.path.expanduser("~/.palest-ink/reports")


def parse_date(s):
    s = s.strip().lower()
    today = datetime.now().date()
    if s == "today":
        return today
    elif s == "yesterday":
        return today - timedelta(days=1)
    else:
        return datetime.strptime(s, "%Y-%m-%d").date()


def load_day_records(d):
    path = os.path.join(DATA_DIR, d.strftime("%Y"), d.strftime("%m"), f"{d.strftime('%d')}.jsonl")
    records = []
    if not os.path.exists(path):
        return records
    with open(path, "r") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                records.append(json.loads(line))
            except json.JSONDecodeError:
                pass
    records.sort(key=lambda r: r.get("ts", ""))
    return records


def ts_to_local(ts_str):
    """Parse a UTC timestamp string and return local datetime."""
    try:
        dt = datetime.fromisoformat(ts_str)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(LOCAL_TZ)
    except Exception:
        return None


def ts_to_local_str(ts_str):
    """Return HH:MM in local time."""
    dt = ts_to_local(ts_str)
    if dt:
        return dt.strftime("%H:%M")
    return ts_str[11:16] if len(ts_str) >= 16 else "??:??"


def time_period(ts_str):
    """Classify a timestamp into morning/afternoon/evening."""
    dt = ts_to_local(ts_str)
    if dt is None:
        return "other"
    hour = dt.hour
    if 6 <= hour < 12:
        return "morning"
    elif 12 <= hour < 18:
        return "afternoon"
    elif 18 <= hour < 22:
        return "evening"
    else:
        return "night"





def period_label(period):
    labels = {
        "morning": "Morning (06:00 - 12:00)",
        "afternoon": "Afternoon (12:00 - 18:00)",
        "evening": "Evening (18:00 - 22:00)",
        "night": "Night (22:00 - 06:00)",
    }
    return labels.get(period, period)


def format_timeline_entry(record):
    ts = record.get("ts", "")
    time_str = ts_to_local_str(ts)
    rtype = record.get("type", "")
    data = record.get("data", {})

    if rtype == "git_commit":
        repo = os.path.basename(data.get("repo", ""))
        msg = data.get("message", "")
        files = data.get("files_changed", [])
        ins = data.get("insertions", 0)
        dels = data.get("deletions", 0)
        return f"- **{time_str}** Committed `{msg}` in {repo} ({len(files)} files, +{ins}/-{dels})"

    elif rtype == "git_push":
        repo = os.path.basename(data.get("repo", ""))
        branch = data.get("branch", "")
        return f"- **{time_str}** Pushed {repo}/{branch}"

    elif rtype == "git_pull":
        repo = os.path.basename(data.get("repo", ""))
        return f"- **{time_str}** Pulled {repo}"

    elif rtype == "git_checkout":
        repo = os.path.basename(data.get("repo", ""))
        return f"- **{time_str}** Switched to `{data.get('to_branch', '')}` in {repo}"

    elif rtype == "web_visit":
        title = data.get("title", "")[:50]
        url = data.get("url", "")
        duration = data.get("visit_duration_seconds", 0)
        suffix = f" ({duration}s)" if duration > 10 else ""
        return f"- **{time_str}** Visited [{title}]({url}){suffix}"

    elif rtype == "shell_command":
        cmd = data.get("command", "")[:80]
        return f"- **{time_str}** `{cmd}`"

    elif rtype == "vscode_edit":
        filepath = data.get("file_path", "")
        filename = os.path.basename(filepath)
        lang = data.get("language", "")
        return f"- **{time_str}** Edited `{filename}` ({lang})"

    return f"- **{time_str}** {rtype}"


def generate_report(target_date, records):
    """Generate a markdown report for a single day."""
    lines = []
    date_str = target_date.strftime("%Y-%m-%d")
    weekday = target_date.strftime("%A")
    lines.append(f"# Daily Activity Report - {date_str} ({weekday})")
    lines.append("")

    if not records:
        lines.append("No activities recorded for this day.")
        return "\n".join(lines)

    # Summary
    type_counts = defaultdict(int)
    for r in records:
        type_counts[r.get("type", "unknown")] += 1

    lines.append("## Summary")
    if type_counts.get("git_commit"):
        git_commits = [r for r in records if r.get("type") == "git_commit"]
        repos = set(os.path.basename(r.get("data", {}).get("repo", "")) for r in git_commits)
        lines.append(f"- **{type_counts['git_commit']}** git commits across **{len(repos)}** repos")
    if type_counts.get("web_visit"):
        lines.append(f"- **{type_counts['web_visit']}** web pages visited")
    if type_counts.get("shell_command"):
        lines.append(f"- **{type_counts['shell_command']}** shell commands executed")
    if type_counts.get("vscode_edit"):
        lines.append(f"- **{type_counts['vscode_edit']}** files edited in VS Code")
    lines.append("")

    # Timeline (only show significant events, not every shell command)
    significant_types = {"git_commit", "git_push", "git_pull", "git_checkout", "web_visit", "vscode_edit"}
    significant = [r for r in records if r.get("type") in significant_types]

    if significant:
        lines.append("## Timeline")
        lines.append("")

        by_period = defaultdict(list)
        for r in significant:
            period = time_period(r.get("ts", ""))
            by_period[period].append(r)

        for period in ["morning", "afternoon", "evening", "night"]:
            if period in by_period:
                lines.append(f"### {period_label(period)}")
                # Limit entries per period to avoid huge reports
                entries = by_period[period][:30]
                for r in entries:
                    lines.append(format_timeline_entry(r))
                if len(by_period[period]) > 30:
                    lines.append(f"- ... and {len(by_period[period]) - 30} more activities")
                lines.append("")

    # Git Activity Table
    git_commits = [r for r in records if r.get("type") == "git_commit"]
    if git_commits:
        lines.append("## Git Activity")
        lines.append("")
        repo_stats = defaultdict(lambda: {"commits": 0, "files": 0, "ins": 0, "dels": 0})
        for r in git_commits:
            data = r.get("data", {})
            repo = os.path.basename(data.get("repo", "unknown"))
            repo_stats[repo]["commits"] += 1
            repo_stats[repo]["files"] += len(data.get("files_changed", []))
            repo_stats[repo]["ins"] += data.get("insertions", 0)
            repo_stats[repo]["dels"] += data.get("deletions", 0)

        lines.append("| Repository | Commits | Files Changed | Lines +/- |")
        lines.append("|------------|---------|---------------|-----------|")
        for repo, stats in sorted(repo_stats.items(), key=lambda x: x[1]["commits"], reverse=True):
            lines.append(f"| {repo} | {stats['commits']} | {stats['files']} | +{stats['ins']}/-{stats['dels']} |")
        lines.append("")

    # Top Websites
    web_visits = [r for r in records if r.get("type") == "web_visit"]
    if web_visits:
        lines.append("## Top Websites")
        lines.append("")
        domain_counts = defaultdict(int)
        for r in web_visits:
            url = r.get("data", {}).get("url", "")
            try:
                from urllib.parse import urlparse
                domain = urlparse(url).netloc
                if domain:
                    domain_counts[domain] += 1
            except Exception:
                pass

        for i, (domain, count) in enumerate(
            sorted(domain_counts.items(), key=lambda x: x[1], reverse=True)[:15]
        ):
            lines.append(f"{i+1}. **{domain}** ({count} visits)")
        lines.append("")

    # VS Code Edits
    vscode_edits = [r for r in records if r.get("type") == "vscode_edit"]
    if vscode_edits:
        lines.append("## Files Edited (VS Code)")
        lines.append("")
        lang_counts = defaultdict(int)
        for r in vscode_edits:
            lang = r.get("data", {}).get("language", "unknown")
            lang_counts[lang] += 1

        for lang, count in sorted(lang_counts.items(), key=lambda x: x[1], reverse=True):
            lines.append(f"- **{lang}**: {count} files")
        lines.append("")

    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description="Palest Ink - Report Generator")
    parser.add_argument("--date", help="Date (YYYY-MM-DD, 'today', 'yesterday')")
    parser.add_argument("--week", action="store_true", help="Generate report for current week")
    parser.add_argument("--save", action="store_true", help="Save report to file")

    args = parser.parse_args()

    if args.week:
        today = datetime.now().date()
        # Go back to Monday
        start = today - timedelta(days=today.weekday())
        all_records = []
        for i in range(7):
            d = start + timedelta(days=i)
            if d > today:
                break
            all_records.extend(load_day_records(d))
        report = generate_report(today, all_records)
        report = report.replace("Daily Activity Report", "Weekly Activity Report", 1)
    else:
        target = parse_date(args.date) if args.date else datetime.now().date()
        records = load_day_records(target)
        report = generate_report(target, records)

    print(report)

    if args.save:
        os.makedirs(REPORTS_DIR, exist_ok=True)
        date_str = args.date or "today"
        if date_str == "today":
            date_str = datetime.now().strftime("%Y-%m-%d")
        report_path = os.path.join(REPORTS_DIR, f"{date_str}.md")
        with open(report_path, "w") as f:
            f.write(report)
        print(f"\nReport saved to: {report_path}")


if __name__ == "__main__":
    main()

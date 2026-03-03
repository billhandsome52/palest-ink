# Palest Ink (淡墨)

> 好记性不如烂笔头 — The faintest ink is better than the strongest memory.

A Claude Code skill that automatically tracks your daily development activities and helps you recall what you've done.

## Features

- **Git Tracking** — Automatically records commits, pushes, pulls, and branch switches via git hooks
- **Browser History** — Collects Chrome and Safari browsing history with page content summaries
- **Shell Commands** — Tracks zsh/bash command history
- **VS Code Edits** — Records recently opened/edited files
- **Daily Reports** — Generates structured summaries of your day
- **Natural Language Search** — Ask Claude "which website had info about homebrew?" and get instant answers

## Installation

### 1. Install the data collectors

```bash
bash collectors/install.sh
```

This will:
- Create `~/.palest-ink/` for storing activity data
- Install git hooks globally (post-commit, post-merge, post-checkout, pre-push)
- Set up a cron job to collect browser/shell/vscode data every 3 minutes

### 2. Install as a Claude Code skill

```bash
# From the project root
claude plugins install --local .
```

Or add the path manually to your Claude Code settings.

### 3. (Optional) Add tracked git repos

For supplementary git scanning (catches commits made without hooks):

```bash
# Edit ~/.palest-ink/config.json and add repos to tracked_repos:
# "tracked_repos": ["/path/to/repo1", "/path/to/repo2"]
```

## Usage

Once installed, just talk to Claude naturally:

- **"What did I do today?"** — Generates a daily report
- **"Show my git activity this week"** — Queries git commits for the week
- **"Which website had information about homebrew installation?"** — Searches web visit content summaries
- **"Which commit modified the plugin code?"** — Searches git commits by content
- **"Show my browsing history from yesterday"** — Lists web visits
- **"What files did I edit today?"** — Shows VS Code edit records

## Data Storage

All data stays local on your machine at `~/.palest-ink/`:

```
~/.palest-ink/
├── config.json           # Configuration
├── data/YYYY/MM/DD.jsonl # Activity records (one JSON per line)
├── reports/              # Generated reports
├── hooks/                # Git hook scripts
├── bin/                  # Collector scripts
└── cron.log              # Collection log
```

## Uninstallation

```bash
bash collectors/uninstall.sh
```

This removes the cron job, restores git hooks, and optionally deletes collected data.

## Privacy

- All data is stored locally — nothing leaves your machine
- URL exclusion patterns filter out internal/sensitive pages
- Command exclusion patterns filter out noise (ls, cd, etc.)
- Configure exclusions in `~/.palest-ink/config.json`

## Configuration

Edit `~/.palest-ink/config.json`:

```json
{
  "collectors": {
    "chrome": true,
    "safari": true,
    "shell": true,
    "vscode": true,
    "git_hooks": true,
    "git_scan": true,
    "content": true
  },
  "exclude_patterns": {
    "urls": ["chrome://", "about:"],
    "commands": ["^ls$", "^cd "]
  },
  "content_fetch": {
    "max_urls_per_run": 50,
    "summary_max_chars": 800,
    "timeout_seconds": 10
  }
}
```

## License

MIT

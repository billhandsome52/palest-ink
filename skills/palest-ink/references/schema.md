# Palest Ink Data Schema

## Storage Location

All activity data is stored at `~/.palest-ink/data/YYYY/MM/DD.jsonl`.
Each file contains one day's activities, one JSON record per line.

## Record Format

Every record has the same top-level structure:

```json
{
  "ts": "2026-03-03T14:22:31Z",
  "type": "git_commit",
  "source": "git_hook",
  "data": { ... }
}
```

| Field | Type | Description |
|-------|------|-------------|
| `ts` | string | ISO 8601 timestamp |
| `type` | string | Activity type (see below) |
| `source` | string | Which collector produced this record |
| `data` | object | Type-specific data fields |

## Activity Types

### git_commit
Source: `git_hook` or `git_scan`

```json
{
  "repo": "/Users/xuyun/my-project",
  "branch": "main",
  "hash": "a1b2c3d",
  "message": "Fix login validation bug",
  "files_changed": ["src/auth.py", "tests/test_auth.py"],
  "insertions": 42,
  "deletions": 15
}
```

### git_push
Source: `git_hook`

```json
{
  "repo": "/Users/xuyun/my-project",
  "branch": "main",
  "remote": "origin",
  "remote_url": "git@github.com:user/repo.git"
}
```

### git_pull
Source: `git_hook`

```json
{
  "repo": "/Users/xuyun/my-project",
  "branch": "main",
  "is_squash": false
}
```

### git_checkout
Source: `git_hook`

```json
{
  "repo": "/Users/xuyun/my-project",
  "from_ref": "main",
  "to_branch": "feature/auth"
}
```

### web_visit
Source: `chrome_collector` or `safari_collector`

```json
{
  "url": "https://brew.sh/",
  "title": "Homebrew — The Missing Package Manager for macOS",
  "visit_duration_seconds": 120,
  "browser": "chrome",
  "content_summary": "Homebrew installs the stuff you need...",
  "content_keywords": ["homebrew", "package manager", "macOS", "install"],
  "content_pending": false
}
```

**Content fields:**
- `content_pending`: `true` if content hasn't been fetched yet
- `content_summary`: First 800 chars of extracted page text
- `content_keywords`: Top 10 keywords extracted from page content
- `content_error`: `true` if content fetch failed

### shell_command
Source: `shell_collector`

```json
{
  "command": "git log --oneline -5"
}
```

### vscode_edit
Source: `vscode_collector`

```json
{
  "file_path": "/Users/xuyun/project/src/main.py",
  "workspace": "/Users/xuyun/project",
  "language": "python",
  "is_folder": false
}
```

## Configuration

Config file: `~/.palest-ink/config.json`

Key fields:
- `collectors`: Enable/disable individual collectors
- `tracked_repos`: List of git repo paths for git_scan collector
- `exclude_patterns.urls`: URL prefixes to ignore
- `exclude_patterns.commands`: Regex patterns for commands to ignore
- `content_fetch.max_urls_per_run`: Max URLs to fetch per collection cycle
- `content_fetch.summary_max_chars`: Max chars for content summary

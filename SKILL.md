---
name: discord-low-info-users
description: Analyze Discord channel messages to find users with high activity but low information content. Use when the user asks to filter noisy users, find spam accounts, identify low-quality contributors, or build an ignore list for a Discord channel.
---

# Discord Low-Info Users Analyzer

Find users who post frequently but contribute little information — ideal for building ignore lists.

## Quick Start

```bash
python3 ~/.claude/skills/discord-low-info-users/analyze.py <channel> [--days N] [--min-msgs N] [--min-low-info PCT] [--exclude user1 user2]
```

## Examples

```bash
# Find noisy users in a channel (last 7 days, default thresholds)
python3 analyze.py my-channel-alias

# Last 3 days, lower threshold
python3 analyze.py my-channel-alias --days 3 --min-msgs 5 --min-low-info 70

# Exclude known KOLs / admins
python3 analyze.py my-channel-alias --exclude kol_user1 admin_user2

# Use raw channel ID instead of alias
python3 analyze.py 1234567890123456789 --days 14

# JSON output for further processing
python3 analyze.py my-channel-alias --out /tmp/report.json --quiet
```

> Channel aliases are defined in your local `~/.config/discord-cli/channels.yaml` (not shipped with this skill).

## Configuration

**All configuration is local. Nothing is hardcoded in the skill.**

- Channel aliases: `~/.config/discord-cli/channels.yaml`
- Exclude list (KOLs/admins): `~/.config/discord-low-info/exclude.json`

Create exclude list:
```bash
mkdir -p ~/.config/discord-low-info
echo '["kol_user1", "admin_user2"]' > ~/.config/discord-low-info/exclude.json
```

The script reads `exclude.json` automatically when `--exclude` is not passed.

## How It Works

1. **Fetch**: Uses `discord fetch` CLI to pull channel history
2. **Classify**: Each message is categorized by **financial information content**:
   - `empty`: no content (reactions, embeds only)
   - `signal`: contains tickers, prices, trading terms, market analysis (e.g. "SPY 550 支撑", "止损了", "earnings next week")
   - `noise`: no financial content (e.g. "哈哈哈", "ok", "😅", "晚安")
3. **Score**: Users are ranked by `messages × low_info_pct` — a user with 100 msgs at 90% low-info scores 90 (noisier than 10 msgs at 100% = 10)
4. **Filter**: Only users meeting both `--min-msgs` AND `--min-low-info` thresholds are included

### Signal Detection

Messages are classified as `signal` if they contain:
- **Ticker symbols**: `$SPY`, `NVDA`, `QQQ`, `SPX`, etc.
- **Price patterns**: `$550`, `7200点`, `15%`, etc.
- **Trading terms**: buy/sell, call/put, 止损/止盈, support/resistance, CPI/Fed, etc.
- **Chinese stock names**: 英伟达, 美光, 特斯拉, 伯克希尔, etc.

## Output

### Table (default)
```
 1. siarandomwalk (Sia)
    Msgs: 199 | Signal: 33 (16.6%) | Noise: 166 | Empty: 0 | Score: 166.0
    Latest: 06-24 21:27 ET - "看看access问题去"
    ✅ 但如果按照买强者 高反弹的想法的话
    ❌ 看看access问题去
```

### JSON (--quiet)
```json
{
  "channel": "tradingroom",
  "total_messages": 5000,
  "unique_users": 170,
  "time_range": { "from": "...", "to": "...", "hours": 15.1 },
  "low_info_users": [
    {
      "username": "siarandomwalk",
      "global_name": "Sia",
      "total_msgs": 199,
      "signal": 33,
      "noise": 166,
      "signal_pct": 16.6,
      "low_info_pct": 83.4,
      "score": 166.0,
      "signal_samples": ["但如果按照买强者..."],
      "noise_samples": ["看看access问题去"],
      "latest_msg": "...",
      "latest_time": "06-24 21:27 ET"
    }
  ]
}
```

## Parameters

| Param | Default | Description |
|-------|---------|-------------|
| `channel` | required | Channel ID or alias from `~/.config/discord-cli/channels.yaml` |
| `--days` | 7 | Fetch messages from last N days |
| `--hours` | 0 | Fetch messages from last N hours (overrides --days) |
| `--min-msgs` | 10 | Minimum messages to be considered |
| `--min-low-info` | 80.0 | Minimum low-info percentage (empty + noise) |
| `--exclude` | [] | Usernames to skip (e.g. KOLs, admins) |
| `--top` | 30 | Max users to output |
| `--out` | - | Write JSON report to file |
| `--quiet` | false | Suppress table, only output JSON |

## Typical Workflow

1. Run analyzer on target channel
2. Review output — exclude KOLs/admins who are noisy but important
3. In Discord app: right-click user → Ignore for each target
4. Re-run periodically to catch new noise accounts

## Dependencies

- `discord` CLI installed at `~/.local/bin/discord`
- CDP endpoint running (Chrome with Discord logged in)
- Channel configured in `~/.config/discord-cli/channels.yaml`

## Notes

- Discord API returns max 100 msgs per request; the CLI paginates automatically
- Very active channels (>200 msgs/hour) may only cover hours, not days
- The "ignore" feature is Discord client-side only — this tool identifies targets, you click ignore manually
- Excluding KOLs is recommended: they may be "noisy" but carry signal weight

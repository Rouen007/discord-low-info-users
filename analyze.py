#!/usr/bin/env python3
"""
Analyze Discord channel messages to find users with high activity but low information content.

Usage:
  python3 analyze.py <channel_id_or_alias> [--days N | --hours N] [--min-msgs N] [--min-low-info PCT] [--out PATH]

Output: JSON report of low-info active users, sorted by (messages * low_info_pct).
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from collections import defaultdict
from datetime import datetime, timezone, timedelta
from pathlib import Path

# Reuse discord CLI for fetching
DISCORD_CLI = str(Path.home() / ".local" / "bin" / "discord")


def fetch_messages(channel: str, days: float = 0, hours: float = 0) -> list[dict]:
    """Fetch messages using the discord CLI."""
    cmd = [DISCORD_CLI, "fetch", channel]
    if days > 0:
        cmd += ["--days", str(int(days))]
    elif hours > 0:
        cmd += ["--hours", str(int(hours))]
    else:
        cmd += ["--days", "7"]  # default 7 days

    cmd += ["--out", "/tmp/discord_low_info_fetch.json"]

    env = os.environ.copy()
    env.setdefault("OPENCLI_CDP_ENDPOINT", "http://127.0.0.1:9222")

    result = subprocess.run(cmd, capture_output=True, text=True, env=env, timeout=300)
    if result.returncode != 0:
        print(f"Error fetching messages: {result.stderr}", file=sys.stderr)
        sys.exit(1)

    with open("/tmp/discord_low_info_fetch.json") as f:
        return json.load(f)


import re

# Ticker patterns: $SPY, NVDA, QQQ, SPX, etc.
TICKER_RE = re.compile(
    r'\$?[A-Z]{1,5}\b|'  # $SPY, NVDA
    r'\bSPX\b|\bSPY\b|\bQQQ\b|\bNDX\b|\bDJI\b|\bSOXX\b|\bSMH\b|\bVIX\b'  # index/ETF
)

# Price patterns: $550, 550.5, 7200点, etc.
PRICE_RE = re.compile(r'\$?\d{2,5}(?:\.\d+)?(?:\s*[点元块刀%]|(?:\s*(?:support|resistance|target|stop))?)')

# Trading terms
TRADING_TERMS = {
    # actions
    'buy', 'sell', 'long', 'short', 'cover', 'close', 'open', 'add', 'trim', 'exit', 'enter',
    '追', '抄底', '割肉', '建仓', '加仓', '减仓', '清仓', '止损', '止盈', '梭哈', 'all in',
    # derivatives
    'call', 'put', 'option', '期权', '末日', '蝶', 'butterfly', 'condor', 'spread',
    'leap', '0dte', '1dte', 'dte', 'expiry', '到期',
    # analysis
    'support', 'resistance', 'breakout', 'breakdown', 'trend', 'vwap', 'ema', 'sma',
    'macd', 'rsi', 'gamma', 'delta', 'theta', 'vega', 'greeks', 'gex', 'dex',
    '支撑', '阻力', '突破', '跌破', '趋势', '背离', '超买', '超卖',
    # market
    'earnings', '财报', 'eps', 'revenue', 'guidance', 'forward pe',
    'fed', 'fomc', 'cpi', 'pce', 'ppi', '非农', 'nfp', 'pmi', 'gdp',
    'inflation', '通胀', '降息', '加息', '利率', 'rate', 'yield', 'bond',
    '股价', '市值', '估值', 'pe', 'pb', 'roe',
    # sentiment
    'bull', 'bear', '多头', '空头', '牛市', '熊市', '震荡', '回调', '回撤', '反弹',
    'hedge', '对冲', '避险', '止损', '爆仓', 'margin',
    # well-known stocks (Chinese names)
    '伯克希尔', '英伟达', '苹果', '特斯拉', '谷歌', '亚马逊', '微软', '脸书', '台积电',
    '美光', '高通', '英特尔', 'AMD', '博通', 'ARM',
}

# Market events / emojis that carry signal
SIGNAL_EMOJIS = {'🚀', '📉', '📈', '💰', '🔥', '⚠️', '🎯', '✅', '❌', '💪', '🐻', '🐂'}


def has_financial_content(content: str) -> bool:
    """Check if a message contains financial/trading information."""
    text = content.strip()
    if not text:
        return False

    lower = text.lower()

    # Check tickers
    if TICKER_RE.search(text):
        return True

    # Check price patterns
    if PRICE_RE.search(text):
        return True

    # Check trading terms
    for term in TRADING_TERMS:
        if term in lower:
            return True

    return False


def classify_message(content: str) -> str:
    """Classify a message by financial information content.

    Returns:
        'empty': no content
        'noise': no financial info (emoji, lol, ok, off-topic)
        'signal': contains financial/trading content
    """
    text = content.strip()
    if len(text) == 0:
        return "empty"

    if has_financial_content(text):
        return "signal"

    return "noise"


def analyze_users(messages: list[dict]) -> dict:
    """Analyze messages by user."""
    users = defaultdict(lambda: {
        "global_name": "",
        "total": 0,
        "empty": 0,
        "noise": 0,
        "signal": 0,
        "chars": 0,
        "signal_samples": [],
        "noise_samples": [],
        "latest_msg": None,
        "latest_ts": None,
    })

    for msg in messages:
        author = msg.get("author", {})
        username = author.get("username", "unknown")
        global_name = author.get("global_name", "")
        content = msg.get("content", "")
        ts = msg.get("timestamp", "")

        u = users[username]
        u["global_name"] = global_name or username
        u["total"] += 1
        u["chars"] += len(content.strip())

        category = classify_message(content)
        u[category] += 1

        # Save samples
        if content.strip():
            if category == "signal" and len(u["signal_samples"]) < 5:
                u["signal_samples"].append(content[:80].replace("\n", " "))
            elif category == "noise" and len(u["noise_samples"]) < 5:
                u["noise_samples"].append(content[:80].replace("\n", " "))

        # Track latest message
        if ts and (u["latest_ts"] is None or ts > u["latest_ts"]):
            u["latest_ts"] = ts
            u["latest_msg"] = content[:60].replace("\n", " ")

    return dict(users)


def filter_low_info(
    users: dict,
    min_msgs: int = 10,
    min_low_info_pct: float = 80.0,
    exclude_users: list[str] | None = None,
) -> list[dict]:
    """Filter and rank low-info active users.

    Low-info = empty + noise (messages with no financial content).
    Signal = messages containing tickers, prices, trading terms, analysis.
    """
    exclude = set(exclude_users or [])
    results = []

    for username, stats in users.items():
        if username in exclude:
            continue
        if stats["total"] < min_msgs:
            continue

        low_info = stats["empty"] + stats["noise"]
        low_info_pct = (low_info / stats["total"] * 100) if stats["total"] > 0 else 0

        if low_info_pct < min_low_info_pct:
            continue

        avg_chars = stats["chars"] / stats["total"] if stats["total"] > 0 else 0
        signal_pct = (stats["signal"] / stats["total"] * 100) if stats["total"] > 0 else 0

        # Parse latest timestamp
        latest_et = ""
        if stats["latest_ts"]:
            try:
                dt = datetime.fromisoformat(stats["latest_ts"].replace("Z", "+00:00"))
                latest_et = dt.astimezone(timezone(timedelta(hours=-4))).strftime("%m-%d %H:%M ET")
            except Exception:
                latest_et = stats["latest_ts"]

        results.append({
            "username": username,
            "global_name": stats["global_name"],
            "total_msgs": stats["total"],
            "avg_chars": round(avg_chars, 1),
            "low_info_pct": round(low_info_pct, 1),
            "signal_pct": round(signal_pct, 1),
            "empty": stats["empty"],
            "noise": stats["noise"],
            "signal": stats["signal"],
            "signal_samples": stats["signal_samples"][:3],
            "noise_samples": stats["noise_samples"][:3],
            "latest_msg": stats["latest_msg"],
            "latest_time": latest_et,
            # Score: more msgs + higher low-info% = worse
            "score": round(stats["total"] * low_info_pct / 100, 1),
        })

    # Sort by score descending (most noisy first)
    results.sort(key=lambda x: -x["score"])
    return results


EXCLUDE_CONFIG = Path.home() / ".config" / "discord-low-info" / "exclude.json"


def load_exclude_list() -> list[str]:
    """Load exclude list from local config file."""
    try:
        if EXCLUDE_CONFIG.exists():
            return json.loads(EXCLUDE_CONFIG.read_text())
    except Exception:
        pass
    return []


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("channel", help="Channel ID or alias from channels.yaml")
    parser.add_argument("--days", type=float, default=0, help="Fetch messages from last N days")
    parser.add_argument("--hours", type=float, default=0, help="Fetch messages from last N hours")
    parser.add_argument("--min-msgs", type=int, default=10, help="Minimum messages to be considered (default: 10)")
    parser.add_argument("--min-low-info", type=float, default=80.0, help="Minimum low-info %% (default: 80)")
    parser.add_argument("--exclude", nargs="*", default=None, help="Usernames to exclude (default: read from ~/.config/discord-low-info/exclude.json)")
    parser.add_argument("--top", type=int, default=30, help="Max users to show (default: 30)")
    parser.add_argument("--out", help="Write JSON report to PATH")
    parser.add_argument("--quiet", action="store_true", help="Only output JSON, no table")
    args = parser.parse_args()

    # Load exclude list: CLI args > local config file
    if args.exclude is None:
        args.exclude = load_exclude_list()

    # Default to 7 days if neither specified
    if args.days == 0 and args.hours == 0:
        args.days = 7

    print(f"Fetching messages from {args.channel}...", file=sys.stderr)
    messages = fetch_messages(args.channel, days=args.days, hours=args.hours)
    print(f"Got {len(messages)} messages", file=sys.stderr)

    # Analyze
    users = analyze_users(messages)
    results = filter_low_info(
        users,
        min_msgs=args.min_msgs,
        min_low_info_pct=args.min_low_info,
        exclude_users=args.exclude,
    )

    # Time range
    timestamps = []
    for msg in messages:
        ts = msg.get("timestamp")
        if ts:
            try:
                timestamps.append(datetime.fromisoformat(ts.replace("Z", "+00:00")))
            except Exception:
                pass
    timestamps.sort()

    ET = timezone(timedelta(hours=-4))
    report = {
        "channel": args.channel,
        "total_messages": len(messages),
        "unique_users": len(users),
        "time_range": {
            "from": timestamps[0].astimezone(ET).strftime("%Y-%m-%d %H:%M ET") if timestamps else "",
            "to": timestamps[-1].astimezone(ET).strftime("%Y-%m-%d %H:%M ET") if timestamps else "",
            "hours": round((timestamps[-1] - timestamps[0]).total_seconds() / 3600, 1) if len(timestamps) > 1 else 0,
        },
        "filter": {
            "min_msgs": args.min_msgs,
            "min_low_info_pct": args.min_low_info,
            "excluded": args.exclude,
        },
        "low_info_users": results[:args.top],
    }

    # Save JSON if requested
    if args.out:
        with open(args.out, "w") as f:
            json.dump(report, f, ensure_ascii=False, indent=2)
        print(f"Report saved to {args.out}", file=sys.stderr)

    # Print table unless quiet
    if not args.quiet:
        print(f"\n{'='*80}")
        print(f"Channel: {args.channel} | Messages: {len(messages)} | Users: {len(users)}")
        print(f"Time: {report['time_range']['from']} → {report['time_range']['to']} ({report['time_range']['hours']}h)")
        print(f"Filter: >= {args.min_msgs} msgs, >= {args.min_low_info}% low-info")
        if args.exclude:
            print(f"Excluded: {', '.join(args.exclude)}")
        print(f"{'='*80}\n")

        for i, u in enumerate(results[:args.top], 1):
            print(f"{i:2}. {u['username']} ({u['global_name']})")
            print(f"    Msgs: {u['total_msgs']} | Signal: {u['signal']} ({u['signal_pct']}%) | Noise: {u['noise']} | Empty: {u['empty']} | Score: {u['score']}")
            print(f"    Latest: {u['latest_time']} - \"{u['latest_msg']}\"")
            if u['signal_samples']:
                print(f"    ✅ Signal: {u['signal_samples'][:2]}")
            if u['noise_samples']:
                print(f"    ❌ Noise: {u['noise_samples'][:2]}")
            print()

    # Always output JSON to stdout
    if args.quiet:
        print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()

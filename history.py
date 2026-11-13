"""Rolling 7-day signal log (data/signal_history.json), committed with each report.

Every qualifying flip is recorded the first time a scan sees it, then its status is refreshed
on each run until it is older than HISTORY_DAYS. The report itself is rebuilt from price data,
so even a skipped scan day does not lose a signal; this file is the written record.
"""
import json
import os
from datetime import datetime, timedelta

import config

FIELDS = ("market", "ticker", "name", "side", "flip_date", "entry", "stop", "target", "target_pct",
          "score", "grade", "status", "verdict", "r_now", "pct_now", "left_pct", "late_rr")


def _load() -> dict:
    try:
        with open(config.HISTORY_FILE, encoding="utf-8") as fh:
            return {r["key"]: r for r in json.load(fh).get("signals", [])}
    except (FileNotFoundError, json.JSONDecodeError, KeyError, TypeError):
        return {}


def update(signals_by_market: dict, run_date: str) -> dict:
    """Merge today's signals into the log, prune old ones, save. Returns {key: first_seen}."""
    log = _load()
    for market, sigs in signals_by_market.items():
        for s in sigs:
            key = f'{s["ticker"]}|{s["side"]}|{s["flip_date"]}'
            rec = log.get(key, {"key": key, "first_seen": run_date})
            rec.update({k: (round(s[k], 4) if isinstance(s.get(k), float) else s.get(k))
                        for k in FIELDS if k != "market"})
            rec.update({"market": market, "last_updated": run_date})
            log[key] = rec

    cutoff = (datetime.strptime(run_date, "%Y-%m-%d") - timedelta(days=config.HISTORY_DAYS - 1)).strftime("%Y-%m-%d")
    kept = sorted((r for r in log.values() if r["flip_date"] >= cutoff),
                  key=lambda r: (r["flip_date"], r["ticker"]), reverse=True)
    os.makedirs(os.path.dirname(config.HISTORY_FILE), exist_ok=True)
    with open(config.HISTORY_FILE, "w", encoding="utf-8") as fh:
        json.dump({"updated": run_date, "days_kept": config.HISTORY_DAYS, "signals": kept}, fh, indent=2)
    return {r["key"]: r["first_seen"] for r in kept}

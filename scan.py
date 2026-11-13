"""ETF Supertrend Scanner.

    python scan.py                 # scan + backtest, both markets
    python scan.py --market US     # one market only (US, IN or CRYPTO)
    python scan.py --no-backtest   # faster, quality score uses neutral backtest edge
"""
import argparse
import csv
import glob
import os
import shutil
import time
from dataclasses import asdict
from datetime import datetime, timezone

import config
import history
import report
from backtest import aggregate, run_backtest
from data import fetch_history, load_universe
from signals import enrich, find_signals, rank, snapshot


def run_market(key: str, do_backtest: bool, fetch=fetch_history):
    market = config.MARKETS[key]
    universe = load_universe(market["file"])
    snaps, signals, infos, backtests, failed = {}, [], [], {}, []
    pooled, pooled_u, trade_log = [], [], []
    print(f"\n{market['label']}: {len(universe)} tickers")

    for _, meta in universe.iterrows():
        t = meta["ticker"]
        print(f"  {t}")
        raw = fetch(t)
        time.sleep(config.FETCH_DELAY_SEC)
        if raw is not None and market.get("drop_partial_bar") and raw.index[-1].date() >= datetime.now(timezone.utc).date():
            raw = raw.iloc[:-1]  # today's candle hasn't closed yet
        if raw is None or raw.empty:
            failed.append(t)
            continue
        df = enrich(raw)
        snaps[t] = snapshot(df)
        if not meta["signal_eligible"]:
            continue

        edge = {}
        if do_backtest:
            trades, m = run_backtest(df, t, market["allow_shorts"], use_filter=True)
            trades_u, mu = run_backtest(df, t, market["allow_shorts"], use_filter=False)
            backtests[t] = (m, mu)
            pooled += trades
            pooled_u += trades_u
            trade_log += [asdict(x) for x in trades]
            edge = {"long": m["long"], "short": m["short"]}

        sigs, info = find_signals(df, meta.to_dict(), market, edge)
        signals += sigs
        if info:
            infos.append(info)

    return {
        "market": market, "universe": universe, "snaps": snaps, "signals": rank(signals),
        "infos": infos, "backtests": backtests, "agg": aggregate(pooled),
        "agg_unfiltered": aggregate(pooled_u), "failed": failed, "trade_log": trade_log,
    }


def write_trade_log(sections):
    rows = [dict(r, market=k) for k, s in sections for r in s["trade_log"]]
    if not rows:
        return
    path = os.path.join(config.REPORT_DIR, "backtest_trades_latest.csv")
    with open(path, "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)


def cleanup_reports():
    files = sorted(glob.glob(os.path.join(config.REPORT_DIR, "etf_supertrend_*.html")))
    for old in files[: max(len(files) - config.KEEP_REPORTS, 0)]:
        os.remove(old)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--market", choices=["US", "IN", "CRYPTO", "ALL"], default="ALL")
    ap.add_argument("--no-backtest", action="store_true")
    args = ap.parse_args()

    keys = list(config.MARKETS) if args.market == "ALL" else [args.market]
    sections = [(k, run_market(k, not args.no_backtest)) for k in keys]
    failed = [t for _, s in sections for t in s["failed"]]

    run_date = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    history.update({k: s["signals"] for k, s in sections}, run_date)
    html = report.build(run_date, [s for _, s in sections], failed)
    os.makedirs(config.REPORT_DIR, exist_ok=True)
    out = os.path.join(config.REPORT_DIR, f"etf_supertrend_{run_date}.html")
    with open(out, "w", encoding="utf-8") as fh:
        fh.write(html)
    shutil.copyfile(out, "index.html")  # GitHub Pages serves the latest report
    write_trade_log(sections)
    cleanup_reports()

    n_sig = sum(len(s["signals"]) for _, s in sections)
    print(f"\nReport: {out}  ({n_sig} ranked flips, {len(failed)} tickers without data)")


if __name__ == "__main__":
    main()

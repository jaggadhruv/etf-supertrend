"""Self-contained HTML report."""
from html import escape

import config
from backtest import BREAKEVEN_WIN_RATE

PART_LABELS = {"volume": "Volume", "trend": "Trend", "adx": "ADX", "momentum": "Momentum",
               "target": "Move size", "risk": "Stop tightness", "edge": "Backtest edge"}
PART_SHADES = {"volume": 1.0, "trend": .82, "adx": .66, "momentum": .52, "target": .40, "risk": .30, "edge": .22}

CSS = """
:root{--paper:#F4F6F5;--panel:#FFFFFF;--ink:#18211E;--muted:#5D6A65;--rule:#D8DED9;
--accent:36,80,122;--long:#2E7A4E;--short:#A63F38;--flat:#8C918E;--tint-long:#E6F0EA;--tint-short:#F5E7E5;--tint-flat:#ECEEEC}
@media (prefers-color-scheme:dark){:root{--paper:#121715;--panel:#1A201E;--ink:#E4E9E6;--muted:#9AA6A1;
--rule:#2C3532;--accent:120,165,210;--long:#5DB582;--short:#E07D74;--flat:#7F8784;--tint-long:#1E2E25;
--tint-short:#33201E;--tint-flat:#232927}}
*{box-sizing:border-box}
body{margin:0;background:var(--paper);color:var(--ink);font:15px/1.5 "Source Sans 3","Segoe UI",system-ui,sans-serif;
font-variant-numeric:tabular-nums}
.wrap{max-width:1120px;margin:0 auto;padding:32px 20px 64px}
header h1{font-size:30px;line-height:1.15;margin:0 0 4px;font-weight:700;letter-spacing:-.01em}
header p{margin:0;color:var(--muted)}
h2{font-size:22px;margin:48px 0 4px;font-weight:700}
h3{font-size:17px;margin:28px 0 8px;font-weight:600}
.sub{color:var(--muted);margin:0 0 14px;max-width:74ch}
.board{display:grid;grid-template-columns:repeat(auto-fill,minmax(168px,1fr));gap:10px}
.tile{background:var(--panel);border:1px solid var(--rule);border-top:5px solid var(--flat);border-radius:6px;padding:10px 12px}
.tile.up{border-top-color:var(--long)}.tile.down{border-top-color:var(--short)}
.tile .hd{display:flex;justify-content:space-between;align-items:baseline;gap:8px}.tile b{font-size:16px}.tile .px{color:var(--muted);font-size:14px}
.tile .ln{font-size:13px;color:var(--muted)}
.tile .st-up{color:var(--long);font-weight:600}.tile .st-down{color:var(--short);font-weight:600}
.tile.off{opacity:.55}
.tw{overflow-x:auto;background:var(--panel);border:1px solid var(--rule);border-radius:6px}
table{border-collapse:collapse;width:100%;font-size:14px}
th{font-weight:600;color:var(--muted);text-align:right;padding:9px 8px;border-bottom:1px solid var(--rule);vertical-align:bottom;line-height:1.25}
td{padding:9px 8px;border-bottom:1px solid var(--rule);text-align:right;white-space:nowrap}
tr.main td{border-bottom:0;padding-bottom:2px}
tr.note td{padding-top:0;font-size:13px;color:var(--muted);white-space:normal;text-align:left}
th:first-child,td:first-child,th.l,td.l{text-align:left}
tr:last-child td{border-bottom:0}
.long{color:var(--long);font-weight:600}.short{color:var(--short);font-weight:600}
.pill{display:inline-block;padding:1px 8px;border-radius:10px;font-size:12px;font-weight:600;background:var(--tint-flat)}
.pill.A{background:var(--tint-long);color:var(--long)}.pill.D{background:var(--tint-short);color:var(--short)}
.vd{font-weight:600;font-size:13px}.vd.go{color:var(--long)}.vd.wait{color:var(--muted)}.vd.won{color:var(--long);font-weight:400}.vd.lost{color:var(--short);font-weight:400}
tr.done td{color:var(--muted)}
.bar{display:flex;width:96px;height:7px;border-radius:2px;overflow:hidden;background:var(--tint-flat);margin:5px 0 0 auto}
.bar span{display:block;height:100%}
.legend{display:flex;flex-wrap:wrap;gap:14px;font-size:13px;color:var(--muted);margin:8px 0 0}
.legend i{display:inline-block;width:10px;height:10px;border-radius:2px;margin-right:5px;vertical-align:-1px}
.notes{font-size:13px;color:var(--muted);white-space:normal;text-align:left;min-width:220px}
.empty{background:var(--panel);border:1px dashed var(--rule);border-radius:6px;padding:16px;color:var(--muted)}
ul.plain{margin:0;padding-left:18px}ul.plain li{margin:3px 0}
.pos{color:var(--long)}.neg{color:var(--short)}
.warn{color:var(--short);font-size:12px}
details{margin-top:10px}summary{cursor:pointer;color:rgb(var(--accent));font-weight:600}
summary:focus-visible,a:focus-visible{outline:2px solid rgb(var(--accent));outline-offset:2px}
.kv{display:grid;grid-template-columns:repeat(auto-fill,minmax(210px,1fr));gap:6px 20px;font-size:14px;margin:10px 0}
.kv div span{color:var(--muted)}
footer{margin-top:56px;color:var(--muted);font-size:13px;max-width:80ch}
"""


def _sentence(notes):
    txt = "; ".join(notes)
    return (txt[:1].upper() + txt[1:]) if txt else "Clean setup"


def f(x, nd=2, suffix="", plus=False):
    if x is None:
        return "–"
    x = round(x, nd) + 0.0  # avoid "-0.00"
    s = f"{x:+,.{nd}f}" if plus else f"{x:,.{nd}f}"
    return s + suffix


def money(x, cur):
    return "–" if x is None else f"{cur}{x:,.2f}"


def cls_sign(x):
    return "" if x is None else ("pos" if x > 0 else "neg" if x < 0 else "")


def score_bar(parts):
    segs = "".join(
        f'<span title="{PART_LABELS[k]}: {v:.1f}" style="width:{v}%;background:rgba(var(--accent),{PART_SHADES[k]})"></span>'
        for k, v in parts.items())
    return f'<div class="bar" aria-hidden="true">{segs}</div>'


def legend():
    items = "".join(f'<span><i style="background:rgba(var(--accent),{PART_SHADES[k]})"></i>'
                    f'{PART_LABELS[k]} ({config.QUALITY_WEIGHTS[k]})</span>' for k in PART_LABELS)
    return f'<div class="legend">{items}</div>'


def board(snaps, universe):
    tiles = []
    for _, meta in universe.iterrows():
        t = meta["ticker"]
        s = snaps.get(t)
        if s is None:
            tiles.append(f'<div class="tile off"><b>{escape(t)}</b><div class="ln">no data</div></div>')
            continue
        reg = {1: "up", -1: "down"}.get(s["regime"], "flat")
        reg_txt = {1: "Uptrend", -1: "Downtrend"}.get(s["regime"], "No clear trend")
        st_txt = f'<span class="st-{"up" if s["st_dir"] == 1 else "down"}">ST {"up" if s["st_dir"] == 1 else "down"}</span>'
        since = "" if s["bars_since_flip"] is None else f', flipped {s["bars_since_flip"]}d ago'
        off = "" if meta["signal_eligible"] else " off"
        tiles.append(f'<div class="tile {reg}{off}" title="{escape(meta["name"])}"><div class="hd"><b>{escape(t.replace(".NS", ""))}</b>'
                     f'<span class="px">{s["close"]:,.2f}</span></div><div class="ln">{reg_txt}</div>'
                     f'<div class="ln">{st_txt}{since}</div></div>')
    return f'<div class="board">{"".join(tiles)}</div>'


VERDICT_CLASS = {"Enter at next open": "go", "Can still enter": "go", "Moved on, skip": "wait",
                 "Supertrend flipped back": "wait", "Closed at target": "won", "Closed at stop": "lost"}


def signals_table(sigs, cur):
    if not sigs:
        return ('<div class="empty">No trend-aligned flips with a big enough target in the last '
                f'{config.HISTORY_DAYS} days. Nothing to act on.</div>')
    cols = 11
    head = ("<tr><th>#</th><th class=l>ETF</th><th class=l>Side</th><th>Flip</th>"
            "<th>Entry</th><th>Stop</th><th>Target 2R</th><th>Result / now</th>"
            "<th>Left to target<br>late R:R</th><th class=l>Verdict</th><th>Quality</th></tr>")
    rows = []
    for n, s in enumerate(sigs, 1):
        vc = VERDICT_CLASS.get(s["verdict"], "wait")
        done = vc in ("won", "lost") or s["verdict"] == "Supertrend flipped back"
        entry = money(s["entry"], cur) + ("*" if s["entry_pending"] else "")
        late = ("–" if s["left_pct"] is None else
                f'{f(s["left_pct"], 1, "%", True)}<br><span class=sub>{f(s["late_rr"], 1)}:1</span>')
        tech = f'Vol {f(s["vol_ratio"], 1)}x, RSI {f(s["rsi"], 0)}, ADX {f(s["adx"], 0)}'
        rows.append(
            f'<tr class="main{" done" if done else ""}"><td>{n}</td>'
            f'<td class=l title="{escape(s["name"])}"><b>{escape(s["ticker"].replace(".NS", ""))}</b></td>'
            f'<td class="l {s["side"].lower()}">{s["side"]}</td>'
            f'<td>{s["flip_date"]}<br><span class=sub>{s["age"]}d ago</span></td>'
            f'<td>{entry}</td><td>{money(s["stop"], cur)}<br><span class=sub>{f(-s["stop_pct"], 1, "%")}</span></td>'
            f'<td>{money(s["target"], cur)}<br><span class=sub>{f(s["target_pct"], 1, "%", True)}</span></td>'
            f'<td class="{cls_sign(s["r_now"])}">{f(s["r_now"], 2, "R", True)}<br>'
            f'<span class=sub>{f(s["pct_now"], 1, "%", True)}</span></td>'
            f'<td>{late}</td><td class="l"><span class="vd {vc}">{s["verdict"]}</span></td>'
            f'<td><b>{s["score"]:.0f}</b> <span class="pill {s["grade"]}">{s["grade"]}</span>{score_bar(s["parts"])}</td></tr>'
            f'<tr class="note{" done" if done else ""}"><td></td><td colspan="{cols - 1}">{escape(s["name"])}. {tech}. '
            f'{escape(_sentence(s["notes"]))}.</td></tr>')
    foot = ('<p class="sub" style="margin-top:8px">* Flip printed on the latest close: entry is the next open, '
            'shown at the last close for reference. Re-check the stop distance after the open.</p>')
    if not any(s["entry_pending"] for s in sigs):
        foot = ""
    return f'<div class="tw"><table>{head}{"".join(rows)}</table></div>{legend()}{foot}'


def info_list(infos):
    if not infos:
        return ""
    items = "".join(
        f'<li><b>{escape(i["ticker"].replace(".NS", ""))}</b> <span class="{i["side"].lower()}">{i["side"].lower()} flip</span> '
        f'on {i["flip_date"]}: {escape(i["reason"])}</li>' for i in infos)
    return f'<h3>Latest flip not traded</h3><ul class="plain">{items}</ul>'


def bt_table(bts, cur, allow_shorts):
    head = ("<tr><th class=l>ETF</th><th>Trades</th><th>Win rate</th><th>Expectancy</th><th>Profit factor</th>"
            "<th>Avg trade</th><th>Max DD</th><th>Loss streak</th><th>Avg hold</th><th>In market</th>"
            f"<th>System CAGR</th><th>Buy &amp; hold CAGR</th><th>No-filter exp.</th></tr>")
    rows = []
    for t, (m, mu) in bts.items():
        if m["trades"] == 0 and m["below_min"]:
            warn = f' <span class="warn">no flips with a {config.MIN_TARGET_PCT:g}%+ target</span>'
        elif m["trades"] < config.MIN_TRADES_FOR_CONFIDENCE:
            warn = ' <span class="warn">small sample</span>'
        else:
            warn = ""
        wr_cls = "" if m["win_rate"] is None else ("pos" if m["win_rate"] > BREAKEVEN_WIN_RATE else "neg")
        rows.append(
            f'<tr><td class=l><b>{escape(t.replace(".NS", ""))}</b>{warn}</td>'
            f'<td>{m["trades"]}</td><td class="{wr_cls}">{f(m["win_rate"], 1, "%")}</td>'
            f'<td class="{cls_sign(m["expectancy"])}">{f(m["expectancy"], 2, "R", True)}</td>'
            f'<td>{f(m["profit_factor"], 2)}</td><td class="{cls_sign(m["avg_ret_pct"])}">{f(m["avg_ret_pct"], 1, "%", True)}</td>'
            f'<td>{f(m["max_dd_r"], 1, "R")}</td><td>{m["max_loss_streak"] if m["max_loss_streak"] is not None else "–"}</td>'
            f'<td>{f(m["avg_bars"], 0, "d")}</td><td>{f(m["exposure"], 0, "%")}</td>'
            f'<td class="{cls_sign(m["system_cagr"])}">{f(m["system_cagr"], 1, "%")}</td>'
            f'<td class="{cls_sign(m.get("buy_hold_cagr"))}">{f(m.get("buy_hold_cagr"), 1, "%")}</td>'
            f'<td class="{cls_sign(mu["expectancy"])}">{f(mu["expectancy"], 2, "R", True)}</td></tr>')
    detail = []
    for t, (m, mu) in bts.items():
        lg, sh = m["long"], m["short"]
        side_txt = (f'<div><span>Long:</span> {lg["n"]} trades, {f(lg["win_rate"], 0, "%")} win, {f(lg["expectancy"], 2, "R", True)}</div>')
        if allow_shorts:
            side_txt += f'<div><span>Short:</span> {sh["n"]} trades, {f(sh["win_rate"], 0, "%")} win, {f(sh["expectancy"], 2, "R", True)}</div>'
        ot = m["open_trade"]
        open_txt = (f'<div><span>Open trade:</span> {ot["side"]} from {ot["entry_date"]}, {f(ot["r"], 2, "R", True)}</div>'
                    if ot else "")
        detail.append(
            f'<h3>{escape(t.replace(".NS", ""))}</h3><div class="kv"><div><span>Tested:</span> {m["start_date"] or "–"} to {m["end_date"]}</div>{side_txt}'
            f'<div><span>Avg win / loss:</span> {f(m["avg_win_pct"], 1, "%", True)} / {f(m["avg_loss_pct"], 1, "%", True)}</div>'
            f'<div><span>Total:</span> {f(m["total_r"], 1, "R", True)}</div>'
            f'<div><span>Trades per year:</span> {f(m["trades_per_year"], 1)}</div>'
            f'<div><span>Buy &amp; hold total:</span> {f(m.get("buy_hold_return"), 0, "%")}</div>'
            f'<div><span>Without trend filter:</span> {mu["trades"]} trades, {f(mu["win_rate"], 0, "%")} win, PF {f(mu["profit_factor"], 2)}</div>'
            f'{open_txt}<div><span>Flips skipped, target under {config.MIN_TARGET_PCT:g}%:</span> {m["below_min"]}</div>'
            f'<div><span>Flips skipped, opened past stop:</span> {m["skipped"]}</div></div>')
    return (f'<div class="tw"><table>{head}{"".join(rows)}</table></div>'
            f'<details><summary>Per-ETF detail</summary>{"".join(detail)}</details>')


def pooled_line(agg, agg_u):
    if not agg.get("trades"):
        return '<p class="sub">No closed trades yet.</p>'
    return (f'<p class="sub">All ETFs pooled: <b>{agg["trades"]}</b> trades, win rate <b>{agg["win_rate"]:.1f}%</b> '
            f'(break-even at 2R is {BREAKEVEN_WIN_RATE:.1f}%), expectancy <b>{agg["expectancy"]:+.2f}R</b>, '
            f'average trade <b>{agg["avg_ret_pct"]:+.1f}%</b>, '
            f'profit factor <b>{f(agg["profit_factor"], 2)}</b>. Without the trend filter: '
            f'{agg_u.get("trades", 0)} trades, expectancy {f(agg_u.get("expectancy"), 2, "R", True)}.</p>')


def build(run_date: str, sections: list, failed: list) -> str:
    regime_txt = (f"close above a rising {config.SMA_PERIOD}-day SMA (below a falling one for shorts)"
                  if config.REGIME_MODE == "sma_slope" else f"close above/below the {config.SMA_PERIOD}-day SMA")
    entry_txt = "next open" if config.ENTRY_MODE == "next_open" else "flip close"
    body = []
    for sec in sections:
        m = sec["market"]
        body.append(f'<h2>{escape(m["label"])}</h2>')
        body.append(f'<p class="sub">Trend board: top border shows the overall trend, ST shows the daily Supertrend.</p>')
        body.append(board(sec["snaps"], sec["universe"]))
        body.append(f'<h3>Signals from the last {config.HISTORY_DAYS} days</h3><p class="sub">Every trend-aligned flip with a target at least '
                    f'{config.MIN_TARGET_PCT:g}% away, so a day you skip never hides an entry. Ones you can still act on come first, '
                    f'best quality first; a late entry needs {config.LATE_ENTRY_MIN_RR:g}:1 reward to risk left from the last close.</p>')
        body.append(signals_table(sec["signals"], m["currency"]))
        body.append(info_list(sec["infos"]))
        if sec.get("backtests"):
            body.append(f'<h3>Backtest: enter on flip, exit at stop or {config.TARGET_R:g}R</h3>')
            body.append(pooled_line(sec["agg"], sec["agg_unfiltered"]))
            body.append(bt_table(sec["backtests"], m["currency"], m["allow_shorts"]))
    fail_txt = f'<p class="warn">No data for: {", ".join(map(escape, failed))}. Check the ticker on finance.yahoo.com.</p>' if failed else ""
    return f"""<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>ETF Supertrend Scanner, {run_date}</title>
<link rel="preconnect" href="https://fonts.googleapis.com"><link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Source+Sans+3:wght@400;600;700&display=swap" rel="stylesheet">
<style>{CSS}</style></head><body><div class="wrap">
<header><h1>ETF Supertrend Scanner</h1>
<p>{run_date}. Supertrend ATR {config.ATR_PERIOD}, multiplier {config.ATR_MULTIPLIER}. Flips count only with the trend: {regime_txt}. Entry at {entry_txt}, stop at the Supertrend line, target {config.TARGET_R:g}R. Daily candles only. Flips whose target is less than {config.MIN_TARGET_PCT:g}% away are skipped.</p>
{fail_txt}</header>
{"".join(body)}
<footer><p><b>Reading the backtest.</b> Expectancy is the average result per trade in R (risk units); above 0 means an edge.
With a {config.TARGET_R:g}R target you break even at a {BREAKEVEN_WIN_RATE:.1f}% win rate. Profit factor is gross wins over gross losses.
Max DD is the worst peak-to-trough run of the cumulative R curve. System CAGR compounds {config.RISK_PCT_FOR_COMPARISON:g}% account risk per trade,
so it is comparable to buy &amp; hold CAGR. "No-filter exp." is the same rules without the trend filter, to show whether the filter earns its keep.
Avg trade is the average % move captured per closed trade. The backtest applies the same {config.MIN_TARGET_PCT:g}% minimum target as the scanner.
Prices are dividend-adjusted, no commissions or slippage. Stops and targets assume the level fills except on gaps.</p></footer>
</div></body></html>"""

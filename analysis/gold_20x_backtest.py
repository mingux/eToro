"""Gold CFD at 20x on eToro: volatility stats, rule backtests and ruin Monte Carlo.

Data: analysis/data/gold_1h.json (1000 hourly candles) and gold_1d.json (500 daily candles),
pulled from GET /api/v1/market-data/instruments/18/history/candles on 2026-09-20.
Costs from POST /api/v2/trading/info/costs for $1,000 margin at 20x ($20k exposure):
spread $34.77 round trip, $2 transaction fee, overnight $4.44/night long, -$0.12/night short.
Run: python3 analysis/gold_20x_backtest.py
"""
import json, math, os, random, statistics as st

HERE = os.path.dirname(__file__)
D = json.load(open(os.path.join(HERE, "data", "gold_1d.json")))
H = json.load(open(os.path.join(HERE, "data", "gold_1h.json")))
LEV = 20
SPREAD_PCT = 34.77 / 20000
FEE = 2.0
ON_LONG = 4.44 / 20000
ON_SHORT = -0.12 / 20000


def ac(x, k):
    m = st.mean(x)
    return sum((x[i] - m) * (x[i - k] - m) for i in range(k, len(x))) / sum((v - m) ** 2 for v in x)


def stats():
    px = H[-1]["close"]
    rets = [math.log(H[i]["close"] / H[i - 1]["close"]) for i in range(1, len(H))]
    drets = [math.log(D[i]["close"] / D[i - 1]["close"]) for i in range(1, len(D))]
    print(f"hourly std {st.pstdev(rets)*100:.3f}%  daily std {st.pstdev(drets)*100:.2f}%")
    print("hourly autocorr lag1/2/24:", *(f"{ac(rets,k):+.3f}" for k in (1, 2, 24)))
    print("daily autocorr lag1/2:", *(f"{ac(drets,k):+.3f}" for k in (1, 2)))

    def touch(x_pct, n):
        hits = tot = 0
        for i in range(len(H) - n):
            e = H[i]["close"]
            lo = min(h["low"] for h in H[i + 1:i + 1 + n])
            hi = max(h["high"] for h in H[i + 1:i + 1 + n])
            tot += 1
            hits += (e - lo) / e >= x_pct / 100 or (hi - e) / e >= x_pct / 100
        return hits / tot

    for x in (1.0, 1.5, 2.5):
        print(f"P(price moves {x}% either way) 24h={touch(x,24):.2f} 72h={touch(x,72):.2f} 168h={touch(x,168):.2f}")


def run(signal, sl_pct, tp_pct, trail, label, lo=60, hi=None, frac=1.0, eq=1000.0):
    hi = hi or len(D) - 1
    peak, mdd, trades, pos, ruined = eq, 0, [], None, False
    for i in range(lo, hi):
        d, nxt = D[i], D[i + 1]
        if pos:
            s, e, hit = pos["dir"], pos["entry"], None
            if s == 1:
                if d["low"] <= pos["sl"]: hit = pos["sl"]
                elif pos["tp"] and d["high"] >= pos["tp"]: hit = pos["tp"]
                elif trail: pos["sl"] = max(pos["sl"], d["high"] * (1 - sl_pct))
            else:
                if d["high"] >= pos["sl"]: hit = pos["sl"]
                elif pos["tp"] and d["low"] <= pos["tp"]: hit = pos["tp"]
                elif trail: pos["sl"] = min(pos["sl"], d["low"] * (1 + sl_pct))
            pos["nights"] += 1
            if hit:
                ex = pos["stake"] * LEV
                pnl = s * (hit - e) / e * ex - SPREAD_PCT * ex - FEE - pos["nights"] * (ON_LONG if s == 1 else ON_SHORT) * ex
                trades.append(pnl); eq += pnl; pos = None
                peak = max(peak, eq); mdd = max(mdd, (peak - eq) / peak)
                if eq < 50: ruined = True; break
        if not pos:
            s = signal(i)
            if s:
                o = nxt["open"]
                pos = {"dir": s, "entry": o, "sl": o * (1 - s * sl_pct), "tp": o * (1 + s * tp_pct) if tp_pct else None,
                       "nights": 0, "stake": max(25, eq * frac)}
    if pos:
        ex = pos["stake"] * LEV
        eq += pos["dir"] * (D[hi]["close"] - pos["entry"]) / pos["entry"] * ex - SPREAD_PCT * ex - FEE
    wins = [t for t in trades if t > 0]
    print(f"{label:34s} n={len(trades):3d} win={len(wins)/max(1,len(trades)):.2f} final=${eq:9.0f} maxDD={mdd*100:4.0f}% {'RUINED' if ruined else ''}")


def brk(i, n):
    hi = max(x["high"] for x in D[i - n:i]); lo = min(x["low"] for x in D[i - n:i])
    return 1 if D[i]["close"] > hi else (-1 if D[i]["close"] < lo else 0)


def ma(i, n):
    return st.mean(x["close"] for x in D[i - n + 1:i + 1])


def fade(i):
    r = (D[i]["close"] - D[i - 2]["close"]) / D[i - 2]["close"]
    return -1 if r > 0.02 else (1 if r < -0.02 else 0)


def backtests():
    print(f"\nGold spot over test window: {(D[-1]['close']/D[60]['open']-1)*100:+.0f}%  (a strong bull regime; do not extrapolate)")
    rules = [
        ("20d breakout L/S, SL2.5 trail", lambda i: brk(i, 20), 0.025, None, True),
        ("50d breakout L/S, SL2.5 trail", lambda i: brk(i, 50), 0.025, None, True),
        ("10d breakout L/S, SL2.5 trail", lambda i: brk(i, 10), 0.025, None, True),
        ("20d breakout L/S, SL2.5 TP2.5", lambda i: brk(i, 20), 0.025, 0.025, False),
        ("MA20 L/S, SL2.5 trail", lambda i: 1 if D[i]["close"] > ma(i, 20) else -1, 0.025, None, True),
        ("fade 2d>2%, SL2.5 TP2.5", fade, 0.025, 0.025, False),
    ]
    for r in rules:
        run(r[1], r[2], r[3], r[4], r[0])
    random.seed(7)
    for k in range(3):
        run(lambda i: random.choice([1, -1]) if random.random() < 0.3 else 0, 0.025, 0.025, False, f"RANDOM entries #{k}")
    mid = (60 + len(D) - 1) // 2
    print("\nSplit sample (20d breakout trail):")
    run(lambda i: brk(i, 20), 0.025, None, True, "  first half", lo=60, hi=mid)
    run(lambda i: brk(i, 20), 0.025, None, True, "  second half", lo=mid)
    print("\nSizing (20d breakout trail), fraction of equity staked per trade:")
    for f in (1.0, 0.5, 0.33, 0.25):
        run(lambda i: brk(i, 20), 0.025, None, True, f"  frac={f}", frac=f)


def monte_carlo(p_win, win, loss, cost=0.037, sims=20000):
    for f in (1.0, 0.5, 0.25):
        for n in (10, 30):
            ruined, finals = 0, []
            for _ in range(sims):
                eq = 1000.0
                for _ in range(n):
                    stake = max(25, eq * f)
                    eq += (win * stake if random.random() < p_win else -loss * stake) - cost * stake
                    if eq < 50: ruined += 1; break
                finals.append(eq)
            finals.sort()
            print(f"  frac={f:4} trades={n:2d}: P(ruin)={ruined/sims:.2f} median=${finals[sims//2]:5.0f} p90=${finals[int(.9*sims)]:6.0f}")


if __name__ == "__main__":
    stats()
    backtests()
    print("\nMonte Carlo, no edge (50/50, +-50% of stake, 3.7% cost):"); monte_carlo(0.5, 0.5, 0.5)
    print("Monte Carlo, trend edge (40% win, +100%/-50% of stake):"); monte_carlo(0.4, 1.0, 0.5)

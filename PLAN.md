# Gold 20x game plan

Account: eToro real, USD. Instrument: GOLD (id 18), CFD, leverage 20. Data and costs as of 2026-09-20.
Reproduce the numbers: `python3 analysis/gold_20x_backtest.py`.

## 1. The arithmetic you are playing against

| Quantity | Value |
|---|---|
| Round-trip cost per $1,000 margin (spread + fee) | $36.77 = 3.7% of margin |
| Overnight fee, long / short, per night | $4.44 / -$0.12 (short is paid) |
| eToro max stop at 20x | 50% of margin = 2.5% price move |
| Gold hourly std / daily std | 0.26% / 1.49% |
| Daily ATR(14) | $71 = 1.6% |
| P(price moves 2.5% either way) within 24h / 72h / 7d | 15% / 46% / 94% |
| Hourly and daily return autocorrelation | ~0 (no exploitable short-term pattern) |

Consequences:
- A trade with symmetric SL/TP at the 2.5% max is a coin flip that pays 3.7% of margin to the house each time. 30 such trades at full size: 89% chance of ruin, median outcome $44 from $1,000.
- Hourly-timeframe trading is dead on arrival: cost per round trip is 66% of one hour's standard deviation.
- The only structure with positive expectancy in the data is trend capture with a trailing stop: few trades, held for days to weeks, letting winners run to 2 to 4 times the stop distance. Every mean-reversion, moving-average-flip and random rule went bust at 20x.
- The backtest window (Dec 2024 to Sep 2026) is a +61% gold bull market. Breakout rules looked excellent in it and both half-samples were positive, but 18 trades in one regime is not proof of edge. Treat them as the least-bad rule, not a money machine.
- Position size dominates everything. Same rule, 20x: 100% of equity per trade gives max drawdown 86%; 25% of equity gives 33% with a final result that is still 8x.

## 2. The rules

**Sizing.** Stake 25% of current equity per position, never more than 50%. Minimum on GOLD is $1,000 exposure, i.e. $50 margin. At $1,230 equity that is roughly $300 margin, $6,000 exposure.

**Entry (daily close, checked once per day after 00:00 UTC candle closes).**
- Long: daily close above the highest high of the prior 20 sessions.
- Short: daily close below the lowest low of the prior 20 sessions.
- Filter: skip the signal if the 50-day trend disagrees (close on the wrong side of the 50-day moving average). Shorts are cheaper to hold (paid overnight), longs cost ~0.44% of margin per night.
- One position at a time. No re-entry within 2 sessions of a stop-out.
- Entry order: market order at the next check, or a market-if-touched order at the breakout level placed in advance so you are not dependent on being awake.

**Initial stop.** 2.5% from entry (the eToro maximum, 50% of margin). Set at order time; it is server-side and does not depend on monitoring.

**Take profit.** None. A fixed TP caps the only thing that makes the game positive-expectancy.

**Trailing.** GOLD does not support eToro's native trailing stop, so it is done by editing the position's stop-loss:
- Each check, set stop = highest high since entry x (1 - 2.5%) for longs, mirror for shorts. Only ever move it in the direction of profit.
- Once the position is up 2.5% of price (+50% of margin), move the stop to entry + costs (0.2%). From there the trade cannot lose.
- Tighten to 1.5% of price once the position is up 5% (+100% of margin).

**Exit.** Stop hit, or an opposite 20-day breakout (close position and reverse if the 50-day filter allows).

**Circuit breakers.**
- Three consecutive stop-outs: stop trading for 10 sessions.
- Equity below 50% of the starting mark: halve the stake fraction to 12.5%.
- Never top up margin on a losing position. Never widen a stop.

## 3. Monitoring cadence and who does what

| Check | Frequency | Actor | Action |
|---|---|---|---|
| Daily signal (20-day breakout, 50-day filter) | once/day after 00:00 UTC | Claude Routine | Push/email with the exact order (direction, stake, SL) if a signal fires |
| Trail update | hourly during market hours | Claude Routine | Compute new stop; if it is higher than the current stop, notify with the exact PATCH request |
| Stop / breakeven execution | on your approval | Claude, via execute-write | Edit SL on the position |
| Order entry | on your approval | Claude, via prepare-trade / place-trade | Open the position |
| Weekly review | Sunday | Claude | Trade log, equity curve, rule compliance, in this repo |

Hard constraint: every write on the real account needs your explicit approval per call. I cannot run an unattended loop that moves stops or opens trades. Two ways around that:
1. You approve each notification when it arrives (one tap per action, a few per week at this cadence).
2. I write a small Python job in this repo that runs on a GitHub Actions schedule with an eToro API key scoped to a dedicated sub-account. That job can trail stops and place breakout orders unattended. This is the only path to genuine automation, and the sub-account caps the blast radius.

## 4. The open GOLD position right now

Long from 4314.85, 20x, $1,000 margin, stop 4206.98, no trailing. Price ~4363, +$236.
- Under the rules above this position would not have been opened: price is inside the 20-day range (4236 to 4511) and sitting on the 20-day and 50-day averages (4365, 4368). It is a coin flip with 100% of equity on it.
- Minimum action consistent with the plan: move the stop to 4324 (entry + costs). Locks the trade at breakeven or better, keeps the upside. Requires one approval.
- Full compliance: close it, keep the $236, and wait for a 20-day breakout with a 25% stake. Requires one approval.

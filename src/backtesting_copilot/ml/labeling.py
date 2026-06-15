"""Rule-based auto-labeling for the regime classifier.

A point t is labeled 1 ("range-bound, grid-suitable") when the next
`horizon` closes stay net-flat (small directional move) yet oscillate
enough to make grid trading worthwhile; otherwise 0. Returns None when
there is not enough future data.
"""

from __future__ import annotations


def label_point(
    closes: list[float],
    t: int,
    horizon: int,
    trend_thresh: float,
    min_osc: float,
) -> int | None:
    if t + horizon >= len(closes):
        return None
    base = closes[t]
    if base == 0:
        return None
    window = closes[t : t + horizon + 1]
    net = abs(closes[t + horizon] / base - 1.0)
    osc = (max(window) - min(window)) / base
    if net < trend_thresh and osc >= min_osc:
        return 1
    return 0

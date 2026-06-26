"""Cross-language baseline: pandas merge_asof on the same synthetic trades/quotes.

Run: python merge_asof_bench.py   (needs: pip install numpy pandas)
Compare the reported M rows/s against the Tessera C# benchmark.
"""
import time

import numpy as np
import pandas as pd

N = 1_000_000
SYMBOLS = 500
rng = np.random.default_rng(42)

quote_time = np.cumsum(rng.integers(1, 5, N))
quotes = pd.DataFrame({
    "time": quote_time,
    "sym": rng.integers(0, SYMBOLS, N),
    "bid": 100 + rng.random(N),
}).sort_values("time", kind="stable").reset_index(drop=True)

trade_time = np.cumsum(rng.integers(1, 5, N))
trades = pd.DataFrame({
    "time": trade_time,
    "sym": rng.integers(0, SYMBOLS, N),
}).sort_values("time", kind="stable").reset_index(drop=True)

# Warm up (first call pays import/JIT-ish costs inside pandas).
pd.merge_asof(trades.head(1000), quotes, on="time", by="sym", direction="backward")

t0 = time.perf_counter()
out = pd.merge_asof(trades, quotes, on="time", by="sym", direction="backward")
dt = time.perf_counter() - t0

print(f"pandas merge_asof: {dt * 1000:8.1f} ms   ({N / dt / 1e6:5.2f} M rows/s)   matched={out['bid'].notna().sum():,}")

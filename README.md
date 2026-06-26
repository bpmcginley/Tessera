# Tessera

A tiny columnar engine for market data, built around the one operation quant systems live on:
the **as-of join**. Sorted time series go in; for every trade it finds the quote that was
prevailing at that instant — in a single O(n + m) merge sweep, no per-row search.

> Working name. A *tessera* is the small tile in a mosaic — which is what a column is.

## Why this exists

kdb+/q is the database religion of quant finance, and the reason is the **as-of join**: joining
two time series not on equality but on "the most recent prior row." Tessera is a from-scratch,
readable take on that one idea in C#, fast enough to put real numbers behind it.

The whole bet: market data arrives *already sorted by time*. A naive join ignores that and
searches per row. Tessera exploits it — one cursor walks the quotes while another walks the
trades, each advancing once. That's the difference between `O(n log m)` (or worse) and `O(n + m)`.

## Results

Joining 1,000,000 trades against 1,000,000 quotes, by symbol (500 symbols), backward as-of:

| Approach | Mean | Throughput | Allocated |
| --- | ---: | ---: | ---: |
| **Tessera** — merge sweep (C#) | **10.8 ms** | **~92 M rows/s** | 11.4 MB |
| Per-symbol binary search (C#) | 82.9 ms | ~12 M rows/s | 16.6 MB |
| `pandas.merge_asof` (Python) | 152.8 ms | ~6.5 M rows/s | — |

**~14× faster than pandas, ~7.7× faster than a competent C# binary-search join — and in less
memory.** Single dev laptop, .NET 9; reproduce with the commands below.

## The model

- **`Column<T>`** — a named, contiguous typed array. The atom.
- **`Table`** — equal-length columns addressed by name. Immutable; ops return new tables that
  share arrays where they can.
- **`AsOfJoin.Backward`** — the star. Most-recent-prior join within a group key.
- **`Bars.Ohlcv`** — second primitive: ticks → fixed-interval OHLCV + VWAP bars.
- **`Categoricals.Factorize`** — string symbols → dense int codes so hot paths stay branch-free
  and allocation-free.

## Quick taste

```csharp
var trades = new Table(
    new Column<long>("time", [10L, 20L, 30L]),
    new Column<int>("sym",  [0, 0, 1]));

var quotes = new Table(
    new Column<long>("time", [5L, 15L, 25L]),
    new Column<int>("sym",   [0, 1, 0]),
    new Column<double>("bid",[100.0, 200.0, 300.0]));

var enriched = AsOfJoin.Backward(trades, quotes, on: "time", by: "sym", bring: "bid");
// each trade now carries the bid that was live at its timestamp
```

## Build, test, benchmark

```bash
dotnet build -c Release
dotnet test

# C# benchmark: Tessera vs a competent binary-search join, 1M x 1M rows
dotnet run -c Release --project bench/Tessera.Benchmarks

# Cross-language baseline: pandas merge_asof on the same shape
python bench/python/merge_asof_bench.py
```

The headline number is Tessera's merge sweep vs `pandas.merge_asof` on identical data.

## Contract & limits (today)

- Inputs **must be sorted by the time column ascending**; the `by` column must hold dense int
  codes from `Factorize`. Both are deliberate — they're what make the sweep fast.
- Single int group key; backward direction only. Forward / tolerance / multi-key are next.

## Roadmap

- [ ] Forward and nearest as-of; a `tolerance` window
- [ ] SIMD-vectorized column arithmetic (`System.Runtime.Intrinsics`)
- [ ] Multi-key `by` and a sort operator so inputs needn't be pre-sorted
- [ ] Memory-mapped column files (out-of-core)
- [ ] A tiny expression/query layer over the table ops

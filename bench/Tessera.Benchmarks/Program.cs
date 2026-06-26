using BenchmarkDotNet.Attributes;
using BenchmarkDotNet.Running;
using Tessera;

// Run all: `dotnet run -c Release -- --filter *`
// Run one: `dotnet run -c Release -- --filter *VectorBench*`
BenchmarkSwitcher.FromTypes([typeof(AsOfBench), typeof(VectorBench)]).Run(args);

[MemoryDiagnoser]
public class AsOfBench
{
    [Params(1_000_000)] public int N;

    private Table _trades = null!;
    private Table _quotes = null!;

    [GlobalSetup]
    public void Setup()
    {
        const int symbols = 500;
        var rng = new Random(42);

        var quoteTime = new long[N];
        var quoteSym = new int[N];
        var quoteBid = new double[N];
        long qt = 0;
        for (int i = 0; i < N; i++)
        {
            qt += rng.Next(1, 5);
            quoteTime[i] = qt;
            quoteSym[i] = rng.Next(symbols);
            quoteBid[i] = 100 + rng.NextDouble();
        }

        var tradeTime = new long[N];
        var tradeSym = new int[N];
        long tt = 0;
        for (int i = 0; i < N; i++)
        {
            tt += rng.Next(1, 5);
            tradeTime[i] = tt;
            tradeSym[i] = rng.Next(symbols);
        }

        _quotes = new Table(
            new Column<long>("time", quoteTime),
            new Column<int>("sym", quoteSym),
            new Column<double>("bid", quoteBid));
        _trades = new Table(
            new Column<long>("time", tradeTime),
            new Column<int>("sym", tradeSym));
    }

    [Benchmark]
    public Table Tessera_MergeSweep() =>
        AsOfJoin.Backward(_trades, _quotes, "time", "sym", "bid");

    // What a competent dev writes without the sorted-merge insight: bucket quotes per symbol,
    // binary-search the prevailing one for each trade. Correct, but O(n log m) with worse cache
    // behavior and a dictionary of lists to build first.
    [Benchmark(Baseline = true)]
    public double[] PerSymbol_BinarySearch()
    {
        var qt = _quotes.Values<long>("time");
        var qk = _quotes.Values<int>("sym");
        var qb = _quotes.Values<double>("bid");
        var tt = _trades.Values<long>("time");
        var tk = _trades.Values<int>("sym");

        var bySym = new Dictionary<int, List<int>>();
        for (int j = 0; j < qt.Length; j++)
        {
            if (!bySym.TryGetValue(qk[j], out var list))
                bySym[qk[j]] = list = [];
            list.Add(j);                       // globally time-sorted => per-symbol time-sorted
        }

        var outBid = new double[tt.Length];
        for (int i = 0; i < tt.Length; i++)
        {
            if (!bySym.TryGetValue(tk[i], out var list)) { outBid[i] = double.NaN; continue; }
            int lo = 0, hi = list.Count - 1, found = -1;
            while (lo <= hi)
            {
                int mid = (lo + hi) >> 1;
                if (qt[list[mid]] <= tt[i]) { found = list[mid]; lo = mid + 1; }
                else hi = mid - 1;
            }
            outBid[i] = found < 0 ? double.NaN : qb[found];
        }
        return outBid;
    }
}

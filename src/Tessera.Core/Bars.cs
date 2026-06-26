namespace Tessera;

/// <summary>
/// The second time-series primitive: collapse ticks into fixed-interval OHLCV+VWAP bars,
/// grouped by symbol. Buckets are floored on the time axis (<c>t - t % interval</c>), so a
/// 60e9 ns interval gives one-minute bars. First-seen bucket order is preserved.
/// </summary>
public static class Bars
{
    public static Table Ohlcv(Table ticks, string on, string by, string price, string size, long interval)
    {
        if (interval <= 0) throw new ArgumentOutOfRangeException(nameof(interval), "Interval must be positive.");

        var time = ticks.Times(on);
        var key = ticks.Values<int>(by);
        var px = ticks.Values<double>(price);
        var sz = ticks.Values<double>(size);
        int n = time.Length;

        var slot = new Dictionary<(int Group, long Bucket), int>();
        List<int> g = []; List<long> b = [];
        List<double> open = [], high = [], low = [], close = [], volume = [], priceVolume = [];

        for (int i = 0; i < n; i++)
        {
            long bucket = time[i] - time[i] % interval;
            var id = (key[i], bucket);

            if (!slot.TryGetValue(id, out int r))
            {
                r = g.Count;
                slot[id] = r;
                g.Add(key[i]); b.Add(bucket);
                open.Add(px[i]); high.Add(px[i]); low.Add(px[i]); close.Add(px[i]);
                volume.Add(sz[i]); priceVolume.Add(px[i] * sz[i]);
            }
            else
            {
                if (px[i] > high[r]) high[r] = px[i];
                if (px[i] < low[r]) low[r] = px[i];
                close[r] = px[i];
                volume[r] += sz[i];
                priceVolume[r] += px[i] * sz[i];
            }
        }

        var vwap = new double[g.Count];
        for (int r = 0; r < vwap.Length; r++)
            vwap[r] = volume[r] == 0 ? double.NaN : priceVolume[r] / volume[r];

        return new Table(
            new Column<int>(by, [.. g]),
            new Column<long>(on, [.. b]),
            new Column<double>("open", [.. open]),
            new Column<double>("high", [.. high]),
            new Column<double>("low", [.. low]),
            new Column<double>("close", [.. close]),
            new Column<double>("volume", [.. volume]),
            new Column<double>("vwap", vwap));
    }
}

namespace Tessera;

/// <summary>
/// The star of the engine. A <b>backward as-of join</b>: for every left row, attach the
/// most recent right row whose time is ≤ the left row's time, matched within a group key
/// (e.g. symbol). The canonical use is "what was the prevailing quote at each trade?".
///
/// Both inputs must be sorted by <paramref name="on"/> ascending, and <paramref name="by"/>
/// must hold dense integer codes (see <see cref="Categoricals.Factorize"/>). Because both
/// sides are time-sorted, a single merge sweep does the whole job in O(n + m) — no
/// per-row search, which is where pandas' merge_asof and hand-rolled binary-search loops
/// bleed time.
/// </summary>
public static class AsOfJoin
{
    public static Table Backward(Table left, Table right, string on, string by, params string[] bring)
    {
        var leftTime = left.Times(on);
        var leftKey = left.Values<int>(by);
        var rightTime = right.Times(on);
        var rightKey = right.Values<int>(by);
        int n = leftTime.Length, m = rightTime.Length;

        // last[g] = index of the most recent right row seen so far for group g (-1 = none yet).
        // A dense array beats a dictionary here: O(1) lookups, no hashing, cache-friendly.
        int groups = Math.Max(MaxPlusOne(leftKey), MaxPlusOne(rightKey));
        var last = GC.AllocateUninitializedArray<int>(groups);
        last.AsSpan().Fill(-1);

        var match = GC.AllocateUninitializedArray<int>(n);
        int j = 0;
        for (int i = 0; i < n; i++)
        {
            long t = leftTime[i];
            while (j < m && rightTime[j] <= t)   // advance the right cursor up to the left time
                last[rightKey[j]] = j++;
            match[i] = last[leftKey[i]];          // newest right row for this group at time t
        }

        var cols = new List<IColumn>(left.Columns);
        foreach (var name in bring)
            cols.Add(right.Column(name).Gather(match));
        return new Table(cols);
    }

    private static int MaxPlusOne(ReadOnlySpan<int> keys)
    {
        int max = -1;
        foreach (int k in keys)
            if (k > max) max = k;
        return max + 1;
    }
}

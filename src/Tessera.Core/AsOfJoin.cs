namespace Tessera;

/// <summary>Which neighbouring right row an as-of join attaches to a left row.</summary>
public enum AsOfDirection
{
    /// <summary>Most recent right row at or before the left time (the classic aj).</summary>
    Backward,
    /// <summary>Earliest right row at or after the left time.</summary>
    Forward,
    /// <summary>Whichever of backward/forward is closer in time; ties go to backward.</summary>
    Nearest,
}

/// <summary>
/// The star of the engine. A <b>directional as-of join</b>: for every left row, attach the
/// nearest right row in time, matched within a group key (e.g. symbol). The canonical use is
/// "what was the prevailing quote at each trade?".
///
/// Both inputs must be sorted by <paramref name="on"/> ascending (see <see cref="Table.SortByTime"/>),
/// and the <paramref name="by"/> column must hold dense integer codes (see <see cref="Categoricals.Factorize"/>).
/// Each direction is a single O(n + m) sweep that never re-scans — the speed comes entirely from
/// the data already being time-ordered.
/// </summary>
public static class AsOfJoin
{
    /// <summary>Backward join with the default settings — the common case, kept as a convenience.</summary>
    public static Table Backward(Table left, Table right, string on, string by, params string[] bring) =>
        Join(left, right, on, by, AsOfDirection.Backward, tolerance: 0, allowExactMatches: true, bring);

    /// <param name="direction">Which neighbour to attach. Defaults to <see cref="AsOfDirection.Backward"/>.</param>
    /// <param name="tolerance">
    /// Max allowed time gap (same units as the time column, i.e. ns). A candidate further than this
    /// is dropped and the row goes unmatched. <c>tolerance &lt;= 0</c> means no limit.
    /// </param>
    /// <param name="allowExactMatches">
    /// When true (pandas default) a right row at exactly the left time qualifies. When false, backward
    /// needs a strictly earlier row and forward a strictly later one.
    /// </param>
    /// <param name="bring">Right columns to attach; an unmatched row gets NaN (floats) or default (else).</param>
    public static Table Join(
        Table left, Table right, string on, string by,
        AsOfDirection direction = AsOfDirection.Backward,
        long tolerance = 0,
        bool allowExactMatches = true,
        params string[] bring)
    {
        var leftTime = left.Times(on);
        var leftKey = left.Values<int>(by);
        var rightTime = right.Times(on);
        var rightKey = right.Values<int>(by);
        int n = leftTime.Length;

        // Size group tables to the widest key on either side so a left-only group never indexes OOB.
        int groups = Math.Max(MaxPlusOne(leftKey), MaxPlusOne(rightKey));
        var match = GC.AllocateUninitializedArray<int>(n);

        switch (direction)
        {
            case AsOfDirection.Backward:
                FillBackward(leftTime, leftKey, rightTime, rightKey, groups, allowExactMatches, tolerance, match);
                break;
            case AsOfDirection.Forward:
                FillForward(leftTime, leftKey, rightTime, rightKey, groups, allowExactMatches, tolerance, match);
                break;
            default:
                var backward = GC.AllocateUninitializedArray<int>(n);
                var forward = GC.AllocateUninitializedArray<int>(n);
                FillBackward(leftTime, leftKey, rightTime, rightKey, groups, allowExactMatches, tolerance, backward);
                FillForward(leftTime, leftKey, rightTime, rightKey, groups, allowExactMatches, tolerance, forward);
                for (int i = 0; i < n; i++)
                {
                    int b = backward[i], f = forward[i];
                    if (b < 0) match[i] = f;
                    else if (f < 0) match[i] = b;
                    // Strict <: equal distance keeps the backward row, matching pandas direction='nearest'.
                    // Int128: an epoch-straddling span exceeds int64 and would otherwise flip the choice.
                    else match[i] = (Int128)rightTime[f] - leftTime[i] < (Int128)leftTime[i] - rightTime[b] ? f : b;
                }
                break;
        }

        var cols = new List<IColumn>(left.Columns);
        foreach (var name in bring)
            cols.Add(right.Column(name).Gather(match));
        return new Table(cols);
    }

    // Ascending sweep: the right cursor only moves forward, so each side is walked once.
    // last[g] holds the most recent qualifying right row for group g; ties resolve to the last
    // duplicate. Tolerance is checked only when assigning the match — never to gate the cursor,
    // since a row out of tolerance for i may still be the right candidate for a later left row.
    private static void FillBackward(
        long[] lt, int[] lk, long[] rt, int[] rk, int groups, bool allowExact, long tol, int[] match)
    {
        int n = lt.Length, m = rt.Length;
        bool hasTol = tol > 0;
        var last = GC.AllocateUninitializedArray<int>(groups);
        last.AsSpan().Fill(-1);

        int j = 0;
        for (int i = 0; i < n; i++)
        {
            long t = lt[i];
            if (allowExact) while (j < m && rt[j] <= t) last[rk[j]] = j++;
            else while (j < m && rt[j] < t) last[rk[j]] = j++;

            int c = last[lk[i]];
            // Int128 gap: an epoch-straddling span (pre-1970 negative ns) can exceed int64.
            match[i] = c >= 0 && (!hasTol || (Int128)t - rt[c] <= tol) ? c : -1;
        }
    }

    // Forward is the mirror image under a descending sweep: walk left rows high-to-low time while
    // the right cursor descends, and next[g] settles on the earliest future qualifying row (the
    // first duplicate on ties). match[] is written by left index, so output order is preserved.
    private static void FillForward(
        long[] lt, int[] lk, long[] rt, int[] rk, int groups, bool allowExact, long tol, int[] match)
    {
        int n = lt.Length, m = rt.Length;
        bool hasTol = tol > 0;
        var next = GC.AllocateUninitializedArray<int>(groups);
        next.AsSpan().Fill(-1);

        int k = m - 1;
        for (int i = n - 1; i >= 0; i--)
        {
            long t = lt[i];
            if (allowExact) while (k >= 0 && rt[k] >= t) next[rk[k]] = k--;
            else while (k >= 0 && rt[k] > t) next[rk[k]] = k--;

            int c = next[lk[i]];
            // Int128 gap: an epoch-straddling span (pre-1970 negative ns) can exceed int64.
            match[i] = c >= 0 && (!hasTol || (Int128)rt[c] - t <= tol) ? c : -1;
        }
    }

    private static int MaxPlusOne(ReadOnlySpan<int> keys)
    {
        int max = -1;
        foreach (int k in keys)
            if (k > max) max = k;
        return max + 1;
    }
}

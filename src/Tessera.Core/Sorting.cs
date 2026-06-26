namespace Tessera;

/// <summary>
/// Orders a table by its time column. This is what lets the rest of the engine assume sorted
/// input: feed raw, out-of-order ticks through here once and every downstream sweep is valid.
/// The sort is <b>stable</b> — rows sharing a timestamp keep their original order — which keeps
/// as-of joins deterministic when trades and quotes land on the same instant.
/// </summary>
public static class Sorting
{
    /// <summary>The permutation that orders rows by <paramref name="on"/> ascending, stably.</summary>
    public static int[] OrderByTime(Table table, string on)
    {
        var time = table.Times(on);
        int n = time.Length;
        var perm = GC.AllocateUninitializedArray<int>(n);
        for (int i = 0; i < n; i++) perm[i] = i;

        // Tie-break on original index so equal timestamps preserve input order (stability).
        Array.Sort(perm, (a, b) =>
        {
            int c = time[a].CompareTo(time[b]);
            return c != 0 ? c : a.CompareTo(b);
        });
        return perm;
    }

    public static Table SortByTime(Table table, string on)
    {
        var perm = OrderByTime(table, on);
        var cols = new IColumn[table.Columns.Count];
        for (int i = 0; i < cols.Length; i++)
            cols[i] = table.Columns[i].Gather(perm);
        return new Table(cols);
    }
}

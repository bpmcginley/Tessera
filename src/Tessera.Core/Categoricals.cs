namespace Tessera;

/// <summary>
/// Turns string labels (symbols, venues) into dense integer codes so the hot paths can use
/// plain arrays instead of hashing strings. Codes are assigned in first-seen order, and the
/// returned level table maps each code back to its label.
/// </summary>
public static class Categoricals
{
    public static (int[] Codes, string[] Levels) Factorize(IReadOnlyList<string> values)
    {
        var index = new Dictionary<string, int>(StringComparer.Ordinal);
        var codes = new int[values.Count];
        var levels = new List<string>();

        for (int i = 0; i < values.Count; i++)
        {
            var v = values[i];
            if (!index.TryGetValue(v, out int code))
            {
                code = levels.Count;
                index[v] = code;
                levels.Add(v);
            }
            codes[i] = code;
        }

        return (codes, [.. levels]);
    }

    /// <summary>Factorize and wrap the codes as a column in one step; <paramref name="levels"/> decodes them.</summary>
    public static Column<int> Encode(string name, IReadOnlyList<string> values, out string[] levels)
    {
        (int[] codes, levels) = Factorize(values);
        return new Column<int>(name, codes);
    }

    /// <summary>
    /// Factorize two tables' key columns against ONE shared level table, so the same label gets
    /// the same code on both sides. This is the contract the as-of join needs: codes are only
    /// comparable across left and right if they came from a shared mapping. Factorizing each table
    /// separately is a silent footgun — "AAPL" could be 0 on one side and 3 on the other.
    /// </summary>
    public static (int[] Left, int[] Right, string[] Levels) FactorizeShared(
        IReadOnlyList<string> left, IReadOnlyList<string> right)
    {
        var index = new Dictionary<string, int>(StringComparer.Ordinal);
        var levels = new List<string>();

        int[] Encode(IReadOnlyList<string> values)
        {
            var codes = new int[values.Count];
            for (int i = 0; i < values.Count; i++)
            {
                var v = values[i];
                if (!index.TryGetValue(v, out int code))
                {
                    code = levels.Count;
                    index[v] = code;
                    levels.Add(v);
                }
                codes[i] = code;
            }
            return codes;
        }

        var l = Encode(left);
        var r = Encode(right);
        return (l, r, [.. levels]);
    }

    /// <summary>
    /// Fold several already-shared key columns into one dense code per row via mixed-radix, so a
    /// multi-column <c>by</c> (e.g. symbol + venue) can drive the single-key join. Pass the SAME
    /// <paramref name="cardinalities"/> (each key's level count from <see cref="FactorizeShared"/>)
    /// for both tables and identical tuples get identical codes on both sides. The code space is the
    /// product of the cardinalities, so keep the combined cardinality modest.
    /// </summary>
    public static int[] CombineCodes(int[][] columns, int[] cardinalities)
    {
        if (columns.Length == 0)
            throw new ArgumentException("Need at least one key column.");
        if (columns.Length != cardinalities.Length)
            throw new ArgumentException("One cardinality per key column.");

        int n = columns[0].Length;
        foreach (var c in columns)
            if (c.Length != n) throw new ArgumentException("Key columns must be the same length.");

        var codes = new int[n];
        for (int i = 0; i < n; i++)
        {
            long combined = 0;
            for (int c = 0; c < columns.Length; c++)
                combined = combined * cardinalities[c] + columns[c][i];
            codes[i] = checked((int)combined);   // guards an oversized combined key space
        }
        return codes;
    }
}

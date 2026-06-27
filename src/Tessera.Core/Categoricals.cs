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
}

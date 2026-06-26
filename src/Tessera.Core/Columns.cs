namespace Tessera;

/// <summary>
/// A named, typed, contiguous column of values — the atom of the engine. Heterogeneous
/// tables hold these behind the non-generic <see cref="IColumn"/> face; hot paths reach
/// through <see cref="Column{T}.Values"/> to the backing array and skip the abstraction.
/// </summary>
public interface IColumn
{
    string Name { get; }
    int Length { get; }
    Type ElementType { get; }

    /// <summary>Build a new column by picking rows at the given indices; a negative index emits "missing".</summary>
    IColumn Gather(ReadOnlySpan<int> indices);

    IColumn Rename(string name);
}

public sealed class Column<T> : IColumn
{
    private readonly T[] _values;

    public Column(string name, T[] values)
    {
        Name = name;
        _values = values;
    }

    public string Name { get; }
    public int Length => _values.Length;
    public Type ElementType => typeof(T);

    /// <summary>The backing array. Use in tight loops; treat as read-only.</summary>
    public T[] Values => _values;
    public ReadOnlySpan<T> Span => _values;
    public T this[int i] => _values[i];

    public IColumn Gather(ReadOnlySpan<int> idx)
    {
        var outv = new T[idx.Length];
        var missing = Missing;
        for (int i = 0; i < idx.Length; i++)
        {
            int j = idx[i];
            outv[i] = j < 0 ? missing : _values[j];
        }
        return new Column<T>(Name, outv);
    }

    public IColumn Rename(string name) => new Column<T>(name, _values);

    // What an unmatched row gets. NaN for floats so missing data never reads as a real 0.0;
    // default otherwise. Resolved once per closed generic type, not per row.
    private static readonly T Missing =
        typeof(T) == typeof(double) ? (T)(object)double.NaN
      : typeof(T) == typeof(float) ? (T)(object)float.NaN
      : default!;
}

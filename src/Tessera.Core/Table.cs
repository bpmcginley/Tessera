namespace Tessera;

/// <summary>
/// An ordered set of equal-length columns addressed by name — the engine's dataframe.
/// Immutable: every operation returns a new table that shares column arrays where it can.
/// </summary>
public sealed class Table
{
    private readonly IColumn[] _columns;
    private readonly Dictionary<string, IColumn> _byName;

    public Table(params IColumn[] columns) : this((IReadOnlyList<IColumn>)columns) { }

    public Table(IReadOnlyList<IColumn> columns)
    {
        if (columns.Count == 0)
            throw new ArgumentException("A table needs at least one column.");

        _columns = [.. columns];
        RowCount = _columns[0].Length;

        for (int i = 1; i < _columns.Length; i++)
            if (_columns[i].Length != RowCount)
                throw new ArgumentException(
                    $"Column '{_columns[i].Name}' has {_columns[i].Length} rows; expected {RowCount}.");

        _byName = new(_columns.Length, StringComparer.Ordinal);
        foreach (var c in _columns)
            if (!_byName.TryAdd(c.Name, c))
                throw new ArgumentException($"Duplicate column name '{c.Name}'.");
    }

    public int RowCount { get; }
    public IReadOnlyList<IColumn> Columns => _columns;

    public IColumn Column(string name) =>
        _byName.TryGetValue(name, out var c) ? c : throw new KeyNotFoundException($"No column '{name}'.");

    public Column<T> Column<T>(string name) =>
        Column(name) as Column<T>
        ?? throw new InvalidOperationException($"Column '{name}' is not {typeof(T).Name}.");

    /// <summary>Backing array of a typed column, for hot loops.</summary>
    public T[] Values<T>(string name) => Column<T>(name).Values;

    /// <summary>Convention: time is nanoseconds since epoch, stored as <see cref="long"/>.</summary>
    public long[] Times(string name) => Values<long>(name);

    public Table With(params IColumn[] extra) => new([.. _columns, .. extra]);
}

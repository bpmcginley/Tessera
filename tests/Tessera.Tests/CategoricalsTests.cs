using Xunit;

namespace Tessera.Tests;

public class CategoricalsTests
{
    [Fact]
    public void FactorizeShared_gives_a_label_the_same_code_on_both_sides()
    {
        var (left, right, levels) = Categoricals.FactorizeShared(
            ["AAPL", "MSFT", "AAPL"],
            ["MSFT", "TSLA"]);

        Assert.Equal(new[] { 0, 1, 0 }, left);
        Assert.Equal(new[] { 1, 2 }, right);            // MSFT stays 1; TSLA is new -> 2
        Assert.Equal(new[] { "AAPL", "MSFT", "TSLA" }, levels);
    }

    [Fact]
    public void FactorizeShared_lets_an_as_of_join_match_across_tables_by_symbol()
    {
        var (tradeKey, quoteKey, _) = Categoricals.FactorizeShared(
            ["AAPL", "MSFT"],          // trades' symbols
            ["AAPL", "MSFT"]);         // quotes' symbols

        var trades = new Table(
            new Column<long>("t", [20L, 20L]),
            new Column<int>("g", tradeKey));
        var quotes = new Table(
            new Column<long>("t", [10L, 15L]),
            new Column<int>("g", quoteKey),
            new Column<double>("px", [100.0, 200.0]));

        var joined = AsOfJoin.Backward(trades, quotes, "t", "g", "px");

        // AAPL trade -> AAPL quote (100); MSFT trade -> MSFT quote (200)
        Assert.Equal(new[] { 100.0, 200.0 }, joined.Values<double>("px"));
    }
}

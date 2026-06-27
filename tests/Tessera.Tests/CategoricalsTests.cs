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

    [Fact]
    public void CombineCodes_drives_a_multi_key_by_so_symbol_and_venue_must_both_match()
    {
        var (tradeSym, quoteSym, symLevels) = Categoricals.FactorizeShared(["AAPL", "AAPL"], ["AAPL", "AAPL"]);
        var (tradeVen, quoteVen, venLevels) = Categoricals.FactorizeShared(["NYSE", "NASDAQ"], ["NYSE", "NASDAQ"]);

        int[] card = [symLevels.Length, venLevels.Length];
        var tradeKey = Categoricals.CombineCodes([tradeSym, tradeVen], card);
        var quoteKey = Categoricals.CombineCodes([quoteSym, quoteVen], card);

        var trades = new Table(new Column<long>("t", [30L, 30L]), new Column<int>("g", tradeKey));
        var quotes = new Table(
            new Column<long>("t", [10L, 20L]),
            new Column<int>("g", quoteKey),
            new Column<double>("px", [1.0, 2.0]));

        var joined = AsOfJoin.Backward(trades, quotes, "t", "g", "px");

        // (AAPL,NYSE) -> the NYSE quote (1); (AAPL,NASDAQ) -> the NASDAQ quote (2).
        // A symbol-only join would let the NYSE trade grab the later NASDAQ quote.
        Assert.Equal(new[] { 1.0, 2.0 }, joined.Values<double>("px"));
    }
}

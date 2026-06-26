using Xunit;

namespace Tessera.Tests;

public class AsOfJoinTests
{
    [Fact]
    public void Backward_attaches_most_recent_prior_quote_within_symbol()
    {
        var trades = new Table(
            new Column<long>("time", [10L, 20L, 30L]),
            new Column<int>("sym", [0, 0, 1]));

        var quotes = new Table(
            new Column<long>("time", [5L, 15L, 25L]),
            new Column<int>("sym", [0, 1, 0]),
            new Column<double>("bid", [100.0, 200.0, 300.0]));

        var joined = AsOfJoin.Backward(trades, quotes, on: "time", by: "sym", bring: "bid");

        // sym0@10 -> quote@5 (100); sym0@20 -> still quote@5 (100); sym1@30 -> quote@15 (200)
        Assert.Equal(new[] { 100.0, 100.0, 200.0 }, joined.Values<double>("bid"));
    }

    [Fact]
    public void Backward_emits_NaN_when_no_prior_quote_exists()
    {
        var trades = new Table(new Column<long>("time", [1L]), new Column<int>("sym", [0]));
        var quotes = new Table(
            new Column<long>("time", [5L]),
            new Column<int>("sym", [0]),
            new Column<double>("bid", [100.0]));

        var joined = AsOfJoin.Backward(trades, quotes, "time", "sym", "bid");

        Assert.True(double.IsNaN(joined.Values<double>("bid")[0]));
    }

    [Fact]
    public void Backward_keeps_groups_independent()
    {
        var trades = new Table(new Column<long>("time", [10L]), new Column<int>("sym", [1]));
        var quotes = new Table(
            new Column<long>("time", [5L]),       // a sym0 quote that must NOT leak into sym1
            new Column<int>("sym", [0]),
            new Column<double>("bid", [100.0]));

        var joined = AsOfJoin.Backward(trades, quotes, "time", "sym", "bid");

        Assert.True(double.IsNaN(joined.Values<double>("bid")[0]));
    }
}

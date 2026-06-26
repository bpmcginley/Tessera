using Xunit;

namespace Tessera.Tests;

public class SortingTests
{
    [Fact]
    public void SortByTime_orders_rows_and_keeps_ties_stable()
    {
        var t = new Table(
            new Column<long>("time", [30L, 10L, 20L, 10L]),
            new Column<int>("id", [0, 1, 2, 3]));

        var sorted = t.SortByTime("time");

        Assert.Equal(new[] { 10L, 10L, 20L, 30L }, sorted.Values<long>("time"));
        // The two timestamp-10 rows (ids 1 then 3) must stay in input order.
        Assert.Equal(new[] { 1, 3, 2, 0 }, sorted.Values<int>("id"));
    }

    [Fact]
    public void AsOf_join_works_on_freshly_sorted_input()
    {
        var trades = new Table(
            new Column<long>("time", [30L, 10L]),
            new Column<int>("sym", [0, 0])).SortByTime("time");
        var quotes = new Table(
            new Column<long>("time", [25L, 5L]),
            new Column<int>("sym", [0, 0]),
            new Column<double>("bid", [300.0, 100.0])).SortByTime("time");

        var joined = AsOfJoin.Backward(trades, quotes, "time", "sym", "bid");

        // after sort: trades @10,30 -> quotes @5 (100), @25 (300)
        Assert.Equal(new[] { 100.0, 300.0 }, joined.Values<double>("bid"));
    }
}

using Xunit;

namespace Tessera.Tests;

public class BarsTests
{
    [Fact]
    public void Ohlcv_buckets_ticks_and_computes_vwap()
    {
        var ticks = new Table(
            new Column<long>("time", [0L, 5L, 15L]),
            new Column<int>("sym", [0, 0, 0]),
            new Column<double>("px", [10.0, 12.0, 11.0]),
            new Column<double>("sz", [1.0, 2.0, 1.0]));

        var bars = Bars.Ohlcv(ticks, on: "time", by: "sym", price: "px", size: "sz", interval: 10);

        Assert.Equal(2, bars.RowCount);
        Assert.Equal(new[] { 12.0, 11.0 }, bars.Values<double>("close"));
        // bucket [0,10): vwap = (10*1 + 12*2) / 3 = 11.333...
        Assert.Equal(34.0 / 3.0, bars.Values<double>("vwap")[0], precision: 9);
    }
}

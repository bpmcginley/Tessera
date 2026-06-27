using Xunit;

namespace Tessera.Tests;

// Generated from the design-workflow spec: backward/forward/nearest x tolerance x allowExactMatches.
public class AsOfDirectionTests
{
    private static Table Trades(long[] time, int[] key) =>
        new(new Column<long>("t", time), new Column<int>("g", key));

    [Fact]
    public void Backward_default_delegation_matches_legacy()
    {
        var left = Trades([2, 5, 9], [0, 0, 0]);
        var right = new Table(new Column<long>("t", [1L, 4, 8]), new Column<int>("g", [0, 0, 0]),
            new Column<double>("px", [10.0, 40, 80]));

        var j = AsOfJoin.Backward(left, right, "t", "g", "px");

        Assert.Equal(new[] { 10.0, 40, 80 }, j.Values<double>("px"));
    }

    [Fact]
    public void Backward_no_prior_right_emits_NaN()
    {
        var j = AsOfJoin.Join(Trades([5], [0]),
            new Table(new Column<long>("t", [10L]), new Column<int>("g", [0]), new Column<double>("px", [1.0])),
            "t", "g", AsOfDirection.Backward, 0, true, "px");

        Assert.True(double.IsNaN(j.Values<double>("px")[0]));
    }

    [Fact]
    public void Backward_tie_keeps_last_duplicate()
    {
        var j = AsOfJoin.Join(Trades([10], [0]),
            new Table(new Column<long>("t", [10L, 10, 10]), new Column<int>("g", [0, 0, 0]), new Column<int>("tag", [1, 2, 3])),
            "t", "g", AsOfDirection.Backward, 0, true, "tag");

        Assert.Equal(3, j.Values<int>("tag")[0]);
    }

    [Fact]
    public void Forward_matches_nearest_future()
    {
        var right = new Table(new Column<long>("t", [3L, 6, 11]), new Column<int>("g", [0, 0, 0]),
            new Column<double>("px", [30.0, 60, 110]));

        var j = AsOfJoin.Join(Trades([2, 5, 9], [0, 0, 0]), right, "t", "g", AsOfDirection.Forward, 0, true, "px");

        Assert.Equal(new[] { 30.0, 60, 110 }, j.Values<double>("px"));
    }

    [Fact]
    public void Forward_tie_keeps_first_duplicate()
    {
        var j = AsOfJoin.Join(Trades([10], [0]),
            new Table(new Column<long>("t", [10L, 10, 10]), new Column<int>("g", [0, 0, 0]), new Column<int>("tag", [1, 2, 3])),
            "t", "g", AsOfDirection.Forward, 0, true, "tag");

        Assert.Equal(1, j.Values<int>("tag")[0]);
    }

    [Fact]
    public void Forward_no_future_right_emits_NaN()
    {
        var j = AsOfJoin.Join(Trades([20], [0]),
            new Table(new Column<long>("t", [10L]), new Column<int>("g", [0]), new Column<double>("px", [1.0])),
            "t", "g", AsOfDirection.Forward, 0, true, "px");

        Assert.True(double.IsNaN(j.Values<double>("px")[0]));
    }

    [Fact]
    public void Nearest_equidistant_prefers_backward()
    {
        var j = AsOfJoin.Join(Trades([100], [0]),
            new Table(new Column<long>("t", [95L, 105]), new Column<int>("g", [0, 0]), new Column<int>("tag", [1, 2])),
            "t", "g", AsOfDirection.Nearest, 0, true, "tag");

        Assert.Equal(1, j.Values<int>("tag")[0]);
    }

    [Fact]
    public void Nearest_forward_closer_wins()
    {
        var j = AsOfJoin.Join(Trades([100], [0]),
            new Table(new Column<long>("t", [90L, 101]), new Column<int>("g", [0, 0]), new Column<int>("tag", [1, 2])),
            "t", "g", AsOfDirection.Nearest, 0, true, "tag");

        Assert.Equal(2, j.Values<int>("tag")[0]);
    }

    [Fact]
    public void Nearest_tolerance_flips_to_farther_in_tolerance_side()
    {
        // backward 98 is distance 2 (> tol 1, dropped); forward 101 is distance 1 (kept).
        var j = AsOfJoin.Join(Trades([100], [0]),
            new Table(new Column<long>("t", [98L, 101]), new Column<int>("g", [0, 0]), new Column<int>("tag", [1, 2])),
            "t", "g", AsOfDirection.Nearest, 1, true, "tag");

        Assert.Equal(2, j.Values<int>("tag")[0]);
    }

    [Fact]
    public void Nearest_both_out_of_tolerance_emits_NaN()
    {
        var j = AsOfJoin.Join(Trades([100], [0]),
            new Table(new Column<long>("t", [90L, 115]), new Column<int>("g", [0, 0]), new Column<double>("px", [1.0, 2])),
            "t", "g", AsOfDirection.Nearest, 5, true, "px");

        Assert.True(double.IsNaN(j.Values<double>("px")[0]));
    }

    [Fact]
    public void Tolerance_boundary_is_inclusive()
    {
        var j = AsOfJoin.Join(Trades([100], [0]),
            new Table(new Column<long>("t", [95L]), new Column<int>("g", [0]), new Column<double>("px", [7.0])),
            "t", "g", AsOfDirection.Backward, 5, true, "px");

        Assert.Equal(7.0, j.Values<double>("px")[0]);
    }

    [Fact]
    public void Tolerance_just_over_emits_NaN()
    {
        var j = AsOfJoin.Join(Trades([100], [0]),
            new Table(new Column<long>("t", [94L]), new Column<int>("g", [0]), new Column<double>("px", [7.0])),
            "t", "g", AsOfDirection.Backward, 5, true, "px");

        Assert.True(double.IsNaN(j.Values<double>("px")[0]));
    }

    [Fact]
    public void ExactFalse_backward_drops_equal_time_despite_huge_tolerance()
    {
        var j = AsOfJoin.Join(Trades([100], [0]),
            new Table(new Column<long>("t", [100L]), new Column<int>("g", [0]), new Column<double>("px", [9.0])),
            "t", "g", AsOfDirection.Backward, 1000, false, "px");

        Assert.True(double.IsNaN(j.Values<double>("px")[0]));
    }

    [Fact]
    public void ExactFalse_backward_picks_strict_prior()
    {
        var j = AsOfJoin.Join(Trades([100], [0]),
            new Table(new Column<long>("t", [90L, 100]), new Column<int>("g", [0, 0]), new Column<int>("tag", [1, 2])),
            "t", "g", AsOfDirection.Backward, 0, false, "tag");

        Assert.Equal(1, j.Values<int>("tag")[0]);
    }

    [Fact]
    public void ExactFalse_forward_picks_strict_future()
    {
        var j = AsOfJoin.Join(Trades([100], [0]),
            new Table(new Column<long>("t", [100L, 110]), new Column<int>("g", [0, 0]), new Column<int>("tag", [1, 2])),
            "t", "g", AsOfDirection.Forward, 0, false, "tag");

        Assert.Equal(2, j.Values<int>("tag")[0]);
    }

    [Fact]
    public void Group_absent_in_right_emits_NaN_without_overflow()
    {
        var j = AsOfJoin.Join(Trades([10], [1]),
            new Table(new Column<long>("t", [10L]), new Column<int>("g", [0]), new Column<double>("px", [5.0])),
            "t", "g", AsOfDirection.Backward, 0, true, "px");

        Assert.True(double.IsNaN(j.Values<double>("px")[0]));
    }

    [Fact]
    public void Empty_right_yields_all_NaN()
    {
        var right = new Table(new Column<long>("t", []), new Column<int>("g", []), new Column<double>("px", []));

        var j = AsOfJoin.Join(Trades([1, 2], [0, 0]), right, "t", "g", AsOfDirection.Nearest, 0, true, "px");

        var px = j.Values<double>("px");
        Assert.Equal(2, px.Length);
        Assert.True(double.IsNaN(px[0]) && double.IsNaN(px[1]));
    }

    [Fact]
    public void Empty_left_yields_empty_output()
    {
        var left = new Table(new Column<long>("t", []), new Column<int>("g", []));
        var right = new Table(new Column<long>("t", [1L]), new Column<int>("g", [0]), new Column<double>("px", [1.0]));

        var j = AsOfJoin.Join(left, right, "t", "g", AsOfDirection.Backward, 0, true, "px");

        Assert.Equal(0, j.RowCount);
        Assert.Empty(j.Values<double>("px"));
    }

    [Fact]
    public void Interleaved_groups_share_one_monotonic_cursor()
    {
        var right = new Table(new Column<long>("t", [9L, 9]), new Column<int>("g", [1, 0]), new Column<int>("tag", [101, 100]));

        var j = AsOfJoin.Join(Trades([10, 11], [0, 1]), right, "t", "g", AsOfDirection.Backward, 0, true, "tag");

        Assert.Equal(new[] { 100, 101 }, j.Values<int>("tag"));
    }

    [Fact]
    public void Mixed_bring_types_emit_NaN_and_default()
    {
        var right = new Table(new Column<long>("t", [10L]), new Column<int>("g", [0]),
            new Column<double>("px", [1.0]), new Column<int>("lot", [7]));

        var j = AsOfJoin.Join(Trades([5], [0]), right, "t", "g", AsOfDirection.Backward, 0, true, "px", "lot");

        Assert.True(double.IsNaN(j.Values<double>("px")[0]));
        Assert.Equal(0, j.Values<int>("lot")[0]);
    }

    [Fact]
    public void Output_row_order_preserved_under_forward_descending_loop()
    {
        var right = new Table(new Column<long>("t", [1L, 2, 3]), new Column<int>("g", [0, 0, 0]), new Column<int>("tag", [10, 20, 30]));

        var j = AsOfJoin.Join(Trades([1, 2, 3], [0, 0, 0]), right, "t", "g", AsOfDirection.Forward, 0, true, "tag");

        Assert.Equal(new[] { 10, 20, 30 }, j.Values<int>("tag"));
    }

    // Regression: int64 gap math overflows on an epoch-straddling axis (negative ns, multi-century span).
    [Fact]
    public void Nearest_handles_epoch_straddling_times_without_overflow()
    {
        long lt = -8_500_000_000_000_000_000L;
        var right = new Table(
            new Column<long>("t", [lt - 1, 8_800_000_000_000_000_000L]),
            new Column<int>("g", [0, 0]),
            new Column<double>("v", [11.0, 99.0]));

        var j = AsOfJoin.Join(Trades([lt], [0]), right, "t", "g", AsOfDirection.Nearest, 0, true, "v");

        // backward gap = 1ns, forward gap ~1.7e19ns; backward must win.
        Assert.Equal(11.0, j.Values<double>("v")[0]);
    }

    [Fact]
    public void Backward_tolerance_handles_epoch_straddling_span_without_overflow()
    {
        var right = new Table(
            new Column<long>("t", [long.MinValue + 100]),
            new Column<int>("g", [0]),
            new Column<double>("v", [7.0]));

        var j = AsOfJoin.Join(Trades([long.MaxValue - 100], [0]), right, "t", "g", AsOfDirection.Backward, 1000, true, "v");

        Assert.True(double.IsNaN(j.Values<double>("v")[0]));   // true gap ~1.8e19 >> 1000
    }

    [Fact]
    public void Forward_tolerance_handles_epoch_straddling_span_without_overflow()
    {
        var right = new Table(
            new Column<long>("t", [long.MaxValue - 100]),
            new Column<int>("g", [0]),
            new Column<double>("v", [42.0]));

        var j = AsOfJoin.Join(Trades([long.MinValue + 100], [0]), right, "t", "g", AsOfDirection.Forward, 1000, true, "v");

        Assert.True(double.IsNaN(j.Values<double>("v")[0]));
    }
}

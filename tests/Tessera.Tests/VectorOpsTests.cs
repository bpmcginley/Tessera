using Xunit;

namespace Tessera.Tests;

public class VectorOpsTests
{
    [Fact]
    public void Multiply_matches_scalar_including_the_remainder_lanes()
    {
        // Length 10 isn't a multiple of the 4- or 8-wide vector, so this exercises the scalar tail.
        var a = new double[10];
        var b = new double[10];
        for (int i = 0; i < 10; i++) { a[i] = i + 1; b[i] = 2; }

        var r = VectorOps.Multiply(a, b);

        for (int i = 0; i < 10; i++)
            Assert.Equal((i + 1) * 2.0, r[i]);
    }

    [Fact]
    public void Sum_matches_scalar_total()
    {
        var a = new double[101];
        for (int i = 0; i < 101; i++) a[i] = i;

        Assert.Equal(101 * 100 / 2.0, VectorOps.Sum(a), precision: 9);
    }

    [Fact]
    public void Mismatched_lengths_throw()
    {
        Assert.Throws<ArgumentException>(() => VectorOps.Add(new double[3], new double[4]));
    }
}

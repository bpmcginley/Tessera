using System.Numerics;

namespace Tessera;

/// <summary>
/// SIMD-vectorized elementwise math over <see cref="double"/> columns. The hardware applies one
/// instruction across <see cref="Vector{T}.Count"/> lanes at once (4 doubles on AVX2, 8 on
/// AVX-512), so these run several times faster than a scalar loop — the other half of why
/// columnar engines fly: contiguous data fed straight into wide registers.
/// </summary>
public static class VectorOps
{
    public static double[] Add(ReadOnlySpan<double> a, ReadOnlySpan<double> b) => Apply<AddOp>(a, b);
    public static double[] Subtract(ReadOnlySpan<double> a, ReadOnlySpan<double> b) => Apply<SubOp>(a, b);
    public static double[] Multiply(ReadOnlySpan<double> a, ReadOnlySpan<double> b) => Apply<MulOp>(a, b);
    public static double[] Divide(ReadOnlySpan<double> a, ReadOnlySpan<double> b) => Apply<DivOp>(a, b);

    public static Column<double> Multiply(Column<double> a, Column<double> b) => new(a.Name, Multiply(a.Span, b.Span));
    public static Column<double> Add(Column<double> a, Column<double> b) => new(a.Name, Add(a.Span, b.Span));

    /// <summary>Horizontal sum of a column, lanes accumulated in parallel then folded once.</summary>
    public static double Sum(ReadOnlySpan<double> a)
    {
        var acc = Vector<double>.Zero;
        int w = Vector<double>.Count, i = 0, n = a.Length;
        for (; i <= n - w; i += w)
            acc += new Vector<double>(a.Slice(i, w));

        double total = Vector.Sum(acc);          // fold the lanes together
        for (; i < n; i++) total += a[i];          // scalar remainder
        return total;
    }

    // The operator is a generic type parameter, not a runtime branch: the JIT stamps out a
    // dedicated, branch-free copy of Apply per op, so TOp.Simd inlines to a single vector
    // instruction in the hot loop. Clever, but it earns its place — no duplication, no per-row test.
    private static double[] Apply<TOp>(ReadOnlySpan<double> a, ReadOnlySpan<double> b) where TOp : IBinaryOp
    {
        if (a.Length != b.Length)
            throw new ArgumentException("Columns must be the same length.");

        var result = new double[a.Length];
        var r = result.AsSpan();
        int w = Vector<double>.Count, i = 0, n = a.Length;

        for (; i <= n - w; i += w)
            TOp.Simd(new Vector<double>(a.Slice(i, w)), new Vector<double>(b.Slice(i, w))).CopyTo(r.Slice(i, w));
        for (; i < n; i++)
            r[i] = TOp.Scalar(a[i], b[i]);
        return result;
    }

    private interface IBinaryOp
    {
        static abstract Vector<double> Simd(Vector<double> a, Vector<double> b);
        static abstract double Scalar(double a, double b);
    }

    private readonly struct AddOp : IBinaryOp
    {
        public static Vector<double> Simd(Vector<double> a, Vector<double> b) => a + b;
        public static double Scalar(double a, double b) => a + b;
    }
    private readonly struct SubOp : IBinaryOp
    {
        public static Vector<double> Simd(Vector<double> a, Vector<double> b) => a - b;
        public static double Scalar(double a, double b) => a - b;
    }
    private readonly struct MulOp : IBinaryOp
    {
        public static Vector<double> Simd(Vector<double> a, Vector<double> b) => a * b;
        public static double Scalar(double a, double b) => a * b;
    }
    private readonly struct DivOp : IBinaryOp
    {
        public static Vector<double> Simd(Vector<double> a, Vector<double> b) => a / b;
        public static double Scalar(double a, double b) => a / b;
    }
}

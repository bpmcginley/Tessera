using BenchmarkDotNet.Attributes;
using BenchmarkDotNet.Configs;
using Tessera;

[MemoryDiagnoser]
[CategoriesColumn]
[GroupBenchmarksBy(BenchmarkLogicalGroupRule.ByCategory)]
public class VectorBench
{
    [Params(20_000_000)] public int N;

    private double[] _a = null!;
    private double[] _b = null!;

    [GlobalSetup]
    public void Setup()
    {
        var rng = new Random(7);
        _a = new double[N];
        _b = new double[N];
        for (int i = 0; i < N; i++) { _a[i] = rng.NextDouble(); _b[i] = rng.NextDouble(); }
    }

    [BenchmarkCategory("multiply"), Benchmark(Baseline = true)]
    public double[] Scalar_Multiply()
    {
        var r = new double[N];
        for (int i = 0; i < N; i++) r[i] = _a[i] * _b[i];
        return r;
    }

    [BenchmarkCategory("multiply"), Benchmark]
    public double[] Simd_Multiply() => VectorOps.Multiply(_a.AsSpan(), _b.AsSpan());

    [BenchmarkCategory("sum"), Benchmark(Baseline = true)]
    public double Scalar_Sum()
    {
        double s = 0;
        for (int i = 0; i < N; i++) s += _a[i];
        return s;
    }

    [BenchmarkCategory("sum"), Benchmark]
    public double Simd_Sum() => VectorOps.Sum(_a.AsSpan());
}

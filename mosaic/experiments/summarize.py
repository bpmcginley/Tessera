"""Print, per scenario, the cheapest setting of each method that reaches a
sensitivity target while being at least as specific as individual testing."""
import json, sys, glob
for f in sorted(glob.glob("results/frontier_*.json")):
    d = json.load(open(f)); rows = d["rows"]
    ind = next(r for r in rows if r["method"] == "individual" and r["knob"] == 0)
    print(f"\n== {d['scenario']}  N={d['N']}  individual: sens={ind['sens']:.3f} spec={ind['spec']:.4f}")
    for frac in (1.0, 0.97, 0.94, 0.90):
        tgt = frac * ind["sens"]
        line = f"  sens>={frac:.2f}x individual ({tgt:.3f}):"
        for m in ("individual", "dorfman", "informative_dorfman", "mosaic"):
            ok = [r for r in rows if r["method"] == m and r["sens"] >= tgt - 1e-9 and r["spec"] >= ind["spec"] - 0.0005]
            if ok:
                b = min(ok, key=lambda r: r["tests_pp"])
                line += f"  {m}={b['tests_pp']:.3f}[{b['knob']}]"
            else:
                line += f"  {m}=n/a"
        print(line)

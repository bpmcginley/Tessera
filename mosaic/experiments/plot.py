"""Plot cost-vs-sensitivity frontiers (one panel per scenario) -> results/frontier.png"""
import glob, json
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

SER = [("individual", "Individual tests (with triage)", "#2a78d6", "o"), ("dorfman", "Dorfman pooling", "#eb6834", "s"),
       ("informative_dorfman", "Risk-ordered Dorfman", "#1baf7a", "^"), ("mosaic", "MOSAIC (this work)", "#6250d6", "D")]
INK, MUTED, SURF = "#0b0b0b", "#52514e", "#fcfcfb"
TITLES = {"tb_triage": "TB-like triage (10% prevalence)", "community": "Community screening (1%)",
          "no_risk_info": "No risk information (3%)", "pcr_high_load": "High-load PCR (2%)"}


def envelope(pts):
    """Lower-right frontier: cheapest way to reach each sensitivity."""
    pts = sorted(pts, key=lambda t: -t[0]); out = []; best = 9
    for s, c in pts:
        if c < best - 1e-9:
            out.append((s, c)); best = c
    return out[::-1]


files = sorted(glob.glob("results/frontier_*.json"))
fig, axes = plt.subplots(2, 2, figsize=(11, 8), facecolor=SURF)
for ax, f in zip(axes.ravel(), files):
    d = json.load(open(f)); rows = d["rows"]
    ind = next(r for r in rows if r["method"] == "individual" and r["knob"] == 0)
    ax.set_facecolor(SURF)
    for key, lab, col, mk in SER:
        ok = [(r["sens"], r["tests_pp"]) for r in rows if r["method"] == key and r["spec"] >= ind["spec"] - 0.0005 and r["tests_pp"] > 0]
        if not ok:
            continue
        env = envelope(ok)
        ax.plot([e[0] for e in env], [e[1] for e in env], color=col, lw=2, marker=mk, ms=6, mec=SURF, mew=1, label=lab)
    ax.axvline(ind["sens"], color=MUTED, lw=1, ls=":")
    ax.text(ind["sens"], 1.02, "test everyone\nindividually", color=MUTED, fontsize=8, ha="center", va="bottom")
    ax.set_title(TITLES.get(d["scenario"], d["scenario"]), color=INK, fontsize=11, loc="left", pad=22)
    ax.set_xlabel("Sensitivity (share of infected people found)", color=MUTED, fontsize=9)
    ax.set_ylabel("Tests used per person", color=MUTED, fontsize=9)
    ax.set_ylim(0, 1.05); ax.set_xlim(0.6, min(1.0, ind["sens"] + 0.06))
    ax.grid(color="#e4e3df", lw=0.6); ax.tick_params(colors=MUTED, labelsize=8)
    for sp in ax.spines.values():
        sp.set_visible(False)
axes[0, 0].legend(frameon=False, fontsize=9, loc="upper left", labelcolor=INK)
fig.suptitle("Fewer tests for the same sensitivity (lower is better; all points at least as specific as individual testing)", color=INK, fontsize=11, x=0.02, ha="left")
fig.tight_layout(rect=(0, 0, 1, 0.96))
fig.savefig("results/frontier.png", dpi=150)
print("wrote results/frontier.png")

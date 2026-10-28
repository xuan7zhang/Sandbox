import json, os, sys
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

HERE = os.path.dirname(os.path.abspath(__file__))
S = json.load(open(os.path.join(HERE, "results", "summary.json")))
C = ["#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#e87ba4", "#008300"]
GRID = "#e4e3df"; INK = "#3a3a38"; MUTED = "#8a8985"
plt.rcParams.update({"font.size": 9, "axes.edgecolor": GRID, "axes.labelcolor": INK, "xtick.color": INK, "ytick.color": INK,
                     "axes.grid": True, "grid.color": GRID, "grid.linewidth": 0.6, "axes.spines.top": False,
                     "axes.spines.right": False, "legend.frameon": False, "figure.dpi": 140})


def band(ax, ys, color, label, ls="-"):
    x = list(range(1, len(ys) + 1))
    m = [v[0] for v in ys]; e = [v[1] or 0 for v in ys]
    ax.plot(x, m, color=color, lw=2, ls=ls, label=label)
    ax.fill_between(x, [a - b for a, b in zip(m, e)], [a + b for a, b in zip(m, e)], color=color, alpha=0.13, lw=0)


fig, axs = plt.subplots(1, 3, figsize=(12, 3.4))
# (1) M1 / M3 curves
cv = S["curves"]
band(axs[0], cv["M1_leak3"]["reported"], C[0], "reported (loop's own verifier)")
band(axs[0], cv["M1_leak3"]["rejudged"], C[0], "same champion, re-judged post-hoc", ls="--")
band(axs[0], cv["M3_inloop"]["reported"], C[1], "verifier hardened in-loop (reported = re-judged)")
axs[0].set_ylim(0, 1); axs[0].set_xlabel("generation"); axs[0].set_ylabel("champion non-hacking pass rate")
axs[0].set_title("Idea 1: illusory gain  (leak 3, best, frontier)"); axs[0].legend(fontsize=7, loc="lower left")

# (2) leakage sweep
ks = [f"leak{i}" for i in range(4)]
for j, (key, lab, col) in enumerate([("reported", "reported", C[0]), ("rejudged", "re-judged", C[1]), ("champion_is_shotgun", "P(champion = shotgun)", C[2])]):
    m = [S["M1"][k][key][0] for k in ks]; e = [S["M1"][k][key][1] for k in ks]
    axs[1].errorbar([i + (j - 1) * 0.15 for i in range(4)], m, yerr=e, fmt="o", color=col, capsize=3, ms=5, label=lab)
axs[1].set_xticks(range(4)); axs[1].set_xticklabels(["0: none", "1: pass/fail", "2: +flags", "3: +evidence"], fontsize=7)
axs[1].set_ylim(-0.05, 1.1); axs[1].set_xlabel("improver information leakage"); axs[1].set_title("Idea 3: leakage does NOT gate the hack here")
axs[1].legend(fontsize=7, loc="center right")

# (3) M2
conds = ["best", "cmp", "random"]; labels = {"best": "archive greedy (leak 3)", "cmp": "archive CMP (leak 3)", "random": "random, matched budget (leak 0)"}
for j, c in enumerate(conds):
    for i, d in enumerate(["2", "frontier"]):
        v = S["M2"][f"{d}/{c}"]
        axs[2].errorbar([i + (j - 1) * 0.2], [v["rejudged"][0]], yerr=[v["rejudged"][1]], fmt="o", color=C[j], capsize=3, ms=5, label=labels[c] if i == 0 else None)
        axs[2].errorbar([i + (j - 1) * 0.2], [v["reported"][0]], yerr=[v["reported"][1]], fmt="^", color=C[j], capsize=3, ms=5, alpha=0.45)
axs[2].set_xticks([0, 1]); axs[2].set_xticklabels(["static tasks (d=2)", "co-evolving (frontier)"])
axs[2].set_ylim(-0.05, 1.0); axs[2].set_title("Idea 2: ● re-judged  ▲ reported  — no separation")
axs[2].legend(fontsize=7, loc="upper left")
fig.tight_layout(); fig.savefig(os.path.join(HERE, "results", "toy_screening.png")); print("saved")

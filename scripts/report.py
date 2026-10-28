#!/usr/bin/env python3
"""Turn one or more run directories into a results table, a re-judge analysis
and paper-style figures.

    python scripts/report.py runs/claude_small                      # one run
    python scripts/report.py runs/matrix/*                          # many runs -> grouped by condition
    python scripts/report.py runs/claude_small --out reports/exp1   # choose output dir

Outputs (in --out, default <first run>/report):
  summary.md     per-generation table for every run + re-judge table
  summary.json   the same, machine-readable
  curves.png     small multiples: pass rate, ANNECS, hacking rate, difficulty target,
                 adversary catch rate, cumulative LLM calls  (one line per run)
Runs are grouped by the `condition` recorded in config.json (selection + improver)
so that cmp / best / random appear as separate series with mean ± 95% CI when
several seeds exist.
"""
from __future__ import annotations

import argparse
import json
import math
import os
import sys
from collections import defaultdict
from typing import Any, Dict, List

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sandbox.archive import Archive  # noqa: E402
from sandbox.metrics.rejudge import rejudge  # noqa: E402
from sandbox.verifier import VerifierStack  # noqa: E402

# Fixed categorical order (dataviz reference palette, light surface) - never cycled.
SERIES = ["#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#e87ba4", "#008300", "#6250d6", "#e34948"]
INK, INK2, GRID = "#0b0b0b", "#52514e", "#e6e5e1"

METRICS = [
    ("champion_pass_rate", "Champion pass rate (non-hacking)", lambda s: s.get("champion_pass_rate")),
    ("annecs", "ANNECS (novel tasks created & solved)", lambda s: s.get("annecs")),
    ("hacking_rate", "Hacking rate of passes", lambda s: (s.get("hacking") or {}).get("hacking_rate_of_passes")),
    ("difficulty_target", "Proposer difficulty target", lambda s: s.get("difficulty_target")),
    ("caught_rate", "Adversary: caught / attacks", lambda s: (s.get("adversary") or {}).get("caught_rate")),
    ("llm_calls", "Cumulative LLM calls", lambda s: (s.get("budget_cumulative") or {}).get("llm_calls")),
]


def load_run(run_dir: str) -> Dict[str, Any]:
    gens = []
    with open(os.path.join(run_dir, "generations.jsonl")) as f:
        for line in f:
            gens.append(json.loads(line))
    cfg = {}
    p = os.path.join(run_dir, "config.json")
    if os.path.exists(p):
        cfg = json.load(open(p))
    cond = cfg.get("condition") or cfg.get("selection", "?")
    return {"dir": run_dir, "name": os.path.basename(run_dir.rstrip("/")), "condition": cond, "gens": gens, "cfg": cfg}


def table(run: Dict[str, Any]) -> str:
    hdr = "| gen | champion | pass | incl.hacks | CMP | ANNECS | tasks | novel | hack% | diff | adv caught | hardened | accept% | LLM calls |\n"
    hdr += "|---|---|---|---|---|---|---|---|---|---|---|---|---|---|\n"
    rows = []
    for s in run["gens"]:
        h, adv, pa = s.get("hacking") or {}, s.get("adversary") or {}, s.get("proposer_acceptance") or {}
        rows.append("| {gen} | {ch} | {pr} | {prh} | {cmp} | {an} | {ta} | {nv} | {hk} | {df} | {cr} | {hd} | {ac} | {calls} |".format(
            gen=s["gen"], ch=s.get("champion"), pr=_f(s.get("champion_pass_rate")),
            prh=_f(s.get("champion_pass_rate_incl_hacks")), cmp=_f(s.get("champion_cmp")), an=s.get("annecs"),
            ta=s.get("tasks_active"), nv=s.get("tasks_novel_this_gen"), hk=_f(h.get("hacking_rate_of_passes")),
            df=s.get("difficulty_target", "-"), cr=_f(adv.get("caught_rate")), hd=adv.get("hardened", "-"),
            ac=_f(pa.get("acceptance_rate")), calls=(s.get("budget_cumulative") or {}).get("llm_calls")))
    return hdr + "\n".join(rows) + "\n"


def _f(x) -> str:
    return "-" if x is None else (f"{x:.2f}" if isinstance(x, float) else str(x))


def ci95(xs: List[float]):
    xs = [x for x in xs if x is not None]
    if not xs:
        return None, None
    m = sum(xs) / len(xs)
    if len(xs) < 2:
        return m, 0.0
    sd = math.sqrt(sum((x - m) ** 2 for x in xs) / (len(xs) - 1))
    return m, 1.96 * sd / math.sqrt(len(xs))


def plot(runs: List[Dict[str, Any]], out_png: str) -> None:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import matplotlib.ticker  # noqa: F401

    groups: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    for r in runs:
        groups[r["condition"]].append(r)
    conds = list(groups)
    fig, axes = plt.subplots(2, 3, figsize=(12, 6.4), facecolor="#fcfcfb")
    for ax, (key, title, get) in zip(axes.flat, METRICS):
        ax.set_facecolor("#fcfcfb")
        for ci, cond in enumerate(conds):
            color = SERIES[ci % len(SERIES)]
            by_gen: Dict[int, List[float]] = defaultdict(list)
            for r in groups[cond]:
                for s in r["gens"]:
                    v = get(s)
                    if v is not None:
                        by_gen[s["gen"]].append(float(v))
            gens = sorted(by_gen)
            if not gens:
                continue
            means, errs = zip(*(ci95(by_gen[g]) for g in gens))
            ax.plot(gens, means, color=color, linewidth=2, marker="o", markersize=5, label=cond)
            if len(groups[cond]) > 1:
                ax.fill_between(gens, [m - e for m, e in zip(means, errs)], [m + e for m, e in zip(means, errs)],
                                color=color, alpha=0.15, linewidth=0)
            ax.annotate(f"{means[-1]:.2f}" if isinstance(means[-1], float) and means[-1] < 10 else f"{means[-1]:.0f}",
                        (gens[-1], means[-1]), textcoords="offset points", xytext=(6, 0), va="center", fontsize=8,
                        color=INK2)
        ax.set_title(title, fontsize=10, color=INK, loc="left")
        ax.xaxis.set_major_locator(matplotlib.ticker.MaxNLocator(integer=True))
        ax.set_xlabel("generation", fontsize=8, color=INK2)
        ax.grid(True, color=GRID, linewidth=0.8)
        for sp in ("top", "right"):
            ax.spines[sp].set_visible(False)
        for sp in ("left", "bottom"):
            ax.spines[sp].set_color(GRID)
        ax.tick_params(colors=INK2, labelsize=8)
        if key in ("champion_pass_rate", "hacking_rate", "caught_rate"):
            ax.set_ylim(-0.02, 1.02)
    if len(conds) > 1:
        axes.flat[0].legend(frameon=False, fontsize=8, loc="lower right")
    fig.suptitle("Self-improvement run" + (f"s ({len(runs)})" if len(runs) > 1 else f": {runs[0]['name']}"),
                 fontsize=12, color=INK, x=0.01, ha="left")
    fig.tight_layout()
    fig.savefig(out_png, dpi=160)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("runs", nargs="+")
    ap.add_argument("--out", default=None)
    ap.add_argument("--no-rejudge", action="store_true")
    a = ap.parse_args()
    runs = [load_run(r) for r in a.runs if os.path.exists(os.path.join(r, "generations.jsonl"))]
    if not runs:
        sys.exit("no runs with generations.jsonl")
    out = a.out or os.path.join(runs[0]["dir"], "report")
    os.makedirs(out, exist_ok=True)

    md = ["# Results\n"]
    summary: Dict[str, Any] = {"runs": []}
    for r in runs:
        md.append(f"## {r['name']}  (condition: {r['condition']})\n")
        md.append(table(r))
        entry = {"name": r["name"], "condition": r["condition"], "generations": r["gens"]}
        if not a.no_rejudge:
            rj = rejudge(Archive(r["dir"]), stack=VerifierStack())  # full-stack re-judge (hidden verifier + integrity checks)
            entry["rejudge"] = {k: v for k, v in rj.items() if k != "rows"}
            md.append(f"\nRe-judged ANNECS: archive-level {rj['annecs']['archive']}, champion-level {rj['annecs']['champion']}")
            md.append(f"\nRe-judge under current verifiers: {rj['rejudged']} episodes re-scored, "
                      f"{rj['flipped_total']} passes flipped.\n\n| gen | n | old pass | re-judged pass | verifier-attributed |\n|---|---|---|---|---|\n")
            for g, v in rj["by_generation"].items():
                md.append(f"| {g} | {v['n']} | {v['old_rate']:.2f} | {v['new_rate']:.2f} | {v['verifier_attributed']:+.2f} |\n")
            md.append("\n")
        summary["runs"].append(entry)

    # cross-run aggregate on the final generation
    groups: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    for r in runs:
        groups[r["condition"]].append(r["gens"][-1])
    if len(runs) > 1:
        md.append("## Final-generation aggregate (mean ± 95% CI over runs)\n\n| condition | runs | pass | ANNECS | hack% | LLM calls |\n|---|---|---|---|---|---|\n")
        agg = {}
        for cond, finals in groups.items():
            pr = ci95([s.get("champion_pass_rate") for s in finals])
            an = ci95([s.get("annecs") for s in finals])
            hk = ci95([(s.get("hacking") or {}).get("hacking_rate_of_passes") for s in finals])
            calls = ci95([(s.get("budget_cumulative") or {}).get("llm_calls") for s in finals])
            agg[cond] = {"runs": len(finals), "pass": pr, "annecs": an, "hack": hk, "llm_calls": calls}
            md.append(f"| {cond} | {len(finals)} | {_pm(pr)} | {_pm(an)} | {_pm(hk)} | {_pm(calls, 0)} |\n")
        summary["aggregate_final"] = agg
    with open(os.path.join(out, "summary.md"), "w") as f:
        f.write("".join(md))
    with open(os.path.join(out, "summary.json"), "w") as f:
        json.dump(summary, f, indent=1, ensure_ascii=False)
    plot(runs, os.path.join(out, "curves.png"))
    print(f"wrote {out}/summary.md, summary.json, curves.png")


def _pm(pair, nd=2) -> str:
    m, e = pair
    if m is None:
        return "-"
    return f"{m:.{nd}f} ± {e:.{nd}f}"


if __name__ == "__main__":
    main()

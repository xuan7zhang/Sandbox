"""Idea-2 report: search method under the static-benchmark protocol (overnight_idea2.py).

Reads <root>/runs/<condition>/seed*/generations.jsonl. Per condition and generation: champion clean pass
rate on the shared TRAIN tasks (what selection sees) and on the shared TEST tasks (never seen by selection
or the improver), cumulative accepted children and meta-LLM tokens (matched-budget check), as mean ± 95% CI
over seeds. v0's test rate across all runs' generation 0 gives the evaluation-noise floor.
Writes <root>/report/IDEA2_REPORT.md, idea2.json, idea2_curves.png.
"""
from __future__ import annotations

import argparse, glob, json, math, os


def ci(xs):
    xs = [x for x in xs if x is not None]
    if not xs:
        return None, None, 0
    m = sum(xs) / len(xs)
    if len(xs) < 2:
        return m, None, len(xs)
    sd = math.sqrt(sum((x - m) ** 2 for x in xs) / (len(xs) - 1))
    t = {2: 12.71, 3: 4.30, 4: 3.18, 5: 2.78, 6: 2.57}.get(len(xs), 1.96)
    return m, t * sd / math.sqrt(len(xs)), len(xs)


def fmt(m, h):
    return "-" if m is None else (f"{m:.3f}" if h is None else f"{m:.3f} ± {h:.3f}")


def load(root):
    groups = {}
    for d in sorted(glob.glob(os.path.join(root, "runs", "*", "seed*"))):
        if not os.path.isdir(d) or ".partial" in d:
            continue
        p = os.path.join(d, "generations.jsonl")
        if not os.path.exists(p):
            continue
        gens = [json.loads(l) for l in open(p)]
        acc, cum = 0, []
        for g in gens:
            acc += int(bool(g.get("accepted_child")))
            cum.append(acc)
        groups.setdefault(d.split(os.sep)[-2], []).append({
            "seed": d.rsplit("seed", 1)[1], "done": os.path.exists(d + ".DONE"), "gens": gens, "accepted_cum": cum})
    return groups


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", required=True)
    a = ap.parse_args()
    groups = load(a.root)
    out_dir = os.path.join(a.root, "report")
    os.makedirs(out_dir, exist_ok=True)
    v0_test = [r["gens"][0].get("champion_heldout_pass_rate") for rs in groups.values() for r in rs if r["gens"]]
    v0_train = [r["gens"][0].get("champion_pass_rate") for rs in groups.values() for r in rs if r["gens"]]
    md = [f"# Idea 2 — search method on a fixed task pool (Qwen3-30B-A3B-Instruct-2507)\n\n_updated {__import__('time').strftime('%F %T')}_\n\n"]
    m, h, n = ci(v0_test)
    m2, h2, _ = ci(v0_train)
    sd = None if n < 2 else math.sqrt(sum((x - m) ** 2 for x in v0_test if x is not None) / (n - 1))
    md.append(f"**Noise floor** (v0 at generation 0 of every run, n={n}): train {fmt(m2, h2)}, test {fmt(m, h)}"
              + (f", per-run test sd {sd:.3f}" if sd is not None else "") + "\n\n")
    md.append("Progress: " + "; ".join(f"`{k}` " + ", ".join(f"s{r['seed']}:{len(r['gens'])}{'✓' if r['done'] else ''}" for r in rs)
                                       for k, rs in sorted(groups.items())) + "\n")
    summary = {"v0_test": v0_test, "v0_train": v0_train, "conditions": {}}
    curves = {}
    for k, rs in sorted(groups.items()):
        G = max(len(r["gens"]) for r in rs)
        rows = []
        md.append(f"\n## {k} ({len(rs)} seeds)\n\n| gen | train (selection) | test (held-out) | test − v0 | accepted children (cum.) | meta tokens (cum., k) | episodes (cum.) |\n|---|---|---|---|---|---|---|\n")
        for g in range(G):
            at = [r for r in rs if len(r["gens"]) > g]
            tr = ci([r["gens"][g].get("champion_pass_rate") for r in at])
            te = ci([r["gens"][g].get("champion_heldout_pass_rate") for r in at])
            dl = ci([(r["gens"][g].get("champion_heldout_pass_rate") or 0) - (r["gens"][0].get("champion_heldout_pass_rate") or 0) for r in at])
            ac = ci([r["accepted_cum"][g] for r in at])
            tok = ci([((r["gens"][g].get("budget_cumulative") or {}).get("input_tokens", 0)
                       + (r["gens"][g].get("budget_cumulative") or {}).get("output_tokens", 0)) / 1000 for r in at])
            ep = ci([(r["gens"][g].get("budget_cumulative") or {}).get("episodes") for r in at])
            rows.append({"gen": g, "n": len(at), "train": tr[:2], "test": te[:2], "delta_test": dl[:2], "accepted_cum": ac[:2],
                         "tokens_k": tok[:2], "episodes": ep[:2]})
            md.append(f"| {g} | {fmt(*tr[:2])} | {fmt(*te[:2])} | {fmt(*dl[:2])} | {fmt(*ac[:2])} | {fmt(*tok[:2])} | {fmt(*ep[:2])} |\n")
        final = [r["gens"][-1] for r in rs if r["done"]]
        champs = [g.get("champion") for g in final]
        md.append(f"\nFinal champions (done runs): {champs}\n")
        summary["conditions"][k] = rows
        curves[k] = rows
    json.dump(summary, open(os.path.join(out_dir, "idea2.json"), "w"), indent=1)
    open(os.path.join(out_dir, "IDEA2_REPORT.md"), "w").write("".join(md))
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        fig, axes = plt.subplots(1, 3, figsize=(15, 4))
        for k, rows in curves.items():
            xs = [r["gen"] for r in rows]
            for ax, key in zip(axes, ("train", "test", "accepted_cum")):
                ys = [r[key][0] for r in rows]
                es = [r[key][1] or 0 for r in rows]
                ax.errorbar(xs, ys, yerr=es, label=k, capsize=3, marker="o")
        for ax, t in zip(axes, ("champion pass rate: train (selection)", "champion pass rate: test (held-out)",
                                "accepted children (cumulative)")):
            ax.set_title(t)
            ax.set_xlabel("generation")
        if v0_test and m is not None:
            axes[1].axhline(m, color="gray", ls="--", lw=1, label="v0 mean")
        axes[1].legend(fontsize=8)
        fig.tight_layout()
        fig.savefig(os.path.join(out_dir, "idea2_curves.png"), dpi=120)
    except Exception as e:  # noqa: BLE001
        print(f"plot skipped: {e!r}")
    print(os.path.join(out_dir, "IDEA2_REPORT.md"))


if __name__ == "__main__":
    main()

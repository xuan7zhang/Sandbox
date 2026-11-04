#!/usr/bin/env python3
"""Report for scripts/overnight_overfit.py: per condition x generation, mean ± 95% CI (t) over seeds of
  train reported   : champion clean pass rate on TRAIN as the loop judged it (raw verifiers in B)
  train hardened   : same episodes re-judged with the hardened verifiers (scripts/overfit_posthoc.py)
  VA               : reported - hardened = verifier-attributed (illusory) pass rate
  test             : champion on the held-out TEST tasks (hardened in every condition)
plus accepted children, and the gen-final contrast B vs A.
    python scripts/overfit_report.py --root /data2/ec2-user/rsi_sandbox/overfit
"""
from __future__ import annotations

import argparse, glob, json, os, statistics as st, sys
from collections import defaultdict

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _tstat import ci95_half, welch_p  # noqa: E402


def mc(xs, nd=3):
    xs = [x for x in xs if x is not None]
    if not xs:
        return "—"
    return f"{st.mean(xs):.{nd}f}" + (f" ± {ci95_half(xs):.{nd}f}" if len(xs) > 1 else "")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", required=True)
    a = ap.parse_args()
    R = defaultdict(lambda: defaultdict(lambda: defaultdict(list)))
    final = defaultdict(lambda: defaultdict(list))
    lineage = []
    for rd in sorted(glob.glob(os.path.join(a.root, "runs", "*", "seed?"))):
        cond = os.path.basename(os.path.dirname(rd))
        ph = rd + "_posthoc/posthoc.json"
        gp = os.path.join(rd, "generations.jsonl")
        if not (os.path.exists(ph) and os.path.exists(gp)):
            continue
        P = json.load(open(ph))
        gens = {json.loads(l)["gen"]: json.loads(l) for l in open(gp)}
        tr = {c["gen"]: c for c in P["active"]["champion_curve"]}
        te = {c["gen"]: c for c in P["heldout"]["champion_curve"]}
        for g in sorted(tr):
            m = R[cond][g]
            m["rep"].append(tr[g]["reported"])
            m["hard"].append(tr[g]["posthoc"])
            m["va"].append(tr[g].get("illusory"))
            m["test"].append(te.get(g, {}).get("posthoc"))
            m["acc"].append(1.0 if gens.get(g, {}).get("accepted_child") else 0.0 if g else None)
        last = max(tr)
        for k, v in (("rep", tr[last]["reported"]), ("hard", tr[last]["posthoc"]), ("va", tr[last].get("illusory")),
                     ("test", te.get(last, {}).get("posthoc")),
                     ("gain_rep", tr[last]["reported"] - tr[0]["reported"]),
                     ("gain_hard", tr[last]["posthoc"] - tr[0]["posthoc"])):
            final[cond][k].append(v)
        for g, s in sorted(gens.items()):
            if s.get("accepted_child"):
                rp = os.path.join(rd, "agents", s["accepted_child"], "rationale.md")
                txt = open(rp).read() if os.path.exists(rp) else ""
                head = " ".join(l.strip("-* #") for l in txt.splitlines() if l.strip() and "RATIONALE" not in l)[:240]
                lineage.append((cond, os.path.basename(rd), g, s["accepted_child"],
                                tr.get(g, {}).get("illusory"), head))
    md = ["# Overfit experiment — verifier-attributed progress", "",
          "mean ± 95% CI (t) over seeds. `train reported` = what the loop saw; `train hardened` = same episodes, "
          "hardened verifiers; `VA` = reported − hardened; `test` = held-out tasks, hardened verifiers.", ""]
    for cond in sorted(R):
        md += [f"## {cond}  (n={len(final[cond]['rep'])} seeds)", "",
               "| gen | train reported | train hardened | VA | test | accepted |", "|---|---|---|---|---|---|"]
        for g in sorted(R[cond]):
            m = R[cond][g]
            md.append(f"| {g} | {mc(m['rep'])} | {mc(m['hard'])} | {mc(m['va'])} | {mc(m['test'])} | {mc(m['acc'], 2)} |")
        md.append("")
    md += ["## Final generation", "", "| cond | train reported | train hardened | VA | test | Δreported vs gen0 | "
           "Δhardened vs gen0 |", "|---|---|---|---|---|---|---|"]
    for cond in sorted(final):
        f = final[cond]
        md.append(f"| {cond} | {mc(f['rep'])} | {mc(f['hard'])} | {mc(f['va'])} | {mc(f['test'])} | "
                  f"{mc(f['gain_rep'])} | {mc(f['gain_hard'])} |")
    for b, c in (("B_L3", "A_L3"), ("B_L4", "A_L4"), ("B_L4", "B_L3"), ("B_N4", "A_N4"), ("B_N4", "B_L4")):
        if len(final[b]["va"]) > 1 and len(final[c]["va"]) > 1:
            for k in ("va", "test"):
                x, y = final[b][k], final[c][k]
                md.append(f"\n{b} − {c} final {k}: {st.mean(x) - st.mean(y):+.3f} (Welch p={welch_p(x, y):.3g})")
    md += ["", "## Accepted children", "", "| cond | seed | gen | child | VA at gen | rationale |", "|---|---|---|---|---|---|"]
    for cond, sd, g, ch, va, head in lineage:
        md.append(f"| {cond} | {sd} | {g} | {ch} | {va} | {head.replace('|', '/')} |")
    os.makedirs(os.path.join(a.root, "report"), exist_ok=True)
    open(os.path.join(a.root, "report", "OVERFIT_REPORT.md"), "w").write("\n".join(md) + "\n")
    print("\n".join(md))


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""Night P2 table: A (full system) vs B (no in-loop hardening) per condition x generation, mean ± 95% CI (t).

Reads runs/night_{A,B}_matrix/<cond>/seed*/generations.jsonl, the per-matrix report.py output
(runs/night_{A,B}_matrix/report/summary.json: full-stack re-judge per generation, re-judged ANNECS) and,
when present, scripts/posthoc_audit.py output (<run>_posthoc/posthoc.json: champion curve after hardening
a copy of every task — the only re-judge that can see a loophole in B, whose verifiers are never hardened).
    python scripts/night_extract.py --out runs/report_night/P2_TABLE.md
"""
from __future__ import annotations

import argparse, glob, json, os, statistics as st, sys
from collections import defaultdict

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _tstat import ci95_half  # noqa: E402


def mc(xs, nd=3):
    xs = [x for x in xs if x is not None]
    if not xs:
        return "—"
    if len(xs) == 1:
        return f"{xs[0]:.{nd}f}"
    return f"{st.mean(xs):.{nd}f} ± {ci95_half(xs):.{nd}f}"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", default="runs")
    ap.add_argument("--out", default="runs/report_night/P2_TABLE.md")
    a = ap.parse_args()
    rows = defaultdict(lambda: defaultdict(lambda: defaultdict(list)))  # (sys,cond) -> gen -> metric -> [per seed]
    nseeds = defaultdict(set)
    lineage = []
    for S in ("A", "B"):
        mdir = os.path.join(a.root, f"night_{S}_matrix")
        rj = {}
        sp = os.path.join(mdir, "report", "summary.json")
        if os.path.exists(sp):
            for e in json.load(open(sp))["runs"]:
                rj[e["name"], e["condition"]] = e.get("rejudge")
        for rd in sorted(glob.glob(os.path.join(mdir, "*", "seed?"))):
            gp = os.path.join(rd, "generations.jsonl")
            if not os.path.exists(gp):
                continue
            cond = os.path.basename(os.path.dirname(rd))
            key = (S, cond)
            gens = [json.loads(l) for l in open(gp)]
            nseeds[key].add(os.path.basename(rd))
            cfg = json.load(open(os.path.join(rd, "config.json")))
            r = rj.get((os.path.basename(rd), cfg.get("condition"))) if rj else None
            ph = rd + "_posthoc/posthoc.json"
            ph = json.load(open(ph)) if os.path.exists(ph) else None
            phc = {c["gen"]: c for c in ph["active"]["champion_curve"]} if ph else {}
            phh = {c["gen"]: c for c in ph["heldout"]["champion_curve"]} if ph else {}
            for s in gens:
                g = s["gen"]
                m = rows[key][g]
                kids = s.get("children") or []
                m["pass"].append(s.get("champion_pass_rate"))
                m["incl"].append(s.get("champion_pass_rate_incl_hacks"))
                m["heldout"].append(s.get("champion_heldout_pass_rate"))
                m["hack"].append((s.get("hacking") or {}).get("hacking_rate_of_passes"))
                m["annecs"].append(s.get("annecs"))
                m["invalid"].append(sum(k.get("status") == "invalid" for k in kids) / len(kids) if kids else None)
                m["accepted"].append(1.0 if s.get("accepted_child") else 0.0 if kids else None)
                m["flips"].append((s.get("parent_eval") or {}).get("retest_flips"))
                bg = (r or {}).get("by_generation", {}).get(str(g)) or (r or {}).get("by_generation", {}).get(g)
                m["rj_va"].append(bg["verifier_attributed"] if bg else None)
                if g in phc:
                    m["ph_rep"].append(phc[g]["reported"])
                    m["ph_post"].append(phc[g]["posthoc"])
                    m["ph_ill"].append(phc[g]["reported"] - phc[g]["posthoc"])
                    m["ph_flip"].append(phc[g].get("flipped"))
                if g in phh:
                    m["ph_ho_ill"].append(phh[g]["reported"] - phh[g]["posthoc"])
            if r:
                rows[key]["final"]["annecs_arch"].append(r["annecs"]["archive"])
                rows[key]["final"]["annecs_champ"].append(r["annecs"]["champion"])
            # accepted lineage with rationale headline
            for s in gens:
                ac = s.get("accepted_child")
                if ac:
                    rp = os.path.join(rd, "agents", ac, "rationale.md")
                    txt = open(rp).read() if os.path.exists(rp) else ""
                    head = " ".join(l.strip("-* #") for l in txt.splitlines() if l.strip() and "RATIONALE" not in l)[:220]
                    lineage.append((S, cond, os.path.basename(rd), s["gen"], ac, head))
    md = ["# Night P2 — A (full system: adversary + minimality guard) vs B (post-hoc audit only)", "",
          "mean ± 95% CI (t) over seeds; `rejudge VA` = report.py full-stack re-judge verifier_attributed "
          "(for B this re-judges with the SAME never-hardened verifiers, so it is ≈0 by construction); "
          "`posthoc VA` = scripts/posthoc_audit.py (hardens a copy of every task with scope + minimality guard, "
          "re-judges the champion's episodes): reported − posthoc champion train pass rate.", ""]
    for key in sorted(rows):
        S, cond = key
        md += [f"## {S} / {cond}  (seeds: {', '.join(sorted(nseeds[key]))})", "",
               "| gen | champion pass | incl. hacks | held-out | hack% of passes | rejudge VA | posthoc reported | "
               "posthoc | posthoc VA (train) | posthoc VA (held-out) | ANNECS (live) | improver invalid | accepted | retest flips |",
               "|---|---|---|---|---|---|---|---|---|---|---|---|---|---|"]
        for g in sorted(k for k in rows[key] if k != "final"):
            m = rows[key][g]
            md.append(f"| {g} | {mc(m['pass'])} | {mc(m['incl'])} | {mc(m['heldout'])} | {mc(m['hack'])} | "
                      f"{mc(m['rj_va'])} | {mc(m['ph_rep'])} | {mc(m['ph_post'])} | {mc(m['ph_ill'])} | "
                      f"{mc(m['ph_ho_ill'])} | {mc(m['annecs'], 1)} | {mc(m['invalid'], 2)} | {mc(m['accepted'], 2)} | "
                      f"{mc(m['flips'], 1)} |")
        f = rows[key].get("final", {})
        if f:
            md += ["", f"re-judged ANNECS (final): archive {mc(f.get('annecs_arch', []), 1)}, "
                       f"champion {mc(f.get('annecs_champ', []), 1)}"]
        md.append("")
    md += ["## Accepted children (champion lineage) — rationale headline", "",
           "| sys | cond | seed | gen | child | rationale |", "|---|---|---|---|---|---|"]
    for S, cond, sd, g, ac, head in lineage:
        md.append(f"| {S} | {cond} | {sd} | {g} | {ac} | {head.replace('|', '/')} |")
    os.makedirs(os.path.dirname(a.out), exist_ok=True)
    open(a.out, "w").write("\n".join(md) + "\n")
    print("\n".join(md[:60]))


if __name__ == "__main__":
    main()

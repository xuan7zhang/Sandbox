"""Idea-3 report: improver information level (leak) vs verifier hacking on the fixed lax pool.

Reads <root>/runs/<L>/seed<s>/generations.jsonl and, for finished runs, <run>_posthoc/posthoc.json.
  train / test reported : champion clean pass rate under the raw lax verifiers the loop used
  train / test posthoc  : same episodes re-judged with the scope + minimality guards
  flipped               : champion's train tasks that pass raw but fail hardened (exploits)
  time-to-hack (TTH)    : first generation whose champion is not v0 and flips more train tasks than v0 did
                          at generation 0 (censored at the last generation: '>G')
  child exploit rate    : over every child the improver wrote (accepted or not), share of its train
                          episodes that pass raw but fail hardened; compared with v0's own rate
    python scripts/idea3_report.py --root /data2/ec2-user/rsi_sandbox/idea3
"""
from __future__ import annotations

import argparse, glob, json, os, statistics as st, sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

LEAKS = ["L0", "L1", "L2", "L3"]


def mean_ci(xs):
    xs = [x for x in xs if x is not None]
    if not xs:
        return "—"
    if len(xs) == 1:
        return f"{xs[0]:.3f}"
    from _tstat import ci95_half
    h = ci95_half(xs)
    return f"{st.mean(xs):.3f} ± {h:.3f}"


def load(rd):
    gens = [json.loads(l) for l in open(os.path.join(rd, "generations.jsonl"))] if os.path.exists(
        os.path.join(rd, "generations.jsonl")) else []
    ph = rd + "_posthoc/posthoc.json"
    ph = json.load(open(ph)) if os.path.exists(ph) and os.path.exists(rd + ".DONE") else None
    return gens, ph


def run_stats(gens, ph):
    r = {"gens": len(gens), "done": ph is not None,
         "accepted": sum(1 for s in gens if s.get("accepted_child")),
         "children": sum(len(s.get("children") or []) for s in gens)}
    if not ph:
        return r
    cc = ph["active"]["champion_curve"]
    base = cc[0]["flipped"] if cc else 0
    r["v0_flipped"] = base
    r["final_flipped"] = cc[-1]["flipped"] if cc else None
    tth = None
    for row in cc:
        if row["champion"] != "v0" and row["flipped"] > base:
            tth = row["gen"]
            break
    r["tth"] = tth
    r["censor"] = cc[-1]["gen"] if cc else None
    ba = ph.get("by_agent", {})

    def rate(d):
        return (d["reported"] - d["posthoc"]) / d["n"] if d["n"] else 0.0
    v0 = ba.get("v0")
    r["v0_exploit_rate"] = rate(v0) if v0 else None
    kids = {k: rate(d) for k, d in ba.items() if k != "v0"}
    r["child_exploit_rate_mean"] = st.mean(kids.values()) if kids else None
    r["child_exploit_rate_max"] = max(kids.values()) if kids else None
    r["children_exploiting_more_than_v0"] = sum(x > (r["v0_exploit_rate"] or 0) + 1e-9 for x in kids.values())
    r["n_children_scored"] = len(kids)
    return r


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", required=True)
    a = ap.parse_args()
    out_dir = os.path.join(a.root, "report")
    os.makedirs(out_dir, exist_ok=True)
    data = {}
    for L in LEAKS:
        for rd in sorted(glob.glob(os.path.join(a.root, "runs", L, "seed*"))):
            if not os.path.isdir(rd) or rd.endswith("_posthoc") or ".partial" in rd:
                continue
            gens, ph = load(rd)
            data.setdefault(L, {})[os.path.basename(rd)] = {"gens": gens, "ph": ph, "stats": run_stats(gens, ph)}
    md = ["# Idea 3 — improver information leak vs verifier hacking (lax pool, Qwen3-30B-A3B-Instruct-2507)", "",
          f"_updated {__import__('time').strftime('%F %T')}_", "",
          "Loop judges with the RAW lax verifiers + rule-based integrity stack (no guards, no LLM judge); "
          "improver mode=score. 'posthoc' = same episodes re-judged with scope + minimality guards. "
          "'flipped' = champion train tasks passing raw but failing hardened (exploits).", ""]
    md += ["## Summary per leak level", "",
           "| leak | runs done | accepted children | TTH (gen; '>G' censored) | champion flipped (final) | v0 flipped | "
           "child exploit rate (mean) | v0 exploit rate | children exploiting > v0 | final train reported | final train posthoc | final test posthoc |",
           "|---|---|---|---|---|---|---|---|---|---|---|---|"]
    summary = {}
    for L in LEAKS:
        runs = data.get(L, {})
        S = [v["stats"] for v in runs.values()]
        D = [s for s in S if s["done"]]
        fin = [v["ph"] for v in runs.values() if v["ph"]]
        tth = [(f"{s['tth']}" if s["tth"] is not None else f">{s['censor']}") for s in D]
        last = lambda ph, k, part: ph[part]["champion_curve"][-1][k] if ph[part]["champion_curve"] else None
        row = {"done": len(D), "runs": len(S), "accepted": [s["accepted"] for s in S], "tth": tth,
               "final_flipped": [s["final_flipped"] for s in D], "v0_flipped": [s["v0_flipped"] for s in D],
               "child_rate": [s["child_exploit_rate_mean"] for s in D], "v0_rate": [s["v0_exploit_rate"] for s in D],
               "kids_more": [f"{s['children_exploiting_more_than_v0']}/{s['n_children_scored']}" for s in D],
               "train_rep": [last(p, "reported", "active") for p in fin],
               "train_post": [last(p, "posthoc", "active") for p in fin],
               "test_post": [last(p, "posthoc", "heldout") for p in fin]}
        summary[L] = {**row, "runs_detail": {k: v["stats"] for k, v in runs.items()}}
        md.append(f"| {L} | {len(D)}/{len(S)} | {row['accepted']} | {', '.join(tth) or '—'} | {row['final_flipped']} | "
                  f"{row['v0_flipped']} | {mean_ci(row['child_rate'])} | {mean_ci(row['v0_rate'])} | "
                  f"{', '.join(row['kids_more']) or '—'} | {mean_ci(row['train_rep'])} | {mean_ci(row['train_post'])} | "
                  f"{mean_ci(row['test_post'])} |")
    md += ["", "## Champion curves (train, finished runs)", ""]
    for L in LEAKS:
        fin = {k: v["ph"] for k, v in data.get(L, {}).items() if v["ph"]}
        if not fin:
            continue
        G = max(len(p["active"]["champion_curve"]) for p in fin.values())
        md += [f"### {L} ({len(fin)} runs)", "", "| gen | reported | posthoc | flipped (per run) | test posthoc |",
               "|---|---|---|---|---|"]
        for g in range(G):
            rows = [p["active"]["champion_curve"][g] for p in fin.values() if g < len(p["active"]["champion_curve"])]
            th = [p["heldout"]["champion_curve"][g]["posthoc"] for p in fin.values()
                  if g < len(p["heldout"]["champion_curve"])]
            md.append(f"| {g} | {mean_ci([r['reported'] for r in rows])} | {mean_ci([r['posthoc'] for r in rows])} | "
                      f"{[r['flipped'] for r in rows]} | {mean_ci(th)} |")
        md.append("")
    md += ["## Progress", ""] + [f"- {L}: " + ", ".join(f"{k}:{v['stats']['gens']}{'✓' if v['stats']['done'] else ''}"
                                                       for k, v in data.get(L, {}).items()) for L in LEAKS]
    open(os.path.join(out_dir, "IDEA3_REPORT.md"), "w").write("\n".join(md) + "\n")
    json.dump(summary, open(os.path.join(out_dir, "idea3.json"), "w"), indent=1, default=str)
    print("\n".join(md[:20]))


if __name__ == "__main__":
    main()

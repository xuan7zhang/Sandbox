"""Idea-3 redesign: time-to-hack vs improver leakage, for a depth-1 and a depth-2 loophole.
    python3 toy/run_tth.py --seeds 6 --gens 8 --parallel 2
"""
import argparse, json, math, os, shutil, statistics as st, sys
from concurrent.futures import ProcessPoolExecutor
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from toy.toy import run_toy  # noqa: E402
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "results")


def job(a):
    name, kw = a
    rd = os.path.join(OUT, "runs_tth", name); shutil.rmtree(rd, ignore_errors=True)
    try:
        r = run_toy(rd, **kw)
    except Exception as e:  # noqa: BLE001
        return name, {"error": repr(e)}
    return name, {"time_to_hack": r["time_to_hack"], "final_reported": r["per_gen"][-1]["reported"],
                  "final_rejudged": r["per_gen"][-1]["rejudged"], "gens": len(r["per_gen"])}


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--seeds", type=int, default=6); ap.add_argument("--gens", type=int, default=8)
    ap.add_argument("--parallel", type=int, default=2); a = ap.parse_args()
    jobs = [(f"d{d}_leak{l}_s{s}", dict(seed=s, leak=l, selection="best", generations=a.gens, depth=d, children_per_gen=2))
            for d in (1, 2) for l in range(4) for s in range(a.seeds)]
    with ProcessPoolExecutor(a.parallel) as ex:
        res = dict(ex.map(job, jobs))
    summ = {}
    for d in (1, 2):
        for l in range(4):
            rows = [res[f"d{d}_leak{l}_s{s}"] for s in range(a.seeds) if "error" not in res[f"d{d}_leak{l}_s{s}"]]
            tth = [r["time_to_hack"] for r in rows]
            found = [t for t in tth if t is not None]
            summ[f"depth{d}/leak{l}"] = {"n": len(rows), "hacked_by_end": round(len(found) / max(1, len(rows)), 2),
                                        "median_time_to_hack": (st.median(found) if found else None),
                                        "mean_tth_censored": round(st.mean([t if t is not None else a.gens + 1 for t in tth]), 2),
                                        "tth_all": tth,
                                        "illusory_final": round(st.mean(r["final_reported"] - r["final_rejudged"] for r in rows), 3)}
    json.dump({"summary": summ, "raw": res}, open(os.path.join(OUT, "tth.json"), "w"), indent=1)
    for k, v in summ.items():
        print(f"{k:14} hacked_by_end={v['hacked_by_end']:<5} median_tth={v['median_time_to_hack']}  mean_tth(cens)={v['mean_tth_censored']}  tth={v['tth_all']}  illusory={v['illusory_final']}")


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""Post-hoc audit of an overfit-pool run: scripts/posthoc_audit.py, but every task's verifier in the copy is
replaced by its pre-built HARDENED version from <pool>_hard.json (built by build_overfit_pool.py, verified to
pass the reference and reject shotgun / wrecking), instead of re-deriving guards with the core functions
(whose minimality guard skips trajectory-checking verifiers, adversary.py:178).
    python scripts/overfit_posthoc.py <run_dir> --pool /data2/ec2-user/rsi_sandbox/overfit/pool
Writes <run_dir>_posthoc/posthoc.json (same schema as posthoc_audit.py).
"""
from __future__ import annotations

import argparse, json, os, sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import posthoc_audit as pa  # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("run_dir")
    ap.add_argument("--pool", required=True)
    ap.add_argument("--out", default=None)
    a = ap.parse_args()
    hard = json.load(open(a.pool + "_hard.json"))
    H = {t["id"]: t for t in hard["train"] + hard["test"]}

    def swap(t):
        h = H[t["id"]]
        t.setdefault("meta", {})["minimality_guard"] = True
        if t["verifier"]["code"] == h["verifier"]["code"]:
            return False
        t["verifier"]["code"] = h["verifier"]["code"]
        return True
    pa.add_scope_guard = swap
    pa.add_minimality_guard = lambda t: False
    sys.argv = [sys.argv[0], a.run_dir] + (["--out", a.out] if a.out else [])
    pa.main()


if __name__ == "__main__":
    main()

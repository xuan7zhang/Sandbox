"""Paired acceptance, held-out tasks and fail-loud guards."""
import os
import subprocess
import sys

import pytest
import yaml

from sandbox.llm import MockLLM, preflight
from sandbox.llm.mock_scripts import FollowInstruction, WreckingAdversary
from sandbox.loop import Loop, LoopConfig
from sandbox.loop.improver import MockImprover
from sandbox.proposer import MockProposer

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LIMITED = os.path.join(os.path.dirname(__file__), "fixtures", "agent_limited")


class SpyImprover(MockImprover):
    """MockImprover that records which task ids the improver was shown."""

    def __init__(self, **kw):
        super().__init__(**kw)
        self.seen = set()

    def improve(self, code, diagnostics):
        for item in diagnostics.get("failures", []) + diagnostics.get("hacks", []):
            self.seen.add(item["task_id"])
        return super().improve(code, diagnostics)


def _loop(tmp_path, improver=None, proposer=None, **kw):
    cfg = LoopConfig(run_dir=str(tmp_path / "run"), generations=kw.pop("generations", 2), tasks_per_gen=4,
                     initial_tasks=6, isolate=False, children_per_gen=1, initial_agent_dir=LIMITED, **kw)
    return Loop(cfg, proposer=proposer or MockProposer(seed=1),
                improver=improver or MockImprover(bump_constant="MAX_ACTIONS", bump_by=2),
                solver_llm_factory=lambda: MockLLM(FollowInstruction()),
                adversary_llm_factory=lambda: MockLLM(WreckingAdversary()), log=lambda s: None)


def test_paired_eval_reruns_parent_in_the_same_generation(tmp_path):
    loop = _loop(tmp_path, generations=2)
    sums = loop.run()
    a = loop.archive
    for g, s in enumerate(sums, start=1):  # run() returns generations 1..G
        parent = s["parent"]
        active = {t["id"] for t in a.tasks("active") if t["generation"] <= g}
        fresh = {e["task_id"] for e in a.episodes(agent_version=parent, purpose="eval", generation=g)}
        assert active <= fresh  # every active task re-run for the parent in this generation
        pe = s["parent_eval"]
        assert pe["retest_tasks"] > 0
        assert pe["retest_flips"] == 0  # the scripted solver is deterministic: no test-retest noise
    assert sums[-1]["champion"] != "v0"


def test_accept_margin_blocks_gains_below_it(tmp_path):
    loop = _loop(tmp_path, generations=2, accept_margin=10_000)
    sums = loop.run()
    assert all(s["accepted_child"] is None for s in sums)
    assert sums[-1]["champion"] == "v0"


def test_unpaired_mode_keeps_the_old_gate(tmp_path):
    loop = _loop(tmp_path, generations=2, paired_eval=False)
    sums = loop.run()
    assert all(s["parent_eval"] is None for s in sums)
    assert sums[-1]["champion"] != "v0"


def test_heldout_tasks_are_report_only(tmp_path):
    spy = SpyImprover(bump_constant="MAX_ACTIONS", bump_by=2)
    loop = _loop(tmp_path, improver=spy, generations=2, initial_heldout=3, heldout_per_gen=2)
    sums = loop.run()
    a = loop.archive
    held = {t["id"] for t in a.tasks("heldout")}
    active = {t["id"] for t in a.tasks("active")}
    assert held and not (held & active)
    # never used for selection / acceptance / diagnostics
    assert not any(e["task_id"] in held for e in a.episodes(purpose="eval"))
    assert not (spy.seen & held)
    # but the champion is scored on all of them, every generation
    for g, s in enumerate(sums, start=1):
        assert s["tasks_heldout"] > 0
        assert s["champion_heldout_pass_rate"] is not None
        assert s["champion_heldout_pass_rate_gen0"] is not None
        champ_held = {e["task_id"] for e in a.episodes(agent_version=s["champion"], purpose="heldout")}
        gen_held = {t["id"] for t in a.tasks("heldout") if t["generation"] <= g}
        assert gen_held <= champ_held
    # held-out tasks never count towards ANNECS
    assert all(r["novel_at_creation"] is None for r in a.task_rows() if r["id"] in held)


def test_empty_generation_zero_raises(tmp_path):
    class NoTasks(MockProposer):
        def propose(self, *args, **kw):
            return []

    loop = _loop(tmp_path, proposer=NoTasks(seed=0))
    with pytest.raises(RuntimeError, match="no accepted task"):
        loop.run()


UNREACHABLE = {"provider": "openai", "model": "some/model", "base_url": "http://127.0.0.1:9/v1"}


def test_preflight_rejects_unreachable_endpoint():
    with pytest.raises(RuntimeError, match="cannot reach"):
        preflight({"solver": UNREACHABLE}, timeout_s=3)
    preflight({"solver": {"provider": "mock"}})  # mock and anthropic entries are not probed


@pytest.mark.parametrize("script", ["audit_verifiers.py", "run_loop.py"])
def test_scripts_exit_nonzero_without_a_server(tmp_path, script):
    cfg = {"loop": {"run_dir": str(tmp_path / "r"), "generations": 1},
           "models": {k: dict(UNREACHABLE) for k in ("solver", "proposer", "improver")}}
    p = tmp_path / "cfg.yaml"
    p.write_text(yaml.safe_dump(cfg))
    extra = ["--out", str(tmp_path / "audit")] if script == "audit_verifiers.py" else []
    r = subprocess.run([sys.executable, os.path.join(ROOT, "scripts", script), str(p), *extra],
                       capture_output=True, text=True, cwd=ROOT, timeout=120)
    assert r.returncode != 0
    assert "preflight failed" in r.stderr

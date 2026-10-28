import json
import os

from sandbox.archive import Archive
from sandbox.llm import MockLLM
from sandbox.llm.mock_scripts import FollowInstruction, WreckingAdversary
from sandbox.loop import Loop, LoopConfig
from sandbox.loop.improver import MockImprover, RandomImprover, LLMImprover, validate_agent_code
from sandbox.metrics import annecs, clade_metaproductivity
from sandbox.proposer import MockProposer

LIMITED = os.path.join(os.path.dirname(__file__), "fixtures", "agent_limited")


def _loop(tmp_path, **kw):
    cfg = LoopConfig(run_dir=str(tmp_path / "run"), generations=kw.pop("generations", 3), tasks_per_gen=4,
                     initial_tasks=6, isolate=False, children_per_gen=kw.pop("children_per_gen", 1),
                     initial_agent_dir=LIMITED, difficulty=kw.pop("difficulty", "frontier"), **kw)
    return Loop(cfg, proposer=MockProposer(seed=1),
                improver=MockImprover(bump_constant="MAX_ACTIONS", bump_by=2),
                solver_llm_factory=lambda: MockLLM(FollowInstruction()),
                adversary_llm_factory=lambda: MockLLM(WreckingAdversary()), log=lambda s: None)


def test_closed_loop_improves_and_counts_annecs(tmp_path):
    loop = _loop(tmp_path, generations=3)
    sums = loop.run()
    a = loop.archive
    # the limited agent (2 actions) fails difficulty>=3 tasks; bumping MAX_ACTIONS unlocks them
    assert sums[-1]["champion"] != "v0"
    rates = [s["champion_pass_rate"] for s in sums]
    assert rates[-1] >= rates[0]
    assert annecs(a) >= 1  # at least one task that was novel at creation was later solved
    assert sums[-1]["annecs"] == annecs(a, 3)
    # hacking is a first-class metric and the mock solver never hacks
    assert all(s["hacking"]["hacking_rate_of_passes"] in (0.0, None) for s in sums)
    # adversary found the loose verifiers and they were hardened + versioned
    assert all(s["adversary"]["hardened"] >= 1 for s in sums)
    hist = os.listdir(os.path.join(a.run_dir, "tasks", "history"))
    assert any(f.endswith(".v2.json") for f in hist)
    # lineage + CMP are computable
    champ = sums[-1]["champion"]
    assert clade_metaproductivity(a, "v0") is not None
    assert champ in a.clade("v0")
    # budget accounting is monotone
    b = [s["budget_cumulative"]["llm_calls"] for s in sums]
    assert b == sorted(b) and b[-1] > 0
    # generations.jsonl written
    lines = open(os.path.join(a.run_dir, "generations.jsonl")).read().strip().splitlines()
    assert len(lines) == 4 and json.loads(lines[-1])["gen"] == 3


def test_rejected_children_do_not_become_champion(tmp_path):
    cfg = LoopConfig(run_dir=str(tmp_path / "run"), generations=2, tasks_per_gen=3, initial_tasks=4, isolate=False,
                     initial_agent_dir=LIMITED, adversary=False)
    loop = Loop(cfg, proposer=MockProposer(seed=2), improver=MockImprover(break_every=1),
                solver_llm_factory=lambda: MockLLM(FollowInstruction()), log=lambda s: None)
    sums = loop.run()
    assert all(s["accepted_child"] is None for s in sums)
    assert all(c["status"] == "rejected" for s in sums for c in s["children"])
    assert sums[-1]["champion"] == "v0"


def test_resume_from_existing_archive(tmp_path):
    loop = _loop(tmp_path, generations=1)
    loop.run()
    loop2 = _loop(tmp_path, generations=1)
    loop2._init_generation_zero()
    assert loop2.champion == loop.champion
    assert len(loop2.archive.tasks("active")) == len(loop.archive.tasks("active"))


def test_rollback_task_verifier(tmp_path):
    loop = _loop(tmp_path, generations=1)
    loop.run()
    a = loop.archive
    t = next(x for x in a.task_rows() if x["verifier_version"] >= 2)
    old = a.rollback_task_verifier(t["id"], 1)
    assert "_rsi_scope_guard" not in old["verifier"]["code"]
    assert next(x for x in a.task_rows() if x["id"] == t["id"])["verifier_version"] == 1


def test_random_baseline_and_llm_improver_parse():
    seen = {}

    def script(messages, tools):
        seen["prompt"] = messages[-1]["content"]
        return "RATIONALE:\nadd retries\n```python\ndef run(task, tools, env, llm):\n    return 'x'\n```"

    code, rationale = LLMImprover(MockLLM(script)).improve("def run(task, tools, env, llm): pass", {"failures": []})
    assert code.startswith("def run") and rationale == "add retries" and validate_agent_code(code)[0]
    assert "DIAGNOSTICS" in seen["prompt"]
    code, _ = RandomImprover(MockLLM(script)).improve("def run(task, tools, env, llm): pass", {"failures": [1]})
    assert "no diagnostics" in seen["prompt"]
    assert not validate_agent_code("import subprocess\ndef run(a,b,c,d): pass")[0]

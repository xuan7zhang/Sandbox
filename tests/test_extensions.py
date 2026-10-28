import json
import os
import subprocess
import sys

from sandbox.llm import MockLLM
from sandbox.llm.mock_scripts import FollowInstruction, WreckingAdversary
from sandbox.loop import Loop, LoopConfig
from sandbox.loop.improver import MockImprover
from sandbox.metrics.rejudge import rejudge
from sandbox.proposer import MockProposer, TaskFilter
from sandbox.solver import run_episode
from sandbox.tasks import public_view
from sandbox.verifier import VerifierStack
from sandbox.verifier.judge import RubricJudge
from sandbox.world import get_world, list_worlds

LIMITED = os.path.join(os.path.dirname(__file__), "fixtures", "agent_limited")
V0 = os.path.join(os.path.dirname(__file__), "..", "sandbox", "solver", "agents", "v0")
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _loop(run_dir, world="bizops", generations=1):
    cfg = LoopConfig(run_dir=run_dir, world=world, generations=generations, tasks_per_gen=3, initial_tasks=4,
                     isolate=False, initial_agent_dir=LIMITED)
    return Loop(cfg, proposer=MockProposer(seed=1), improver=MockImprover(bump_constant="MAX_ACTIONS", bump_by=2),
                solver_llm_factory=lambda: MockLLM(FollowInstruction()),
                adversary_llm_factory=lambda: MockLLM(WreckingAdversary()), log=lambda s: None)


def test_tickets_world_constraints():
    assert "tickets" in list_worlds()
    w = get_world("tickets", seed=1)
    for m in w.call("list_members").output:
        assert m["load"] <= m["capacity"]
    t = next(t for t in w.state()["tickets"] if t["blocked_by"] and t["status"] != "done")
    assert not w.call("transition", {"ticket_id": t["id"], "status": "in_progress"}).ok
    assert "cycle" in w.call("add_blocker", {"ticket_id": t["blocked_by"][0], "blocked_by": t["id"]}).error
    assert not w.call("start_sprint", {"sprint_id": "s1"}).ok  # closed
    s = w.call("create_sprint", {"name": "X", "capacity_points": 5}).output
    assert "active" in w.call("start_sprint", {"sprint_id": s["id"]}).error  # another sprint active
    assert w.call("close_sprint", {"sprint_id": "s2"}).ok and w.call("start_sprint", {"sprint_id": s["id"]}).ok


def test_loop_runs_on_tickets_world(tmp_path):
    loop = _loop(str(tmp_path / "r"), world="tickets", generations=2)
    sums = loop.run()
    assert sums[-1]["tasks_active"] >= 7 and sums[-1]["champion_pass_rate"] is not None
    assert all(s["adversary"]["attacks"] > 0 for s in sums)


def test_rejudge_flips_after_verifier_tightening(tmp_path):
    loop = _loop(str(tmp_path / "r"))
    loop.run()
    a = loop.archive
    r0 = rejudge(a)
    assert r0["episodes"] > 0 and r0["flipped_total"] == 0
    t = a.tasks("active")[0]
    t["verifier"]["code"] = "def verify(a, b, c, d): return False"
    a.update_task(t, "tightened")
    r1 = rejudge(a)
    assert r1["rejudged"] > 0 and r1["flipped_total"] >= 1
    assert any(v["verifier_attributed"] > 0 for v in r1["by_generation"].values())


def test_rubric_judge_flags_only_passes():
    seen = {"n": 0}

    def script(messages, tools):
        seen["n"] += 1
        return '{"exploit": true, "confidence": 0.9, "reason": "created duplicate"}'

    w = get_world("bizops", seed=5)
    t = TaskFilter().run(MockProposer(seed=1).propose(w, 1, generation=1, existing=[], difficulty=1), []).accepted[0]
    stack = VerifierStack().add(RubricJudge(MockLLM(script)))
    w = get_world(t["world"], seed=t["seed"])
    ep = run_episode(V0, w, public_view(t, w.describe()), llm=MockLLM(FollowInstruction()), isolate=False)
    v = stack.judge(t, ep)
    assert v.passed and v.hacking_suspected and seen["n"] == 1
    assert any(f.check == "rubric_judge" and f.severity == "hack" for f in v.flags)
    # judge is not called when the hidden verifier fails
    from sandbox.llm.mock_scripts import DoNothing

    w = get_world(t["world"], seed=t["seed"])
    ep = run_episode(V0, w, public_view(t, w.describe()), llm=MockLLM(DoNothing()), isolate=False)
    stack.judge(t, ep)
    assert seen["n"] == 1


def test_cli_matrix_and_report(tmp_path):
    cfg = os.path.join(ROOT, "configs", "minimal_mock.yaml")
    import yaml

    c = yaml.safe_load(open(cfg))
    c["loop"]["run_dir"] = str(tmp_path / "mm")
    c["loop"]["generations"] = 1
    c["loop"]["initial_agent_dir"] = os.path.join(ROOT, "tests", "fixtures", "agent_limited")
    p = tmp_path / "cfg.yaml"
    p.write_text(yaml.safe_dump(c))
    r = subprocess.run([sys.executable, os.path.join(ROOT, "scripts", "run_matrix.py"), str(p), "--seeds", "0", "1",
                        "--conditions", "best", "random", "--parallel", "2"], capture_output=True, text=True, cwd=ROOT)
    assert r.returncode == 0, r.stdout + r.stderr
    rep = tmp_path / "mm_matrix" / "report"
    assert (rep / "curves.png").exists()
    s = json.load(open(rep / "summary.json"))
    assert set(s["aggregate_final"]) == {"best", "random:random-improver"} or set(s["aggregate_final"]) == {"best", "random"}
    assert all("rejudge" in run for run in s["runs"])

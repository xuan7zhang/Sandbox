"""One self-improvement run = a sequence of generations. Each generation:

  1. PROPOSE   new tasks at the champion's frontier difficulty  -> filter -> archive
  2. ATTACK    adversary vs. new tasks -> harden verifiers -> archive (versioned)
  3. PROBE     champion on new tasks  -> novel_at_creation flag (for ANNECS)
  4. SELECT    a parent from the archive (best | cmp | random)
  5. IMPROVE   improver(parent code, diagnostics) -> candidate child(ren)
  6. EVALUATE  child on the full active task set (same set as parent, re-evaluating
               the parent where verifier versions changed)
  7. ACCEPT    child if non-hacking pass rate strictly improves on the parent
  8. REPORT    ANNECS, hacking rate, CMP, budget, acceptance stats

All LLM usage (solver, proposer, improver, adversary) is metered so that a run
with `selection=random` + `RandomImprover` is a matched-budget baseline.
"""
from __future__ import annotations

import json
import os
import random
import time
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional

from ..archive import Archive
from ..llm import LLM, Usage
from ..metrics import generation_summary
from ..proposer import TaskFilter
from ..solver.runner import run_episode
from ..tasks import public_view
from ..verifier import VerifierStack
from ..verifier.adversary import Adversary
from ..world import get_world
from .improver import validate_agent_code

V0_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "solver", "agents", "v0")


@dataclass
class LoopConfig:
    run_dir: str
    world: str = "bizops"
    generations: int = 3
    tasks_per_gen: int = 8
    initial_tasks: int = 12
    candidate_multiplier: float = 1.5  # ask the proposer for more than needed; filters trim
    difficulty: str = "frontier"  # "frontier" or an int as string
    children_per_gen: int = 1
    selection: str = "best"  # best | cmp | random
    base_seed: int = 1000
    isolate: bool = True
    max_steps_cap: int = 80
    episode_timeout_s: float = 600.0
    adversary: bool = True
    minimality_guard: bool = True  # proactive reference-derived verifier hardening (ablation: False)
    initial_agent_dir: str = V0_DIR
    solver_llm_cfg: Dict[str, Any] = field(default_factory=dict)  # for subprocess solver
    rng_seed: int = 0


class Loop:
    def __init__(self, cfg: LoopConfig, *, proposer, improver, stack: Optional[VerifierStack] = None,
                 solver_llm_factory: Optional[Callable[[], LLM]] = None, adversary_llm_factory: Optional[Callable[[], LLM]] = None,
                 hardening_llm: Optional[LLM] = None, log: Callable[[str], None] = print):
        self.cfg = cfg
        self.proposer = proposer
        self.improver = improver
        self.stack = stack or VerifierStack()
        self.solver_llm_factory = solver_llm_factory  # in-process mode (tests)
        self.adversary_llm_factory = adversary_llm_factory
        self.hardening_llm = hardening_llm
        self.filter = TaskFilter()
        self.archive = Archive(cfg.run_dir)
        self.rng = random.Random(cfg.rng_seed)
        self.log = log
        self.champion: Optional[str] = None
        self._meta_usage: Dict[str, Usage] = {}
        os.makedirs(cfg.run_dir, exist_ok=True)
        with open(os.path.join(cfg.run_dir, "config.json"), "w") as f:
            d = {k: (v if isinstance(v, (int, float, str, bool, dict, list)) else str(v)) for k, v in cfg.__dict__.items()}
            d["condition"] = cfg.selection + (":random-improver" if getattr(improver, "name", "").endswith(":random") else "")
            d["proposer"], d["improver"] = getattr(proposer, "name", "?"), getattr(improver, "name", "?")
            json.dump(d, f, indent=1)

    # ------------------------------------------------------------------ public
    def run(self) -> List[Dict[str, Any]]:
        self._init_generation_zero()
        summaries = []
        for g in range(1, self.cfg.generations + 1):
            summaries.append(self.run_generation(g))
        return summaries

    # ------------------------------------------------------------------ gen 0
    def _init_generation_zero(self) -> None:
        a = self.archive
        if a.agents():
            self.champion = next((x["version"] for x in a.agents(status="champion")), None) or a.agents()[0]["version"]
            self.log(f"[gen0] resuming; champion={self.champion}")
            return
        a.start_generation(0)
        a.add_agent_from_dir("v0", self.cfg.initial_agent_dir, parent=None, generation=0, notes="initial agent",
                             status="champion")
        self.champion = "v0"
        world = get_world(self.cfg.world, seed=self.cfg.base_seed)
        new = self._propose_and_filter(world, self.cfg.initial_tasks, generation=0, difficulty=self._difficulty_target())
        adv = self._attack_and_harden(new) if self.cfg.adversary else None
        self._evaluate("v0", new, generation=0, purpose="eval")
        for t in new:
            a.set_task_fields(t["id"], novel_at_creation=int(not self._solved_by(t["id"], "v0")))
        a.finish_generation(0, generation_summary(a, 0, "v0", {"adversary": _strip(adv), "accepted_child": None}))
        self.log(f"[gen0] v0 pass rate={a.pass_rate('v0')} on {len(new)} tasks")

    # ------------------------------------------------------------------ one generation
    def run_generation(self, g: int) -> Dict[str, Any]:
        a, cfg = self.archive, self.cfg
        a.start_generation(g)
        t0 = time.time()
        usage_before = self._meta_usage_snapshot()

        # 1. propose
        world = get_world(cfg.world, seed=cfg.base_seed + g)
        diff = self._difficulty_target()
        new = self._propose_and_filter(world, cfg.tasks_per_gen, generation=g, difficulty=diff)
        # 2. attack + harden
        adv = self._attack_and_harden(new) if cfg.adversary else None
        # 3. probe champion on new tasks -> novelty
        self._evaluate(self.champion, new, generation=g, purpose="eval")
        for t in new:
            a.set_task_fields(t["id"], novel_at_creation=int(not self._solved_by(t["id"], self.champion)))

        # 4. select parent
        parent = self._select_parent()
        active = a.tasks("active")
        self._ensure_evaluated(parent, active, g)  # parent must have fresh verdicts on every active task
        parent_rate = a.pass_rate(parent, task_ids=[t["id"] for t in active])

        # 5-7. improve, evaluate, accept
        accepted: Optional[str] = None
        children: List[Dict[str, Any]] = []
        for k in range(cfg.children_per_gen):
            version = f"g{g}c{k}"
            diag = self._diagnostics(parent, active)
            code, rationale = self.improver.improve(a.agent_code(parent), diag)
            if code is None:
                children.append({"version": version, "status": "invalid", "reason": rationale})
                continue
            ok, why = validate_agent_code(code)
            if not ok:
                children.append({"version": version, "status": "invalid", "reason": why})
                continue
            a.add_agent(version, code, parent=parent, generation=g, notes=f"improver={self.improver.name}",
                        rationale=rationale)
            self._evaluate(version, active, generation=g, purpose="eval")
            rate = a.pass_rate(version, task_ids=[t["id"] for t in active])
            improved = rate is not None and parent_rate is not None and rate > parent_rate + 1e-9
            if improved:
                a.set_agent_status(version, "alive")
                if accepted is None or rate > (a.pass_rate(accepted, task_ids=[t["id"] for t in active]) or 0):
                    accepted = version
            else:
                a.set_agent_status(version, "rejected")
            children.append({"version": version, "status": "alive" if improved else "rejected",
                             "pass_rate": rate, "parent_pass_rate": parent_rate})

        # champion update
        if accepted is not None:
            champ_rate = a.pass_rate(self.champion, task_ids=[t["id"] for t in active])
            acc_rate = a.pass_rate(accepted, task_ids=[t["id"] for t in active])
            if champ_rate is None or (acc_rate or 0) > champ_rate:
                a.set_agent_status(self.champion, "alive")
                a.set_agent_status(accepted, "champion")
                self.champion = accepted

        # 8. report
        usage_delta = self._meta_usage_delta(usage_before)
        summary = generation_summary(a, g, self.champion, {
            "parent": parent, "parent_pass_rate": parent_rate, "children": children, "accepted_child": accepted,
            "difficulty_target": diff, "proposer_acceptance": self._last_filter_summary,
            "adversary": _strip(adv), "meta_llm_usage": usage_delta, "wall_s": round(time.time() - t0, 1),
        })
        a.finish_generation(g, summary)
        self.log(f"[gen{g}] champion={self.champion} rate={summary['champion_pass_rate']} "
                 f"annecs={summary['annecs']} hack={summary['hacking']['hacking_rate_of_passes']} "
                 f"tasks={summary['tasks_active']} accepted={accepted}")
        return summary

    # ------------------------------------------------------------------ pieces
    def _propose_and_filter(self, world, n: int, *, generation: int, difficulty: int) -> List[Dict[str, Any]]:
        existing = self.archive.tasks("active")
        frontier = self._frontier_by_tag()
        want = max(n, int(n * self.cfg.candidate_multiplier))
        cands = self.proposer.propose(world, want, generation=generation, existing=existing, frontier=frontier,
                                      difficulty=difficulty)
        rep = self.filter.run(cands, existing)
        self._last_filter_summary = rep.summary()
        accepted = rep.accepted[:n]
        for t in accepted:
            t["max_steps"] = min(t["max_steps"], self.cfg.max_steps_cap)
            self.archive.add_task(t)
        self.log(f"[gen{generation}] proposed {len(cands)} -> accepted {len(accepted)} "
                 f"(rejected: {rep.summary()['rejected_by']})")
        return accepted

    def _attack_and_harden(self, tasks: List[Dict[str, Any]]) -> Dict[str, Any]:
        llm = self.adversary_llm_factory() if self.adversary_llm_factory else None
        adv = Adversary(self.stack, llm_cfg=self.cfg.solver_llm_cfg, llm=llm, isolate=self.cfg.isolate and llm is None,
                        timeout_s=self.cfg.episode_timeout_s, hardening_llm=self.hardening_llm,
                        minimality_guard=self.cfg.minimality_guard)
        results = {"attacks": 0, "attack_pass_rate": None, "caught_rate": None, "undetected_rate": None, "hardened": 0,
                   "results": []}
        for t in tasks:
            if self.adversary_llm_factory:
                adv.llm = self.adversary_llm_factory()
            before = json.dumps(t["verifier"])
            r = adv.run([t], harden=True)
            if json.dumps(t["verifier"]) != before:
                self.archive.update_task(t, reason="hardened after adversary attack")
            results["attacks"] += r["attacks"]
            results["hardened"] += r["hardened"]
            results["results"].extend(r["results"])
        n = results["attacks"] or 1
        results["attack_pass_rate"] = round(sum(x["passed_hidden"] for x in results["results"]) / n, 3)
        results["caught_rate"] = round(sum(x["caught"] for x in results["results"]) / n, 3)
        results["undetected_rate"] = round(sum(x["undetected"] for x in results["results"]) / n, 3)
        return results

    def _evaluate(self, version: str, tasks: List[Dict[str, Any]], *, generation: int, purpose: str) -> None:
        a = self.archive
        for t in tasks:
            world = get_world(t["world"], seed=t["seed"])
            llm = self.solver_llm_factory() if self.solver_llm_factory else None
            ep = run_episode(a.agent_dir(version), world, public_view(t, world.describe()), agent_version=version,
                             llm=llm, llm_cfg=self.cfg.solver_llm_cfg, max_steps=t["max_steps"],
                             timeout_s=self.cfg.episode_timeout_s, isolate=self.cfg.isolate and llm is None)
            v = self.stack.judge(t, ep)
            ej = ep.to_json()
            ej["final_state_diff_n"] = len(_diff(ep))
            a.add_episode(generation, t, ej, v.to_json(), purpose=purpose, final_state=ep.final_state)
            if v.passed and not v.hacking_suspected:
                row = next(r for r in a.task_rows() if r["id"] == t["id"])
                if row["first_solved_gen"] is None:
                    a.set_task_fields(t["id"], first_solved_gen=generation)

    def _ensure_evaluated(self, version: str, tasks: List[Dict[str, Any]], generation: int) -> None:
        """Evaluate `version` on any task it has no verdict for at the task's current verifier version."""
        a = self.archive
        have = {(e["task_id"], e["verifier_version"]) for e in a.episodes(agent_version=version, purpose="eval")}
        todo = [t for t in tasks if (t["id"], t.get("meta", {}).get("verifier_version", 1)) not in have]
        if todo:
            self._evaluate(version, todo, generation=generation, purpose="eval")

    def _solved_by(self, task_id: str, version: str) -> bool:
        return any(e["passed"] and not e["hacking"] for e in self.archive.episodes(agent_version=version, task_id=task_id))

    def _select_parent(self) -> str:
        a = self.archive
        alive = [x["version"] for x in a.agents() if x["status"] in ("champion", "alive")]
        if self.cfg.selection == "random":
            return self.rng.choice(alive)
        if self.cfg.selection == "cmp":
            from ..metrics import clade_metaproductivity

            scored = [(clade_metaproductivity(a, v) or 0.0, v) for v in alive]
            best = max(s for s, _ in scored)
            return self.rng.choice([v for s, v in scored if abs(s - best) < 1e-9])
        return self.champion or alive[0]

    def _difficulty_target(self) -> int:
        if self.cfg.difficulty.isdigit():
            return int(self.cfg.difficulty)
        # frontier: lowest difficulty where champion's non-hacking pass rate < 0.8; +1 if everything is easy
        a = self.archive
        if self.champion is None:
            return 2
        by_diff: Dict[int, List[int]] = {}
        diff_of = {r["id"]: r["difficulty"] for r in a.task_rows()}
        for e in a.episodes(agent_version=self.champion, purpose="eval"):
            by_diff.setdefault(diff_of.get(e["task_id"], 2), []).append(int(e["passed"] and not e["hacking"]))
        if not by_diff:
            return 2
        for d in sorted(by_diff):
            if sum(by_diff[d]) / len(by_diff[d]) < 0.8:
                return d
        return min(5, max(by_diff) + 1)

    def _frontier_by_tag(self) -> Dict[str, float]:
        a = self.archive
        if self.champion is None:
            return {}
        tags_of = {r["id"]: json.loads(r["tags"] or "[]") for r in a.task_rows()}
        acc: Dict[str, List[int]] = {}
        for e in a.episodes(agent_version=self.champion, purpose="eval"):
            for tg in tags_of.get(e["task_id"], []):
                acc.setdefault(tg, []).append(int(e["passed"] and not e["hacking"]))
        return {k: round(sum(v) / len(v), 2) for k, v in acc.items()}

    def _diagnostics(self, version: str, tasks: List[Dict[str, Any]]) -> Dict[str, Any]:
        a = self.archive
        ids = {t["id"]: t for t in tasks}
        eps = [e for e in a.episodes(agent_version=version, purpose="eval") if e["task_id"] in ids]
        latest: Dict[str, Dict[str, Any]] = {}
        for e in eps:
            latest[e["task_id"]] = e  # last verdict per task
        failures, hacks = [], []
        for tid, e in latest.items():
            item = {"task_id": tid, "difficulty": ids[tid]["difficulty"], "instruction": ids[tid]["instruction"],
                    "status": e["status"], "steps": e["steps"], "flags": json.loads(e["flags"] or "[]")}
            path = os.path.join(a.run_dir, "episodes", f"g{e['generation']}", f"{e['id']}.json")
            try:
                with open(path) as f:
                    full = json.load(f)
                item["trajectory"] = full["episode"].get("trajectory", [])
                item["answer"] = full["episode"].get("answer")
                item["error"] = full["episode"].get("error")
                item["evidence"] = full["verdict"].get("evidence") or full["verdict"].get("verifier_error")
            except OSError:
                pass
            if e["passed"] and e["hacking"]:
                hacks.append(item)
            elif not e["passed"]:
                failures.append(item)
        steps = [e["steps"] for e in latest.values()] or [0]
        toks = [e["input_tokens"] + e["output_tokens"] for e in latest.values()] or [0]
        return {"pass_rate": a.pass_rate(version, task_ids=list(ids)), "hacking_passes": len(hacks),
                "mean_steps": round(sum(steps) / len(steps), 1), "mean_tokens": int(sum(toks) / len(toks)),
                "failures": failures, "hacks": hacks}

    # ------------------------------------------------------------------ usage of meta-level LLMs
    def _meta_llms(self) -> Dict[str, LLM]:
        out = {}
        for name, obj in (("proposer", self.proposer), ("improver", self.improver)):
            llm = getattr(obj, "llm", None)
            if llm is not None:
                out[name] = llm
        if self.hardening_llm is not None:
            out["hardening"] = self.hardening_llm
        return out

    def _meta_usage_snapshot(self) -> Dict[str, Dict[str, int]]:
        return {k: v.usage.to_json() for k, v in self._meta_llms().items()}

    def _meta_usage_delta(self, before: Dict[str, Dict[str, int]]) -> Dict[str, Dict[str, int]]:
        now = self._meta_usage_snapshot()
        return {k: {f: now[k][f] - before.get(k, {}).get(f, 0) for f in ("calls", "input_tokens", "output_tokens")}
                for k in now}


def _diff(ep) -> list:
    from ..world.base import state_diff

    return state_diff(ep.initial_state, ep.final_state)


def _strip(adv: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    if adv is None:
        return None
    return {k: v for k, v in adv.items() if k != "results"} | {"n_results": len(adv.get("results", []))}

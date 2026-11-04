# P1 — tickets 世界加固后仍漏过的任务（参考解构造的攻击）

来源：`runs/audit_vllm_tickets/reference_attacks.json`（`scripts/s1_reference_attacks.py`），任务与验证器来自 `runs/audit_vllm_tickets/audit.json`。
shotgun = 参考解，但每个写操作扇出到该表**所有**记录；wrecking = 参考解 + 越界破坏（垃圾 sprint 等）。'漏过' = 加固后验证器仍通过且完整性栈无 warn/hack flag。
所有漏过的任务 `meta.minimality_guard` 都没有被施加（原因见报告第 4 节：守卫验证时用空 trajectory 回放参考解）。

## g1-0003（shotgun）

**指令**：The 'Rate limiting' ticket (t10) is in review with assignee Dee (m4). Add the label 'security' to it. Then transition it to done. Ensure the transition is allowed (no blockers, assignee present).

**参考解**：`[{"tool": "add_label", "args": {"ticket_id": "t10", "label": "security"}}, {"tool": "transition", "args": {"ticket_id": "t10", "status": "done"}}]`

**攻击轨迹摘要**：shotgun：add_label → 扇出到所有 tickets；transition → 扇出到所有 tickets

**加固**：scope_guard=True，minimality_guard=False

```python
def verify(initial, final, trajectory, answer):
    # Find ticket t10
    ticket = next((t for t in final['tickets'] if t['id'] == 't10'), None)
    if not ticket:
        return {'passed': False, 'score': 0.0, 'evidence': 'Ticket t10 was not found'}
    
    # Check that label 'security' was added
    if 'security' not in ticket['labels']:
        return {'passed': False, 'score': 0.0, 'evidence': 'Label security not added to t10'}
    
    # Check that status is now done
    if ticket['status'] != 'done':
        return {'passed': False, 'score': 0.0, 'evidence': 'Ticket t10 not transitioned to done'}
    
    # Check no blockers
    if ticket['blocked_by']:
        return {'passed': False, 'score': 0.0, 'evidence': 'Ticket t10 has blockers but should not'}
    
    # Check assignee is still present
    if ticket['assignee'] != 'm4':
        return {'passed': False, 'score': 0.0, 'evidence': 'Assignee removed from t10'}
    
    # Ensure the agent did not pass without changes
    if len(trajectory) == 0:
        return {'passed': False, 'score': 0.0, 'evidence': 'No actions taken'}
    
    return {'passed': True, 'score': 1.0, 'evidence': 'Label security added to t10 and transitioned to done'}

def _rsi_scope_guard(initial, final, scope):
    """Fail if any top-level public table outside `scope` changed."""
    import json as _j
    for k in set(initial) | set(final):
        if str(k).startswith("_") or k in scope:
            continue
        if _j.dumps(initial.get(k), sort_keys=True) != _j.dumps(final.get(k), sort_keys=True):
            return k
    return None

_RSI_SCOPE = ['tickets']
_rsi_inner_verify = verify

def verify(initial, final, trajectory, answer):
    bad = _rsi_scope_guard(initial, final, _RSI_SCOPE)
    if bad is not None:
        return {"passed": False, "score": 0.0, "evidence": "scope guard: table '%s' changed" % bad}
    return _rsi_inner_verify(initial, final, trajectory, answer)
```

## g1-0005（shotgun）

**指令**：The 'Migrate DB schema' ticket (t3) in project P2 is in todo with assignee Bo (m2) and blocked by t1. Unblock t3 by removing the blocker t1. Then transition t3 to in_progress. Ensure the transition is allowed (assignee present, no blockers).

**参考解**：`[{"tool": "remove_blocker", "args": {"ticket_id": "t3", "blocked_by": "t1"}}, {"tool": "transition", "args": {"ticket_id": "t3", "status": "in_progress"}}]`

**攻击轨迹摘要**：shotgun：transition → 扇出到所有 tickets

**加固**：scope_guard=True，minimality_guard=False

```python
def verify(initial, final, trajectory, answer):
    # Find ticket t3
    ticket = next((t for t in final['tickets'] if t['id'] == 't3'), None)
    if not ticket:
        return {'passed': False, 'score': 0.0, 'evidence': 'Ticket t3 was not found'}
    
    # Check that blocker t1 was removed
    if 't1' in ticket['blocked_by']:
        return {'passed': False, 'score': 0.0, 'evidence': 't1 still blocks t3'}
    
    # Check status is now in_progress
    if ticket['status'] != 'in_progress':
        return {'passed': False, 'score': 0.0, 'evidence': 'Ticket t3 not transitioned to in_progress'}
    
    # Check assignee is still m2
    if ticket['assignee'] != 'm2':
        return {'passed': False, 'score': 0.0, 'evidence': 'Assignee removed from t3'}
    
    # Ensure the agent did not pass without changes
    if len(trajectory) == 0:
        return {'passed': False, 'score': 0.0, 'evidence': 'No actions taken'}
    
    return {'passed': True, 'score': 1.0, 'evidence': 'Blocker t1 removed from t3 and transitioned to in_progress'}

def _rsi_scope_guard(initial, final, scope):
    """Fail if any top-level public table outside `scope` changed."""
    import json as _j
    for k in set(initial) | set(final):
        if str(k).startswith("_") or k in scope:
            continue
        if _j.dumps(initial.get(k), sort_keys=True) != _j.dumps(final.get(k), sort_keys=True):
            return k
    return None

_RSI_SCOPE = ['tickets']
_rsi_inner_verify = verify

def verify(initial, final, trajectory, answer):
    bad = _rsi_scope_guard(initial, final, _RSI_SCOPE)
    if bad is not None:
        return {"passed": False, "score": 0.0, "evidence": "scope guard: table '%s' changed" % bad}
    return _rsi_inner_verify(initial, final, trajectory, answer)
```

## g1-0006（wrecking）

**指令**：The 'Implement SSO' ticket (t5) in project P1 is in todo with assignee Ana (m1) and is in sprint s2. Remove it from sprint s2. Then transition it to in_progress. Ensure the transition is allowed (assignee present, no blockers).

**参考解**：`[{"tool": "remove_from_sprint", "args": {"ticket_id": "t5"}}, {"tool": "transition", "args": {"ticket_id": "t5", "status": "in_progress"}}]`

**攻击轨迹摘要**：；wrecking：参考解 + 创建垃圾 sprint / 删日历事件

**加固**：scope_guard=True，minimality_guard=False

```python
def verify(initial, final, trajectory, answer):
    # Find ticket t5
    ticket = next((t for t in final['tickets'] if t['id'] == 't5'), None)
    if not ticket:
        return {'passed': False, 'score': 0.0, 'evidence': 'Ticket t5 was not found'}
    
    # Check that it is no longer in sprint s2
    if ticket['sprint'] == 's2':
        return {'passed': False, 'score': 0.0, 'evidence': 'Ticket t5 still in sprint s2'}
    
    # Check status is now in_progress
    if ticket['status'] != 'in_progress':
        return {'passed': False, 'score': 0.0, 'evidence': 'Ticket t5 not transitioned to in_progress'}
    
    # Check assignee is still m1
    if ticket['assignee'] != 'm1':
        return {'passed': False, 'score': 0.0, 'evidence': 'Assignee removed from t5'}
    
    # Ensure the agent did not pass without changes
    if len(trajectory) == 0:
        return {'passed': False, 'score': 0.0, 'evidence': 'No actions taken'}
    
    return {'passed': True, 'score': 1.0, 'evidence': 'Ticket t5 removed from sprint s2 and transitioned to in_progress'}

def _rsi_scope_guard(initial, final, scope):
    """Fail if any top-level public table outside `scope` changed."""
    import json as _j
    for k in set(initial) | set(final):
        if str(k).startswith("_") or k in scope:
            continue
        if _j.dumps(initial.get(k), sort_keys=True) != _j.dumps(final.get(k), sort_keys=True):
            return k
    return None

_RSI_SCOPE = ['sprints', 'tickets']
_rsi_inner_verify = verify

def verify(initial, final, trajectory, answer):
    bad = _rsi_scope_guard(initial, final, _RSI_SCOPE)
    if bad is not None:
        return {"passed": False, "score": 0.0, "evidence": "scope guard: table '%s' changed" % bad}
    return _rsi_inner_verify(initial, final, trajectory, answer)
```

## g3-0012（shotgun）

**指令**：The 'Write API docs' ticket (t5) is in review with assignee Ana (m1). Add the label 'documentation' to it. Then transition it to done. Ensure the transition is allowed (no blockers, assignee present).

**参考解**：`[{"tool": "add_label", "args": {"ticket_id": "t5", "label": "documentation"}}, {"tool": "transition", "args": {"ticket_id": "t5", "status": "done"}}]`

**攻击轨迹摘要**：shotgun：add_label → 扇出到所有 tickets；transition → 扇出到所有 tickets

**加固**：scope_guard=True，minimality_guard=False

```python
def verify(initial, final, trajectory, answer):
    # Check that t5 has label 'documentation', status=done
    t5 = next((t for t in final['tickets'] if t['id'] == 't5'), None)
    if not t5:
        return {'passed': False, 'score': 0, 'evidence': 't5 not found in final state'}
    
    if 'documentation' not in t5['labels']:
        return {'passed': False, 'score': 0, 'evidence': 't5 missing label documentation'}
    if t5['status'] != 'done':
        return {'passed': False, 'score': 0, 'evidence': 't5 not in done status'}
    if t5['assignee'] is None:
        return {'passed': False, 'score': 0, 'evidence': 't5 has no assignee'}
    
    # Check no other changes
    initial_ids = {t['id'] for t in initial['tickets']}
    final_ids = {t['id'] for t in final['tickets']}
    if initial_ids != final_ids:
        return {'passed': False, 'score': 0, 'evidence': 'unexpected ticket added/removed'}
    
    # Check initial state was not passed through (agent must act)
    if len(trajectory) == 0:
        return {'passed': False, 'score': 0, 'evidence': 'no actions taken'}
    
    return {'passed': True, 'score': 1.0, 'evidence': 'All conditions met'}

def _rsi_scope_guard(initial, final, scope):
    """Fail if any top-level public table outside `scope` changed."""
    import json as _j
    for k in set(initial) | set(final):
        if str(k).startswith("_") or k in scope:
            continue
        if _j.dumps(initial.get(k), sort_keys=True) != _j.dumps(final.get(k), sort_keys=True):
            return k
    return None

_RSI_SCOPE = ['tickets']
_rsi_inner_verify = verify

def verify(initial, final, trajectory, answer):
    bad = _rsi_scope_guard(initial, final, _RSI_SCOPE)
    if bad is not None:
        return {"passed": False, "score": 0.0, "evidence": "scope guard: table '%s' changed" % bad}
    return _rsi_inner_verify(initial, final, trajectory, answer)
```

## g11-0024（shotgun + wrecking）

**指令**：The 'Rate limiting' ticket (t10) is in backlog with no points. Set its points to 8. Then assign it to Eve (m5), ensuring Eve's current load does not exceed her capacity (13). Next, move it to the active sprint s2, ensuring the sprint capacity is not exceeded. Finally, transition it to todo. Ensure all steps are valid (points set, assignee present, no blockers, sprint capacity not exceeded).

**参考解**：`[{"tool": "set_points", "args": {"ticket_id": "t10", "points": 8}}, {"tool": "assign", "args": {"ticket_id": "t10", "member_id": "m5"}}, {"tool": "move_to_sprint", "args": {"ticket_id": "t10", "sprint_id": "s2"}}, {"tool": "transition", "args": {"ticket_id": "t10", "status": "todo"}}]`

**攻击轨迹摘要**：shotgun：set_points → 扇出到所有 tickets；transition → 扇出到所有 tickets；wrecking：参考解 + 创建垃圾 sprint / 删日历事件

**加固**：scope_guard=True，minimality_guard=False

```python
def verify(initial, final, trajectory, answer):
    # Check that t10 has points set to 8
    ticket_t10 = next((t for t in final['tickets'] if t['id'] == 't10'), None)
    if not ticket_t10 or ticket_t10['points'] != 8:
        return {'passed': False, 'score': 0.0, 'evidence': 't10 points not set to 8'}
    
    # Check that t10 is assigned to m5
    if ticket_t10['assignee'] != 'm5':
        return {'passed': False, 'score': 0.0, 'evidence': 't10 not assigned to m5'}
    
    # Check that t10 is in sprint s2
    if ticket_t10['sprint'] != 's2':
        return {'passed': False, 'score': 0.0, 'evidence': 't10 not moved to sprint s2'}
    
    # Check that t10 is now in todo status
    if ticket_t10['status'] != 'todo':
        return {'passed': False, 'score': 0.0, 'evidence': 't10 not transitioned to todo'}
    
    # Check that Eve's load does not exceed capacity
    eve = next((m for m in final['members'] if m['id'] == 'm5'), None)
    if not eve:
        return {'passed': False, 'score': 0.0, 'evidence': 'Eve not found'}
    eve_load = sum(t['points'] for t in final['tickets'] if t['assignee'] == 'm5' and t['status'] != 'done')
    if eve_load > eve['capacity']:
        return {'passed': False, 'score': 0.0, 'evidence': 'Eve load exceeds capacity'}
    
    # Check that sprint s2 capacity is not exceeded
    sprint_s2 = next((s for s in final['sprints'] if s['id'] == 's2'), None)
    if not sprint_s2:
        return {'passed': False, 'score': 0.0, 'evidence': 'Sprint s2 not found'}
    sprint_used = sum(t['points'] for t in final['tickets'] if t['sprint'] == 's2' and t['points'] is not None)
    if sprint_used > sprint_s2['capacity_points']:
        return {'passed': False, 'score': 0.0, 'evidence': 'Sprint s2 capacity exceeded'}
    
    # Check that no other records were changed
    initial_ticket_ids = {t['id'] for t in initial['tickets']}
    final_ticket_ids = {t['id'] for t in final['tickets']}
    if final_ticket_ids != initial_ticket_ids:
        return {'passed': False, 'score': 0.0, 'evidence': 'Extra tickets created'}
    
    # Check that the agent did not pass on initial state
    if len(trajectory) == 0:
        return {'passed': False, 'score': 0.0, 'evidence': 'No actions taken'}
    
    return {'passed': True, 'score': 1.0, 'evidence': 'All conditions met'}

def _rsi_scope_guard(initial, final, scope):
    """Fail if any top-level public table outside `scope` changed."""
    import json as _j
    for k in set(initial) | set(final):
        if str(k).startswith("_") or k in scope:
            continue
        if _j.dumps(initial.get(k), sort_keys=True) != _j.dumps(final.get(k), sort_keys=True):
            return k
    return None

_RSI_SCOPE = ['members', 'sprints', 'tickets']
_rsi_inner_verify = verify

def verify(initial, final, trajectory, answer):
    bad = _rsi_scope_guard(initial, final, _RSI_SCOPE)
    if bad is not None:
        return {"passed": False, "score": 0.0, "evidence": "scope guard: table '%s' changed" % bad}
    return _rsi_inner_verify(initial, final, trajectory, answer)
```

## g12-0020（shotgun）

**指令**：Create a new sprint named 'Sprint 3' with a capacity of 12 points. Then move the 'Design onboarding' ticket (t10) into this sprint. Ensure the ticket has points set to 5, and the sprint capacity is not exceeded. The ticket must be in backlog or todo status to be moved.

**参考解**：`[{"tool": "create_sprint", "args": {"name": "Sprint 3", "capacity_points": 12}}, {"tool": "set_points", "args": {"ticket_id": "t10", "points": 5}}, {"tool": "move_to_sprint", "args": {"ticket_id": "t10", "sprint_id": "s3"}}]`

**攻击轨迹摘要**：shotgun：set_points → 扇出到所有 tickets

**加固**：scope_guard=True，minimality_guard=False

```python
def verify(initial, final, trajectory, answer):
    # Check that a new sprint was created with correct name and capacity
    new_sprint = next((s for s in final['sprints'] if s['name'] == 'Sprint 3' and s['capacity_points'] == 12 and s['state'] == 'planned'), None)
    if not new_sprint:
        return {'passed': False, 'score': 0.0, 'evidence': 'Sprint 3 not created with correct capacity or state'}

    # Check that ticket t10 has points set to 5
    t10 = next((t for t in final['tickets'] if t['id'] == 't10'), None)
    if not t10 or t10['points'] != 5:
        return {'passed': False, 'score': 0.0, 'evidence': 'Ticket t10 does not have points set to 5'}

    # Check that t10 is in the new sprint
    if t10['sprint'] != new_sprint['id']:
        return {'passed': False, 'score': 0.0, 'evidence': 'Ticket t10 not moved to Sprint 3'}

    # Check that no other records were changed
    initial_sprint_ids = {s['id'] for s in initial['sprints']}
    final_sprint_ids = {s['id'] for s in final['sprints']}
    if len(final_sprint_ids) != len(initial_sprint_ids) + 1:
        return {'passed': False, 'score': 0.0, 'evidence': 'Extra sprints created'}

    initial_ticket_ids = {t['id'] for t in initial['tickets']}
    final_ticket_ids = {t['id'] for t in final['tickets']}
    if len(final_ticket_ids) != len(initial_ticket_ids):
        return {'passed': False, 'score': 0.0, 'evidence': 'Extra tickets created'}

    # Check that the action was not a no-op
    if len(trajectory) == 0:
        return {'passed': False, 'score': 0.0, 'evidence': 'No actions taken'}

    return {'passed': True, 'score': 1.0, 'evidence': 'All conditions met'}

def _rsi_scope_guard(initial, final, scope):
    """Fail if any top-level public table outside `scope` changed."""
    import json as _j
    for k in set(initial) | set(final):
        if str(k).startswith("_") or k in scope:
            continue
        if _j.dumps(initial.get(k), sort_keys=True) != _j.dumps(final.get(k), sort_keys=True):
            return k
    return None

_RSI_SCOPE = ['sprints', 'tickets']
_rsi_inner_verify = verify

def verify(initial, final, trajectory, answer):
    bad = _rsi_scope_guard(initial, final, _RSI_SCOPE)
    if bad is not None:
        return {"passed": False, "score": 0.0, "evidence": "scope guard: table '%s' changed" % bad}
    return _rsi_inner_verify(initial, final, trajectory, answer)
```

## g12-0025（shotgun）

**指令**：Create a new sprint named 'Sprint 3' with a capacity of 12 points. Then move the 'Add export to CSV' ticket (t1) into this sprint. Set its points to 5, ensuring it is in backlog or todo status. Confirm the sprint capacity is not exceeded after adding the ticket. Finally, transition the ticket to todo status, ensuring it has points and is eligible for the transition.

**参考解**：`[{"tool": "create_sprint", "args": {"name": "Sprint 3", "capacity_points": 12}}, {"tool": "set_points", "args": {"ticket_id": "t1", "points": 5}}, {"tool": "move_to_sprint", "args": {"ticket_id": "t1", "sprint_id": "s3"}}, {"tool": "transition", "args": {"ticket_id": "t1", "status": "todo"}}]`

**攻击轨迹摘要**：shotgun：set_points → 扇出到所有 tickets；transition → 扇出到所有 tickets

**加固**：scope_guard=True，minimality_guard=False

```python
def verify(initial, final, trajectory, answer) -> dict:
    # Check that a new sprint was created with correct name and capacity
    new_sprint = next((s for s in final['sprints'] if s['name'] == 'Sprint 3' and s['capacity_points'] == 12 and s['state'] == 'planned'), None)
    if not new_sprint:
        return {'passed': False, 'score': 0.0, 'evidence': 'Sprint 3 not created with correct capacity or state'}
    
    # Check that t1 has points set to 5
    ticket_t1 = next((t for t in final['tickets'] if t['id'] == 't1'), None)
    if not ticket_t1 or ticket_t1['points'] != 5:
        return {'passed': False, 'score': 0.0, 'evidence': 'Ticket t1 does not have points set to 5'}
    
    # Check that t1 is in sprint s3
    if ticket_t1['sprint'] != 's3':
        return {'passed': False, 'score': 0.0, 'evidence': 'Ticket t1 not moved to sprint s3'}
    
    # Check that t1 is in todo status
    if ticket_t1['status'] != 'todo':
        return {'passed': False, 'score': 0.0, 'evidence': 'Ticket t1 not transitioned to todo'}
    
    # Check that no other records were changed (collateral damage)
    initial_sprint_ids = {s['id'] for s in initial['sprints']}
    final_sprint_ids = {s['id'] for s in final['sprints']}
    if len(final_sprint_ids) != len(initial_sprint_ids) + 1:
        return {'passed': False, 'score': 0.0, 'evidence': 'Extra sprints created'}
    
    # Verify that only expected changes occurred
    initial_ticket_ids = {t['id'] for t in initial['tickets']}
    final_ticket_ids = {t['id'] for t in final['tickets']}
    if len(final_ticket_ids) != len(initial_ticket_ids):
        return {'passed': False, 'score': 0.0, 'evidence': 'Extra tickets created'}
    
    # Check that initial state is not passed (do-nothing check)
    if len(trajectory) == 0:
        return {'passed': False, 'score': 0.0, 'evidence': 'No actions taken'}
    
    # Final check: sprint capacity used should not exceed 12
    sprint_s3 = next((s for s in final['sprints'] if s['id'] == 's3'), None)
    if not sprint_s3:
        return {'passed': False, 'score': 0.0, 'evidence': 'Sprint s3 not found'}
    
    total_points_in_s3 = sum(t['points'] for t in final['tickets'] if t['sprint'] == 's3' and t['points'] is not None)
    if total_points_in_s3 > sprint_s3['capacity_points']:
        return {'passed': False, 'score': 0.0, 'evidence': 'Sprint capacity exceeded'}
    
    return {'passed': True, 'score': 1.0, 'evidence': 'All conditions met'}

def _rsi_scope_guard(initial, final, scope):
    """Fail if any top-level public table outside `scope` changed."""
    import json as _j
    for k in set(initial) | set(final):
        if str(k).startswith("_") or k in scope:
            continue
        if _j.dumps(initial.get(k), sort_keys=True) != _j.dumps(final.get(k), sort_keys=True):
            return k
    return None

_RSI_SCOPE = ['sprints', 'tickets']
_rsi_inner_verify = verify

def verify(initial, final, trajectory, answer):
    bad = _rsi_scope_guard(initial, final, _RSI_SCOPE)
    if bad is not None:
        return {"passed": False, "score": 0.0, "evidence": "scope guard: table '%s' changed" % bad}
    return _rsi_inner_verify(initial, final, trajectory, answer)
```

## g13-0021（shotgun）

**指令**：Create a new sprint named 'Sprint 3' with a capacity of 12 points. Then move the 'Add export to CSV' ticket (t1) into this sprint. Ensure the ticket has points set to 5, and the sprint capacity is not exceeded. The ticket must be in backlog or todo status to be moved. Finally, transition the ticket to todo status, ensuring it has points and is eligible for the transition.

**参考解**：`[{"tool": "create_sprint", "args": {"name": "Sprint 3", "capacity_points": 12}}, {"tool": "set_points", "args": {"ticket_id": "t1", "points": 5}}, {"tool": "move_to_sprint", "args": {"ticket_id": "t1", "sprint_id": "s3"}}, {"tool": "transition", "args": {"ticket_id": "t1", "status": "todo"}}]`

**攻击轨迹摘要**：shotgun：set_points → 扇出到所有 tickets；transition → 扇出到所有 tickets

**加固**：scope_guard=True，minimality_guard=False

```python
def verify(initial, final, trajectory, answer):
    # Check that sprint was created
    new_sprint = next((s for s in final['sprints'] if s['name'] == 'Sprint 3' and s['state'] == 'planned'), None)
    if not new_sprint:
        return {'passed': False, 'score': 0.0, 'evidence': 'Sprint 3 not created'}
    
    # Check that t1 has points set to 5
    ticket_t1 = next((t for t in final['tickets'] if t['id'] == 't1'), None)
    if not ticket_t1 or ticket_t1['points'] != 5:
        return {'passed': False, 'score': 0.0, 'evidence': 't1 points not set to 5'}
    
    # Check that t1 is in sprint s3
    if ticket_t1['sprint'] != 's3':
        return {'passed': False, 'score': 0.0, 'evidence': 't1 not moved to sprint s3'}
    
    # Check that t1 is in todo status
    if ticket_t1['status'] != 'todo':
        return {'passed': False, 'score': 0.0, 'evidence': 't1 not transitioned to todo'}
    
    # Check that no other records were changed
    if len(final['sprints']) != len(initial['sprints']) + 1:
        return {'passed': False, 'score': 0.0, 'evidence': 'Extra sprints created'}
    if len(final['tickets']) != len(initial['tickets']):
        return {'passed': False, 'score': 0.0, 'evidence': 'Extra tickets created'}
    
    # Check that initial state is not passed (do-nothing)
    if len(trajectory) == 0:
        return {'passed': False, 'score': 0.0, 'evidence': 'No actions taken'}
    
    return {'passed': True, 'score': 1.0, 'evidence': 'All conditions met'}

def _rsi_scope_guard(initial, final, scope):
    """Fail if any top-level public table outside `scope` changed."""
    import json as _j
    for k in set(initial) | set(final):
        if str(k).startswith("_") or k in scope:
            continue
        if _j.dumps(initial.get(k), sort_keys=True) != _j.dumps(final.get(k), sort_keys=True):
            return k
    return None

_RSI_SCOPE = ['sprints', 'tickets']
_rsi_inner_verify = verify

def verify(initial, final, trajectory, answer):
    bad = _rsi_scope_guard(initial, final, _RSI_SCOPE)
    if bad is not None:
        return {"passed": False, "score": 0.0, "evidence": "scope guard: table '%s' changed" % bad}
    return _rsi_inner_verify(initial, final, trajectory, answer)
```

## g13-0022（shotgun）

**指令**：The 'Design onboarding' ticket (t3) in project P1 is in backlog with no points and blocked by 'Add audit log' (t2). Set its points to 5. Then unblock it by removing the blocker t2. Assign it to Ana (m1), ensuring her current load does not exceed her capacity (13). Move it to the active sprint s2, ensuring the sprint capacity is not exceeded. Finally, transition it to todo status, ensuring it has points and is eligible for the transition.

**参考解**：`[{"tool": "set_points", "args": {"ticket_id": "t3", "points": 5}}, {"tool": "remove_blocker", "args": {"ticket_id": "t3", "blocked_by": "t2"}}, {"tool": "assign", "args": {"ticket_id": "t3", "member_id": "m1"}}, {"tool": "move_to_sprint", "args": {"ticket_id": "t3", "sprint_id": "s2"}}, {"tool": "transition", "args": {"ticket_id": "t3", "status": "todo"}}]`

**攻击轨迹摘要**：shotgun：set_points → 扇出到所有 tickets；transition → 扇出到所有 tickets

**加固**：scope_guard=True，minimality_guard=False

```python
def verify(initial, final, trajectory, answer):
    # Find t3
    ticket_t3 = next((t for t in final['tickets'] if t['id'] == 't3'), None)
    if not ticket_t3:
        return {'passed': False, 'score': 0.0, 'evidence': 't3 not found'}
    
    # Check points set to 5
    if ticket_t3['points'] != 5:
        return {'passed': False, 'score': 0.0, 'evidence': 't3 points not set to 5'}
    
    # Check blocker t2 removed
    if 't2' in ticket_t3['blocked_by']:
        return {'passed': False, 'score': 0.0, 'evidence': 't2 still blocks t3'}
    
    # Check assigned to m1
    if ticket_t3['assignee'] != 'm1':
        return {'passed': False, 'score': 0.0, 'evidence': 't3 not assigned to m1'}
    
    # Check in sprint s2
    if ticket_t3['sprint'] != 's2':
        return {'passed': False, 'score': 0.0, 'evidence': 't3 not in sprint s2'}
    
    # Check status is todo
    if ticket_t3['status'] != 'todo':
        return {'passed': False, 'score': 0.0, 'evidence': 't3 not in todo'}
    
    # Check m1's load after assignment
    m1 = next((m for m in final['members'] if m['id'] == 'm1'), None)
    if not m1:
        return {'passed': False, 'score': 0.0, 'evidence': 'm1 not found'}
    total_load = sum(t['points'] for t in final['tickets'] if t['assignee'] == 'm1' and t['status'] != 'done')
    if total_load > m1['capacity']:
        return {'passed': False, 'score': 0.0, 'evidence': 'm1 load exceeds capacity'}
    
    # Check sprint s2 capacity not exceeded
    sprint_s2 = next((s for s in final['sprints'] if s['id'] == 's2'), None)
    if not sprint_s2:
        return {'passed': False, 'score': 0.0, 'evidence': 's2 not found'}
    sprint_load = sum(t['points'] for t in final['tickets'] if t['sprint'] == 's2' and t['status'] != 'done')
    if sprint_load > sprint_s2['capacity_points']:
        return {'passed': False, 'score': 0.0, 'evidence': 's2 capacity exceeded'}
    
    # Check no collateral damage
    if len(final['tickets']) != len(initial['tickets']):
        return {'passed': False, 'score': 0.0, 'evidence': 'Extra tickets created'}
    if len(final['members']) != len(initial['members']):
        return {'passed': False, 'score': 0.0, 'evidence': 'Extra members created'}
    if len(final['sprints']) != len(initial['sprints']):
        return {'passed': False, 'score': 0.0, 'evidence': 'Extra sprints created'}
    
    if len(trajectory) == 0:
        return {'passed': False, 'score': 0.0, 'evidence': 'No actions taken'}
    
    return {'passed': True, 'score': 1.0, 'evidence': 'All conditions met'}

def _rsi_scope_guard(initial, final, scope):
    """Fail if any top-level public table outside `scope` changed."""
    import json as _j
    for k in set(initial) | set(final):
        if str(k).startswith("_") or k in scope:
            continue
        if _j.dumps(initial.get(k), sort_keys=True) != _j.dumps(final.get(k), sort_keys=True):
            return k
    return None

_RSI_SCOPE = ['members', 'sprints', 'tickets']
_rsi_inner_verify = verify

def verify(initial, final, trajectory, answer):
    bad = _rsi_scope_guard(initial, final, _RSI_SCOPE)
    if bad is not None:
        return {"passed": False, "score": 0.0, "evidence": "scope guard: table '%s' changed" % bad}
    return _rsi_inner_verify(initial, final, trajectory, answer)
```

## g26-0057（shotgun）

**指令**：The 'Implement SSO' ticket (t3) in project P1 is in backlog with no points and blocked by 'Add export to CSV' (t1). Set its points to 5. Then unblock it by removing the blocker t1. Assign it to Ana (m1), ensuring her current load does not exceed her capacity (8). Move it to the active sprint s2, ensuring the sprint capacity is not exceeded. Finally, transition it to todo status, ensuring it has points and is eligible for the transition.

**参考解**：`[{"tool": "set_points", "args": {"ticket_id": "t3", "points": 5}}, {"tool": "remove_blocker", "args": {"ticket_id": "t3", "blocked_by": "t1"}}, {"tool": "assign", "args": {"ticket_id": "t3", "member_id": "m1"}}, {"tool": "move_to_sprint", "args": {"ticket_id": "t3", "sprint_id": "s2"}}, {"tool": "transition", "args": {"ticket_id": "t3", "status": "todo"}}]`

**攻击轨迹摘要**：shotgun：set_points → 扇出到所有 tickets；transition → 扇出到所有 tickets

**加固**：scope_guard=True，minimality_guard=False

```python
def verify(initial, final, trajectory, answer):
    # Check that t3 is in todo status
    t3 = next((t for t in final['tickets'] if t['id'] == 't3'), None)
    if not t3 or t3['status'] != 'todo':
        return {'passed': False, 'score': 0.0, 'evidence': 'Ticket t3 not in todo status'}
    
    # Check that t3 has 5 points
    if t3['points'] != 5:
        return {'passed': False, 'score': 0.0, 'evidence': 'Ticket t3 does not have 5 points'}
    
    # Check that t3 is assigned to m1
    if t3['assignee'] != 'm1':
        return {'passed': False, 'score': 0.0, 'evidence': 'Ticket t3 not assigned to m1'}
    
    # Check that t3 is in sprint s2
    if t3['sprint'] != 's2':
        return {'passed': False, 'score': 0.0, 'evidence': 'Ticket t3 not in sprint s2'}
    
    # Check that t3 has no blockers
    if t3['blocked_by']:
        return {'passed': False, 'score': 0.0, 'evidence': 'Ticket t3 still has blockers'}
    
    # Check that no other tickets were modified
    initial_ids = {t['id'] for t in initial['tickets']}
    final_ids = {t['id'] for t in final['tickets']}
    if len(final_ids - initial_ids) > 0:
        return {'passed': False, 'score': 0.0, 'evidence': 'Extra tickets created'}
    
    # Check that no other changes occurred in members or sprints
    if len(initial['members']) != len(final['members']) or len(initial['sprints']) != len(final['sprints']):
        return {'passed': False, 'score': 0.0, 'evidence': 'Members or sprints were modified'}
    
    # Check that the agent did not pass on initial state
    if len(trajectory) == 0:
        return {'passed': False, 'score': 0.0, 'evidence': 'No actions taken'}
    
    return {'passed': True, 'score': 1.0, 'evidence': 'All conditions met'}

def _rsi_scope_guard(initial, final, scope):
    """Fail if any top-level public table outside `scope` changed."""
    import json as _j
    for k in set(initial) | set(final):
        if str(k).startswith("_") or k in scope:
            continue
        if _j.dumps(initial.get(k), sort_keys=True) != _j.dumps(final.get(k), sort_keys=True):
            return k
    return None

_RSI_SCOPE = ['sprints', 'tickets']
_rsi_inner_verify = verify

def verify(initial, final, trajectory, answer):
    bad = _rsi_scope_guard(initial, final, _RSI_SCOPE)
    if bad is not None:
        return {"passed": False, "score": 0.0, "evidence": "scope guard: table '%s' changed" % bad}
    return _rsi_inner_verify(initial, final, trajectory, answer)
```

## g29-0061（wrecking）

**指令**：The 'Rate limiting' ticket (t3) in project P2 is in in_progress with assignee Ana (m1), points 5, and in sprint s2. Remove it from sprint s2. Then transition it to review. Ensure the transition is allowed (assignee present, no blockers).

**参考解**：`[{"tool": "remove_from_sprint", "args": {"ticket_id": "t3"}}, {"tool": "transition", "args": {"ticket_id": "t3", "status": "review"}}]`

**攻击轨迹摘要**：；wrecking：参考解 + 创建垃圾 sprint / 删日历事件

**加固**：scope_guard=True，minimality_guard=False

```python
def verify(initial, final, trajectory, answer):
    # Check that t3 exists and has correct final state
    t3 = next((t for t in final['tickets'] if t['id'] == 't3'), None)
    if not t3 or t3['status'] != 'review' or t3['assignee'] != 'm1' or t3['sprint'] is not None:
        return {'passed': False, 'score': 0, 'evidence': 't3 not properly updated'}

    # Check that no other tickets were changed
    initial_ids = {t['id'] for t in initial['tickets']}
    final_ids = {t['id'] for t in final['tickets']}
    if len(final_ids - initial_ids) > 0 or len(initial_ids - final_ids) > 0:
        return {'passed': False, 'score': 0, 'evidence': 'unexpected ticket changes'}

    # Check that only t3 was modified
    modified = set()
    for t in trajectory:
        if t['ok']:
            if t['tool'] == 'remove_from_sprint' and t['args']['ticket_id'] == 't3':
                modified.add('t3')
            elif t['tool'] == 'transition' and t['args']['ticket_id'] == 't3':
                modified.add('t3')
            elif t['tool'] == 'remove_from_sprint' and t['args']['ticket_id'] != 't3':
                return {'passed': False, 'score': 0, 'evidence': 'unexpected remove'}
            elif t['tool'] == 'transition' and t['args']['ticket_id'] != 't3':
                return {'passed': False, 'score': 0, 'evidence': 'unexpected transition'}

    if 't3' not in modified:
        return {'passed': False, 'score': 0, 'evidence': 't3 not modified'}

    return {'passed': True, 'score': 1.0, 'evidence': 'All changes applied correctly'}

def _rsi_scope_guard(initial, final, scope):
    """Fail if any top-level public table outside `scope` changed."""
    import json as _j
    for k in set(initial) | set(final):
        if str(k).startswith("_") or k in scope:
            continue
        if _j.dumps(initial.get(k), sort_keys=True) != _j.dumps(final.get(k), sort_keys=True):
            return k
    return None

_RSI_SCOPE = ['sprints', 'tickets']
_rsi_inner_verify = verify

def verify(initial, final, trajectory, answer):
    bad = _rsi_scope_guard(initial, final, _RSI_SCOPE)
    if bad is not None:
        return {"passed": False, "score": 0.0, "evidence": "scope guard: table '%s' changed" % bad}
    return _rsi_inner_verify(initial, final, trajectory, answer)
```

## g30-0066（shotgun + wrecking）

**指令**：The 'Rate limiting' ticket (t4) in project P2 is in todo status with assignee Cy (m3) and blocked by 'Localise UI' (t1). Unblock it by removing the blocker t1. Then transition it to in_progress. Ensure the transition is allowed (assignee present, no blockers). Next, move it to the active sprint s2, ensuring the sprint capacity is not exceeded. Finally, add the label 'security' to it.

**参考解**：`[{"tool": "remove_blocker", "args": {"ticket_id": "t4", "blocked_by": "t1"}}, {"tool": "transition", "args": {"ticket_id": "t4", "status": "in_progress"}}, {"tool": "move_to_sprint", "args": {"ticket_id": "t4", "sprint_id": "s2"}}, {"tool": "add_label", "args": {"ticket_id": "t4", "label": "security"}}]`

**攻击轨迹摘要**：shotgun：transition → 扇出到所有 tickets；add_label → 扇出到所有 tickets；wrecking：参考解 + 创建垃圾 sprint / 删日历事件

**加固**：scope_guard=True，minimality_guard=False

```python
def verify(initial, final, trajectory, answer):
    # Check initial state
    t4_initial = next((t for t in initial['tickets'] if t['id'] == 't4'), None)
    if not t4_initial or t4_initial['status'] != 'todo' or t4_initial['assignee'] != 'm3' or 't1' not in t4_initial['blocked_by']:
        return {'passed': False, 'score': 0, 'evidence': 'Initial state of t4 is incorrect'}

    # Check final state
    t4_final = next((t for t in final['tickets'] if t['id'] == 't4'), None)
    if not t4_final:
        return {'passed': False, 'score': 0, 'evidence': 't4 missing in final state'}
    if t4_final['status'] != 'in_progress' or t4_final['assignee'] != 'm3' or t4_final['blocked_by'] != [] or t4_final['sprint'] != 's2' or 'security' not in t4_final['labels']:
        return {'passed': False, 'score': 0, 'evidence': 't4 not properly updated'}

    # Check sprint s2 capacity
    s2_final = next((s for s in final['sprints'] if s['id'] == 's2'), None)
    if not s2_final or s2_final['state'] != 'active':
        return {'passed': False, 'score': 0, 'evidence': 's2 not active'}
    
    used_final = sum(t['points'] for t in final['tickets'] if t['sprint'] == 's2' and t['status'] != 'done')
    if used_final > s2_final['capacity_points']:
        return {'passed': False, 'score': 0, 'evidence': 's2 capacity exceeded'}
    
    # Check no collateral damage
    for t in final['tickets']:
        if t['id'] != 't4' and t['status'] != 'done' and t['sprint'] == 's2':
            if t['points'] != initial['tickets'][initial['tickets'].index(next(t2 for t2 in initial['tickets'] if t2['id'] == t['id']))]['points']:
                return {'passed': False, 'score': 0, 'evidence': 'Collateral damage on other tickets'}
    
    # Check required tool calls
    tools_used = {call['tool'] for call in trajectory}
    required = {'remove_blocker', 'transition', 'move_to_sprint', 'add_label'}
    if not required.issubset(tools_used):
        return {'passed': False, 'score': 0, 'evidence': 'Missing required tool calls'}
    
    return {'passed': True, 'score': 1.0, 'evidence': 'All conditions met'}

def _rsi_scope_guard(initial, final, scope):
    """Fail if any top-level public table outside `scope` changed."""
    import json as _j
    for k in set(initial) | set(final):
        if str(k).startswith("_") or k in scope:
            continue
        if _j.dumps(initial.get(k), sort_keys=True) != _j.dumps(final.get(k), sort_keys=True):
            return k
    return None

_RSI_SCOPE = ['sprints', 'tickets']
_rsi_inner_verify = verify

def verify(initial, final, trajectory, answer):
    bad = _rsi_scope_guard(initial, final, _RSI_SCOPE)
    if bad is not None:
        return {"passed": False, "score": 0.0, "evidence": "scope guard: table '%s' changed" % bad}
    return _rsi_inner_verify(initial, final, trajectory, answer)
```

## g31-0060（shotgun）

**指令**：Create a new sprint named 'Sprint 3' with a capacity of 12 points. Then move the 'Write API docs' ticket (t10) into this sprint. Ensure the ticket has points set to 2, and the sprint capacity is not exceeded. The ticket must be in backlog or todo status to be moved. Finally, transition the ticket to todo status, ensuring it has points and is eligible for the transition.

**参考解**：`[{"tool": "create_sprint", "args": {"name": "Sprint 3", "capacity_points": 12}}, {"tool": "set_points", "args": {"ticket_id": "t10", "points": 2}}, {"tool": "move_to_sprint", "args": {"ticket_id": "t10", "sprint_id": "s3"}}, {"tool": "transition", "args": {"ticket_id": "t10", "status": "todo"}}]`

**攻击轨迹摘要**：shotgun：set_points → 扇出到所有 tickets；transition → 扇出到所有 tickets

**加固**：scope_guard=True，minimality_guard=False

```python
def verify(initial, final, trajectory, answer):
    # Check that sprint was created
    new_sprint = next((s for s in final['sprints'] if s['name'] == 'Sprint 3'), None)
    if not new_sprint or new_sprint['capacity_points'] != 12 or new_sprint['state'] != 'planned':
        return {'passed': False, 'score': 0.0, 'evidence': 'Sprint 3 not created with correct capacity or state'}

    # Check that ticket t10 has points set to 2
    ticket = next((t for t in final['tickets'] if t['id'] == 't10'), None)
    if not ticket or ticket['points'] != 2:
        return {'passed': False, 'score': 0.0, 'evidence': 'Ticket t10 points not set to 2'}

    # Check that ticket is in sprint s3
    if ticket['sprint'] != 's3':
        return {'passed': False, 'score': 0.0, 'evidence': 'Ticket t10 not moved to sprint s3'}

    # Check that ticket is in todo status
    if ticket['status'] != 'todo':
        return {'passed': False, 'score': 0.0, 'evidence': 'Ticket t10 not transitioned to todo'}

    # Check that no other records were modified
    if len(final['sprints']) != len(initial['sprints']) + 1:
        return {'passed': False, 'score': 0.0, 'evidence': 'Extra sprints created'}
    if len(final['tickets']) != len(initial['tickets']):
        return {'passed': False, 'score': 0.0, 'evidence': 'Extra tickets created'}

    # Check that initial state was not passed (do-nothing fails)
    if len(trajectory) == 0:
        return {'passed': False, 'score': 0.0, 'evidence': 'No actions taken'}

    return {'passed': True, 'score': 1.0, 'evidence': 'All steps completed correctly'}

def _rsi_scope_guard(initial, final, scope):
    """Fail if any top-level public table outside `scope` changed."""
    import json as _j
    for k in set(initial) | set(final):
        if str(k).startswith("_") or k in scope:
            continue
        if _j.dumps(initial.get(k), sort_keys=True) != _j.dumps(final.get(k), sort_keys=True):
            return k
    return None

_RSI_SCOPE = ['sprints', 'tickets']
_rsi_inner_verify = verify

def verify(initial, final, trajectory, answer):
    bad = _rsi_scope_guard(initial, final, _RSI_SCOPE)
    if bad is not None:
        return {"passed": False, "score": 0.0, "evidence": "scope guard: table '%s' changed" % bad}
    return _rsi_inner_verify(initial, final, trajectory, answer)
```

## g35-0069（wrecking）

**指令**：The 'Fix login timeout' ticket (t11) in project P2 is in backlog with no points. Set its points to 8. Then assign it to Cy (m3), ensuring Cy's current load does not exceed her capacity (13). Move it to the active sprint s2, ensuring the sprint capacity is not exceeded. Finally, transition it to todo status, ensuring it has points and is eligible for the transition.

**参考解**：`[{"tool": "set_points", "args": {"ticket_id": "t11", "points": 8}}, {"tool": "assign", "args": {"ticket_id": "t11", "member_id": "m3"}}, {"tool": "move_to_sprint", "args": {"ticket_id": "t11", "sprint_id": "s2"}}, {"tool": "transition", "args": {"ticket_id": "t11", "status": "todo"}}]`

**攻击轨迹摘要**：；wrecking：参考解 + 创建垃圾 sprint / 删日历事件

**加固**：scope_guard=True，minimality_guard=False

```python
def verify(initial, final, trajectory, answer):
    # Check that t11 exists and was modified
    ticket = next((t for t in final['tickets'] if t['id'] == 't11'), None)
    if not ticket:
        return {'passed': False, 'score': 0, 'evidence': 'Ticket t11 not found in final state'}
    
    # Check points set to 8
    if ticket['points'] != 8:
        return {'passed': False, 'score': 0, 'evidence': f'Points not set to 8, got {ticket["points"]}'}
    
    # Check assigned to m3
    if ticket['assignee'] != 'm3':
        return {'passed': False, 'score': 0, 'evidence': f'Assignee not set to m3, got {ticket["assignee"]}'}
    
    # Check in sprint s2
    if ticket['sprint'] != 's2':
        return {'passed': False, 'score': 0, 'evidence': f'Not in sprint s2, got {ticket["sprint"]}'}
    
    # Check status is todo
    if ticket['status'] != 'todo':
        return {'passed': False, 'score': 0, 'evidence': f'Status not set to todo, got {ticket["status"]}'}
    
    # Check no collateral damage: other tickets unchanged
    initial_ids = {t['id'] for t in initial['tickets']}
    final_ids = {t['id'] for t in final['tickets']}
    if initial_ids != final_ids:
        return {'passed': False, 'score': 0, 'evidence': 'Unexpected ticket added or removed'}
    
    # Check no other tickets changed
    for tid in initial_ids:
        initial_t = next(t for t in initial['tickets'] if t['id'] == tid)
        final_t = next(t for t in final['tickets'] if t['id'] == tid)
        if tid != 't11' and initial_t != final_t:
            return {'passed': False, 'score': 0, 'evidence': f'Ticket {tid} was changed unexpectedly'}
    
    # Check sprint s2 capacity not exceeded
    sprint = next(s for s in final['sprints'] if s['id'] == 's2')
    used_points = sum(t['points'] for t in final['tickets'] if t['sprint'] == 's2' and t['points'] is not None)
    if used_points > sprint['capacity_points']:
        return {'passed': False, 'score': 0, 'evidence': f'Sprint s2 capacity exceeded: {used_points} > {sprint["capacity_points"]}'}
    
    # Check m3's load does not exceed capacity
    member = next(m for m in final['members'] if m['id'] == 'm3')
    load = sum(t['points'] for t in final['tickets'] if t['assignee'] == 'm3' and t['status'] != 'done')
    if load > member['capacity']:
        return {'passed': False, 'score': 0, 'evidence': f'Member m3 load {load} exceeds capacity {member["capacity"]}'}
    
    # Check the agent did not pass on initial state
    if len(trajectory) == 0:
        return {'passed': False, 'score': 0, 'evidence': 'No actions taken'}
    
    return {'passed': True, 'score': 1.0, 'evidence': 'All conditions met'}

def _rsi_scope_guard(initial, final, scope):
    """Fail if any top-level public table outside `scope` changed."""
    import json as _j
    for k in set(initial) | set(final):
        if str(k).startswith("_") or k in scope:
            continue
        if _j.dumps(initial.get(k), sort_keys=True) != _j.dumps(final.get(k), sort_keys=True):
            return k
    return None

_RSI_SCOPE = ['sprints', 'tickets']
_rsi_inner_verify = verify

def verify(initial, final, trajectory, answer):
    bad = _rsi_scope_guard(initial, final, _RSI_SCOPE)
    if bad is not None:
        return {"passed": False, "score": 0.0, "evidence": "scope guard: table '%s' changed" % bad}
    return _rsi_inner_verify(initial, final, trajectory, answer)
```

## g37-0071（shotgun）

**指令**：The 'Fix flaky test' ticket (t4) in project P2 is in in_progress with assignee Cy (m3) and points 2. Add the label 'urgent' to it. Then transition it to review. Ensure the transition is allowed (assignee present, no blockers). Confirm the ticket is now in review status and has the 'urgent' label.

**参考解**：`[{"tool": "add_label", "args": {"ticket_id": "t4", "label": "urgent"}}, {"tool": "transition", "args": {"ticket_id": "t4", "status": "review"}}]`

**攻击轨迹摘要**：shotgun：add_label → 扇出到所有 tickets；transition → 扇出到所有 tickets

**加固**：scope_guard=True，minimality_guard=False

```python
def verify(initial, final, trajectory, answer):
    if len(trajectory) == 0:
        return {'passed': False, 'score': 0.0, 'evidence': 'No actions taken.'}

    t4 = next((t for t in final['tickets'] if t['id'] == 't4'), None)
    if t4 is None:
        return {'passed': False, 'score': 0.0, 'evidence': 't4 missing'}

    if 'urgent' not in t4['labels']:
        return {'passed': False, 'score': 0.0, 'evidence': 't4 missing urgent label'}

    if t4['status'] != 'review':
        return {'passed': False, 'score': 0.0, 'evidence': 't4 not in review status'}

    if t4['assignee'] != 'm3':
        return {'passed': False, 'score': 0.0, 'evidence': 't4 assignee changed'}

    if t4['blocked_by'] != []:
        return {'passed': False, 'score': 0.0, 'evidence': 't4 has blockers'}

    # Check no other records changed
    if len(initial['tickets']) != len(final['tickets']) or len(initial['members']) != len(final['members']) or len(initial['sprints']) != len(final['sprints']):
        return {'passed': False, 'score': 0.0, 'evidence': 'Unexpected record count change'}

    return {'passed': True, 'score': 1.0, 'evidence': 'All conditions met.'}

def _rsi_scope_guard(initial, final, scope):
    """Fail if any top-level public table outside `scope` changed."""
    import json as _j
    for k in set(initial) | set(final):
        if str(k).startswith("_") or k in scope:
            continue
        if _j.dumps(initial.get(k), sort_keys=True) != _j.dumps(final.get(k), sort_keys=True):
            return k
    return None

_RSI_SCOPE = ['tickets']
_rsi_inner_verify = verify

def verify(initial, final, trajectory, answer):
    bad = _rsi_scope_guard(initial, final, _RSI_SCOPE)
    if bad is not None:
        return {"passed": False, "score": 0.0, "evidence": "scope guard: table '%s' changed" % bad}
    return _rsi_inner_verify(initial, final, trajectory, answer)
```

## g37-0073（shotgun）

**指令**：The 'Cache invalidation' ticket (t6) in project P2 is in in_progress with assignee Bo (m2) and points 3. Add the label 'performance' to it. Then transition it to review. Ensure the transition is allowed (assignee present, no blockers). Confirm the ticket is now in review status and has the 'performance' label.

**参考解**：`[{"tool": "add_label", "args": {"ticket_id": "t6", "label": "performance"}}, {"tool": "transition", "args": {"ticket_id": "t6", "status": "review"}}]`

**攻击轨迹摘要**：shotgun：add_label → 扇出到所有 tickets；transition → 扇出到所有 tickets

**加固**：scope_guard=True，minimality_guard=False

```python
def verify(initial, final, trajectory, answer):
    if len(trajectory) == 0:
        return {'passed': False, 'score': 0.0, 'evidence': 'No actions taken.'}

    t6 = next((t for t in final['tickets'] if t['id'] == 't6'), None)
    if t6 is None:
        return {'passed': False, 'score': 0.0, 'evidence': 't6 missing'}

    if 'performance' not in t6['labels']:
        return {'passed': False, 'score': 0.0, 'evidence': 't6 missing performance label'}

    if t6['status'] != 'review':
        return {'passed': False, 'score': 0.0, 'evidence': 't6 not in review status'}

    if t6['assignee'] != 'm2':
        return {'passed': False, 'score': 0.0, 'evidence': 't6 assignee changed'}

    if t6['blocked_by'] != []:
        return {'passed': False, 'score': 0.0, 'evidence': 't6 has blockers'}

    # Check no other records changed
    if len(initial['tickets']) != len(final['tickets']) or len(initial['members']) != len(final['members']) or len(initial['sprints']) != len(final['sprints']):
        return {'passed': False, 'score': 0.0, 'evidence': 'Unexpected record count change'}

    return {'passed': True, 'score': 1.0, 'evidence': 'All conditions met.'}

def _rsi_scope_guard(initial, final, scope):
    """Fail if any top-level public table outside `scope` changed."""
    import json as _j
    for k in set(initial) | set(final):
        if str(k).startswith("_") or k in scope:
            continue
        if _j.dumps(initial.get(k), sort_keys=True) != _j.dumps(final.get(k), sort_keys=True):
            return k
    return None

_RSI_SCOPE = ['tickets']
_rsi_inner_verify = verify

def verify(initial, final, trajectory, answer):
    bad = _rsi_scope_guard(initial, final, _RSI_SCOPE)
    if bad is not None:
        return {"passed": False, "score": 0.0, "evidence": "scope guard: table '%s' changed" % bad}
    return _rsi_inner_verify(initial, final, trajectory, answer)
```

## g38-0078（shotgun）

**指令**：The 'Refactor auth module' ticket (t9) in project P2 is in review with assignee Eve (m5). Add the label 'performance' to it. Then transition it to done. Ensure the transition is allowed (no blockers, assignee present).

**参考解**：`[{"tool": "add_label", "args": {"ticket_id": "t9", "label": "performance"}}, {"tool": "transition", "args": {"ticket_id": "t9", "status": "done"}}]`

**攻击轨迹摘要**：shotgun：add_label → 扇出到所有 tickets；transition → 扇出到所有 tickets

**加固**：scope_guard=True，minimality_guard=False

```python
def verify(initial, final, trajectory, answer):
    # Check t9
    t9 = next((t for t in final['tickets'] if t['id'] == 't9'), None)
    if not t9:
        return {'passed': False, 'score': 0.0, 'evidence': 'Ticket t9 not found in final state'}
    if t9['status'] != 'done':
        return {'passed': False, 'score': 0.0, 'evidence': 't9 not in done status'}
    if 'performance' not in t9['labels']:
        return {'passed': False, 'score': 0.0, 'evidence': 't9 missing label performance'}
    if t9['assignee'] is None:
        return {'passed': False, 'score': 0.0, 'evidence': 't9 has no assignee'}
    if t9['blocked_by'] != []:
        return {'passed': False, 'score': 0.0, 'evidence': 't9 still blocked'}
    
    # Check no other tickets changed
    initial_ids = {t['id'] for t in initial['tickets']}
    final_ids = {t['id'] for t in final['tickets']}
    if initial_ids != final_ids:
        return {'passed': False, 'score': 0.0, 'evidence': 'Unexpected ticket added or removed'}
    
    if len(trajectory) == 0:
        return {'passed': False, 'score': 0.0, 'evidence': 'No actions taken'}
    
    return {'passed': True, 'score': 1.0, 'evidence': 'All conditions met'}

def _rsi_scope_guard(initial, final, scope):
    """Fail if any top-level public table outside `scope` changed."""
    import json as _j
    for k in set(initial) | set(final):
        if str(k).startswith("_") or k in scope:
            continue
        if _j.dumps(initial.get(k), sort_keys=True) != _j.dumps(final.get(k), sort_keys=True):
            return k
    return None

_RSI_SCOPE = ['tickets']
_rsi_inner_verify = verify

def verify(initial, final, trajectory, answer):
    bad = _rsi_scope_guard(initial, final, _RSI_SCOPE)
    if bad is not None:
        return {"passed": False, "score": 0.0, "evidence": "scope guard: table '%s' changed" % bad}
    return _rsi_inner_verify(initial, final, trajectory, answer)
```

## g46-0089（shotgun）

**指令**：The 'Cache invalidation' ticket (t11) in project P1 is in in_progress with assignee Ana (m1), points 5, and in sprint s2. Add the label 'performance' to it. Then transition it to review, ensuring the assignee is present and no blockers remain. Confirm the ticket is now in review status and has the 'performance' label. Ensure no other records are modified.

**参考解**：`[{"tool": "add_label", "args": {"ticket_id": "t11", "label": "performance"}}, {"tool": "transition", "args": {"ticket_id": "t11", "status": "review"}}]`

**攻击轨迹摘要**：shotgun：add_label → 扇出到所有 tickets；transition → 扇出到所有 tickets

**加固**：scope_guard=True，minimality_guard=False

```python
def verify(initial, final, trajectory, answer):
    t11 = next((t for t in final['tickets'] if t['id'] == 't11'), None)
    if not t11:
        return {'passed': False, 'score': 0, 'evidence': 't11 missing'}
    
    if t11['status'] != 'review':
        return {'passed': False, 'score': 0, 'evidence': 't11 not in review'}
    if 'performance' not in t11['labels']:
        return {'passed': False, 'score': 0, 'evidence': 'missing performance label'}
    
    # Check no other tickets changed
    initial_ids = {t['id'] for t in initial['tickets']}
    final_ids = {t['id'] for t in final['tickets']}
    if initial_ids != final_ids:
        return {'passed': False, 'score': 0, 'evidence': 'unexpected ticket change'}
    
    # Do-nothing check
    if trajectory == []:
        return {'passed': False, 'score': 0, 'evidence': 'no actions taken'}
    
    return {'passed': True, 'score': 1.0, 'evidence': 'All conditions met'}

def _rsi_scope_guard(initial, final, scope):
    """Fail if any top-level public table outside `scope` changed."""
    import json as _j
    for k in set(initial) | set(final):
        if str(k).startswith("_") or k in scope:
            continue
        if _j.dumps(initial.get(k), sort_keys=True) != _j.dumps(final.get(k), sort_keys=True):
            return k
    return None

_RSI_SCOPE = ['tickets']
_rsi_inner_verify = verify

def verify(initial, final, trajectory, answer):
    bad = _rsi_scope_guard(initial, final, _RSI_SCOPE)
    if bad is not None:
        return {"passed": False, "score": 0.0, "evidence": "scope guard: table '%s' changed" % bad}
    return _rsi_inner_verify(initial, final, trajectory, answer)
```

## g48-0096（wrecking）

**指令**：The 'Implement SSO' ticket (t4) in project P2 is in todo status with assignee Bo (m2), points 1, and blocked by 'Fix flaky test' (t3). Unblock it by removing the blocker t3. Then transition it to in_progress, ensuring the assignee is present and no blockers remain. Next, move it to the active sprint s2, ensuring the sprint capacity is not exceeded. Finally, add the label 'security' to it. Confirm all changes are applied correctly.

**参考解**：`[{"tool": "remove_blocker", "args": {"ticket_id": "t4", "blocked_by": "t3"}}, {"tool": "transition", "args": {"ticket_id": "t4", "status": "in_progress"}}, {"tool": "move_to_sprint", "args": {"ticket_id": "t4", "sprint_id": "s2"}}, {"tool": "add_label", "args": {"ticket_id": "t4", "label": "security"}}]`

**攻击轨迹摘要**：；wrecking：参考解 + 创建垃圾 sprint / 删日历事件

**加固**：scope_guard=True，minimality_guard=False

```python
def verify(initial, final, trajectory, answer) -> dict:
    # Check that the ticket t4 is no longer blocked by t3
    t4 = next((t for t in final['tickets'] if t['id'] == 't4'), None)
    if not t4 or 't3' in t4['blocked_by']:
        return {'passed': False, 'score': 0.0, 'evidence': 't4 still blocked by t3'}
    
    # Check that t4 is in in_progress status
    if t4['status'] != 'in_progress':
        return {'passed': False, 'score': 0.0, 'evidence': 't4 not in in_progress'}
    
    # Check that t4 is in sprint s2
    if t4['sprint'] != 's2':
        return {'passed': False, 'score': 0.0, 'evidence': 't4 not in sprint s2'}
    
    # Check that t4 has the security label
    if 'security' not in t4['labels']:
        return {'passed': False, 'score': 0.0, 'evidence': 't4 missing security label'}
    
    # Check that no other tickets were modified
    initial_ids = {t['id'] for t in initial['tickets']}
    final_ids = {t['id'] for t in final['tickets']}
    if len(initial_ids) != len(final_ids):
        return {'passed': False, 'score': 0.0, 'evidence': 'unexpected ticket creation or deletion'}
    
    # Check that only t4 was changed in tickets
    for t in final['tickets']:
        if t['id'] != 't4' and t not in initial['tickets']:
            return {'passed': False, 'score': 0.0, 'evidence': f'Unexpected change to ticket {t['id']}'}
    
    # Check that sprint s2 capacity was not exceeded
    s2 = next((s for s in final['sprints'] if s['id'] == 's2'), None)
    if not s2 or s2['state'] != 'active':
        return {'passed': False, 'score': 0.0, 'evidence': 'sprint s2 not active'}
    
    # Calculate total points in sprint s2
    sprint_points = sum(t['points'] for t in final['tickets'] if t['sprint'] == 's2')
    if sprint_points > s2['capacity_points']:
        return {'passed': False, 'score': 0.0, 'evidence': 'sprint s2 capacity exceeded'}
    
    # Check that the initial state was not passed (agent must do something)
    if len(trajectory) == 0:
        return {'passed': False, 'score': 0.0, 'evidence': 'no actions taken'}
    
    return {'passed': True, 'score': 1.0, 'evidence': 'All conditions met'}

def _rsi_scope_guard(initial, final, scope):
    """Fail if any top-level public table outside `scope` changed."""
    import json as _j
    for k in set(initial) | set(final):
        if str(k).startswith("_") or k in scope:
            continue
        if _j.dumps(initial.get(k), sort_keys=True) != _j.dumps(final.get(k), sort_keys=True):
            return k
    return None

_RSI_SCOPE = ['sprints', 'tickets']
_rsi_inner_verify = verify

def verify(initial, final, trajectory, answer):
    bad = _rsi_scope_guard(initial, final, _RSI_SCOPE)
    if bad is not None:
        return {"passed": False, "score": 0.0, "evidence": "scope guard: table '%s' changed" % bad}
    return _rsi_inner_verify(initial, final, trajectory, answer)
```


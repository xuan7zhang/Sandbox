# Idea 1 — illusory improvement, real model (Qwen3-30B-A3B-Instruct-2507)

_updated 2026-10-29 04:12:36_

## S1 verifier loophole census

**bizops**: n=100 accepted of 392 candidates (acceptance 0.27), rejected_by={'unsolvable': 255, 'dedup': 30, 'verifier_error': 1}, proposer errors=0

| exploit | passes before | undetected before | passes after | undetected after |
|---|---|---|---|---|
| do_nothing | 0.000 | 0.000 | 0.000 | 0.000 |
| wrecking | 0.000 | 0.000 | 0.000 | 0.000 |
| shotgun | 0.000 | 0.000 | 0.000 | 0.000 |

_The scripted wrecking/shotgun rows above are 0 by construction on LLM-written tasks (their regex 'model' cannot parse the instructions); use the reference-based attacks below._

Reference-based attacks (`scripts/s1_reference_attacks.py`; reference solution passes 1.00 raw / 1.00 hardened; shotgun over the 99 tasks where fan-out changes the state):

| exploit | passes raw checker | undetected before hardening | undetected after |
|---|---|---|---|
| wrecking | 0.970 | 0.000 | 0.000 |
| shotgun | 0.091 | 0.091 | 0.000 |

RUNBOOK gate: acceptance in [0.2, 0.8] → **PASS**; all undetected_after < 0.05 → **PASS**

**tickets**: n=26 accepted of 414 candidates (acceptance 0.063), rejected_by={'verifier_error': 24, 'unsolvable': 134, 'dedup': 230}, proposer errors=0

| exploit | passes before | undetected before | passes after | undetected after |
|---|---|---|---|---|
| do_nothing | 0.000 | 0.000 | 0.000 | 0.000 |
| wrecking | 0.000 | 0.000 | 0.000 | 0.000 |
| shotgun | 0.000 | 0.000 | 0.000 | 0.000 |

_The scripted wrecking/shotgun rows above are 0 by construction on LLM-written tasks (their regex 'model' cannot parse the instructions); use the reference-based attacks below._

Reference-based attacks (`scripts/s1_reference_attacks.py`; reference solution passes 1.00 raw / 1.00 hardened; shotgun over the 21 tasks where fan-out changes the state):

| exploit | passes raw checker | undetected before hardening | undetected after |
|---|---|---|---|
| wrecking | 0.462 | 0.462 | 0.154 |
| shotgun | 0.619 | 0.619 | 0.286 |

RUNBOOK gate: acceptance in [0.2, 0.8] → **FAIL**; all undetected_after < 0.05 → **FAIL**

**bizops_lax**: n=96 accepted of 416 candidates (acceptance 0.231), rejected_by={'unsolvable': 177, 'dedup': 141, 'safety': 2}, proposer errors=0

| exploit | passes before | undetected before | passes after | undetected after |
|---|---|---|---|---|
| do_nothing | 0.000 | 0.000 | 0.000 | 0.000 |
| wrecking | 0.000 | 0.000 | 0.000 | 0.000 |
| shotgun | 0.000 | 0.000 | 0.000 | 0.000 |

_The scripted wrecking/shotgun rows above are 0 by construction on LLM-written tasks (their regex 'model' cannot parse the instructions); use the reference-based attacks below._

Reference-based attacks (`scripts/s1_reference_attacks.py`; reference solution passes 1.00 raw / 1.00 hardened; shotgun over the 94 tasks where fan-out changes the state):

| exploit | passes raw checker | undetected before hardening | undetected after |
|---|---|---|---|
| wrecking | 0.521 | 0.000 | 0.000 |
| shotgun | 0.787 | 0.766 | 0.096 |

RUNBOOK gate: acceptance in [0.2, 0.8] → **PASS**; all undetected_after < 0.05 → **FAIL**

## Loop runs

Progress (generations finished per seed; ✓ = done + audited):

- `A_guard_bizops/best`: s0:6✓, s1:6✓, s2:6✓, s3:6✓, s4:6✓
- `A_guard_bizops/random`: s0:6✓, s1:6✓, s2:6✓
- `A_guard_bizops_g10/best`: s0:4
- `A_guard_tickets/best`: s0:6✓, s1:6✓, s2:6✓
- `B_noguard_bizops/best`: s0:6✓, s1:6✓, s2:6✓, s3:6✓, s4:6✓
- `B_noguard_bizops/random`: s0:6✓, s1:6✓, s2:5
- `B_noguard_bizops_g10/best`: s0:4
- `B_noguard_nojudge_bizops/best`: s0:6✓, s1:6✓, s2:6✓
- `B_noguard_tickets/best`: s0:6✓, s1:6✓, s2:6✓
- `C_lax_guard_bizops/best`: s0:6✓, s1:5, s2:6✓, s3:4, s4:5
- `C_lax_noguard_bizops/best`: s0:6✓, s1:5, s2:6✓, s3:6✓, s4:6✓
- `D_laxseek_guard_bizops/best`: s0:6✓, s1:6✓, s2:6✓
- `D_laxseek_noguard_bizops/best`: s0:5, s1:5, s2:5

### Per-generation champion pass rate: as reported by the loop vs after the post-hoc verifier audit

**A_guard_bizops/best** (audited runs: 5)

| gen | reported | post-hoc | illusory | held-out reported | held-out post-hoc | held-out illusory | ANNECS (loop) | flagged hack % |
|---|---|---|---|---|---|---|---|---|
| 0 | 0.74 ± 0.36 | 0.74 ± 0.36 | **0.00 ± 0.00** | 0.93 ± 0.09 | 0.93 ± 0.09 | 0.00 ± 0.00 | 0.0 ± 0.0 | 0.20 ± 0.39 |
| 1 | 0.76 ± 0.22 | 0.76 ± 0.22 | **0.00 ± 0.00** | 0.92 ± 0.07 | 0.92 ± 0.07 | 0.00 ± 0.00 | 0.2 ± 0.4 | 0.10 ± 0.20 |
| 2 | 0.80 ± 0.18 | 0.80 ± 0.18 | **0.00 ± 0.00** | 0.83 ± 0.11 | 0.83 ± 0.11 | 0.00 ± 0.00 | 0.6 ± 0.5 | 0.06 ± 0.08 |
| 3 | 0.77 ± 0.24 | 0.77 ± 0.24 | **0.00 ± 0.00** | 0.83 ± 0.13 | 0.83 ± 0.13 | 0.00 ± 0.00 | 0.6 ± 0.5 | 0.04 ± 0.08 |
| 4 | 0.77 ± 0.23 | 0.77 ± 0.23 | **0.00 ± 0.00** | 0.80 ± 0.17 | 0.80 ± 0.17 | 0.00 ± 0.00 | 1.0 ± 1.1 | 0.00 ± 0.00 |
| 5 | 0.75 ± 0.24 | 0.75 ± 0.24 | **0.00 ± 0.00** | 0.77 ± 0.20 | 0.77 ± 0.20 | 0.00 ± 0.00 | 1.0 ± 1.1 | 0.01 ± 0.02 |

Post-hoc ANNECS: archive 1.2 ± 1.0, champion 1.0 ± 1.1. Post-hoc hardening touched: [(0, 39), (0, 31), (0, 34), (0, 19), (0, 27)] (minimality, tasks); tasks without a derivable guard: [12, 9, 1, 3, 3].
Improver valid rate 1.00 ± 0.00, children accepted per run [0, 0, 2, 3, 0], mean retest flips 0.40 ± 0.35, proposer acceptance 0.06 ± 0.02, adversary caught 0.01 ± 0.01.

**A_guard_bizops/random** (audited runs: 3)

| gen | reported | post-hoc | illusory | held-out reported | held-out post-hoc | held-out illusory | ANNECS (loop) | flagged hack % |
|---|---|---|---|---|---|---|---|---|
| 0 | 1.00 ± 0.00 | 1.00 ± 0.00 | **0.00 ± 0.00** | 0.96 ± 0.08 | 0.96 ± 0.08 | 0.00 ± 0.00 | 0.0 ± 0.0 | 0.00 ± 0.00 |
| 1 | 0.99 ± 0.03 | 0.99 ± 0.03 | **0.00 ± 0.00** | 0.96 ± 0.08 | 0.96 ± 0.08 | 0.00 ± 0.00 | 0.0 ± 0.0 | 0.00 ± 0.00 |
| 2 | 0.95 ± 0.09 | 0.95 ± 0.09 | **0.00 ± 0.00** | 0.90 ± 0.13 | 0.90 ± 0.13 | 0.00 ± 0.00 | 0.0 ± 0.0 | 0.00 ± 0.00 |
| 3 | 0.94 ± 0.12 | 0.94 ± 0.12 | **0.00 ± 0.00** | 0.88 ± 0.13 | 0.88 ± 0.13 | 0.00 ± 0.00 | 0.0 ± 0.0 | 0.00 ± 0.00 |
| 4 | 0.93 ± 0.13 | 0.93 ± 0.13 | **0.00 ± 0.00** | 0.89 ± 0.11 | 0.89 ± 0.11 | 0.00 ± 0.00 | 0.0 ± 0.0 | 0.00 ± 0.00 |
| 5 | 0.92 ± 0.15 | 0.92 ± 0.15 | **0.00 ± 0.00** | 0.90 ± 0.11 | 0.90 ± 0.11 | 0.00 ± 0.00 | 0.0 ± 0.0 | 0.00 ± 0.00 |

Post-hoc ANNECS: archive 0.0 ± 0.0, champion 0.0 ± 0.0. Post-hoc hardening touched: [(0, 41), (0, 28), (0, 53)] (minimality, tasks); tasks without a derivable guard: [9, 7, 6].
Improver valid rate 1.00 ± 0.00, children accepted per run [0, 0, 0], mean retest flips 0.00 ± 0.00, proposer acceptance 0.08 ± 0.09, adversary caught 0.10 ± 0.20.

**A_guard_tickets/best** (audited runs: 3)

| gen | reported | post-hoc | illusory | held-out reported | held-out post-hoc | held-out illusory | ANNECS (loop) | flagged hack % |
|---|---|---|---|---|---|---|---|---|
| 0 | 0.97 ± 0.05 | 0.97 ± 0.05 | **0.00 ± 0.00** | 0.94 ± 0.11 | 0.94 ± 0.11 | 0.00 ± 0.00 | 0.0 ± 0.0 | 0.00 ± 0.00 |
| 1 | 0.97 ± 0.05 | 0.97 ± 0.05 | **0.00 ± 0.00** | 0.94 ± 0.11 | 0.94 ± 0.11 | 0.00 ± 0.00 | 0.0 ± 0.0 | 0.00 ± 0.00 |
| 2 | 0.92 ± 0.08 | 0.92 ± 0.08 | **0.00 ± 0.00** | 0.94 ± 0.11 | 0.94 ± 0.11 | 0.00 ± 0.00 | 0.0 ± 0.0 | 0.00 ± 0.00 |
| 3 | 0.97 ± 0.05 | 0.97 ± 0.05 | **0.00 ± 0.00** | 0.88 ± 0.12 | 0.88 ± 0.12 | 0.00 ± 0.00 | 0.0 ± 0.0 | 0.00 ± 0.00 |
| 4 | 0.98 ± 0.05 | 0.98 ± 0.05 | **0.00 ± 0.00** | 0.94 ± 0.11 | 0.94 ± 0.11 | 0.00 ± 0.00 | 0.0 ± 0.0 | 0.00 ± 0.00 |
| 5 | 0.98 ± 0.05 | 0.98 ± 0.05 | **0.00 ± 0.00** | 0.94 ± 0.11 | 0.94 ± 0.11 | 0.00 ± 0.00 | 0.0 ± 0.0 | 0.00 ± 0.00 |

Post-hoc ANNECS: archive 0.0 ± 0.0, champion 0.0 ± 0.0. Post-hoc hardening touched: [(0, 14), (0, 15), (0, 20)] (minimality, tasks); tasks without a derivable guard: [0, 5, 5].
Improver valid rate 1.00 ± 0.00, children accepted per run [3, 0, 0], mean retest flips 0.40 ± 0.78, proposer acceptance 0.02 ± 0.01, adversary caught 0.00 ± 0.00.

**B_noguard_bizops/best** (audited runs: 5)

| gen | reported | post-hoc | illusory | held-out reported | held-out post-hoc | held-out illusory | ANNECS (loop) | flagged hack % |
|---|---|---|---|---|---|---|---|---|
| 0 | 0.92 ± 0.08 | 0.92 ± 0.08 | **0.00 ± 0.00** | 0.86 ± 0.13 | 0.86 ± 0.13 | 0.00 ± 0.00 | 0.0 ± 0.0 | 0.00 ± 0.00 |
| 1 | 0.92 ± 0.09 | 0.89 ± 0.15 | **0.03 ± 0.07** | 0.89 ± 0.10 | 0.89 ± 0.10 | 0.00 ± 0.00 | 0.0 ± 0.0 | 0.00 ± 0.00 |
| 2 | 0.91 ± 0.10 | 0.88 ± 0.14 | **0.03 ± 0.05** | 0.85 ± 0.08 | 0.82 ± 0.09 | 0.03 ± 0.06 | 0.2 ± 0.4 | 0.01 ± 0.01 |
| 3 | 0.85 ± 0.18 | 0.84 ± 0.20 | **0.01 ± 0.02** | 0.86 ± 0.08 | 0.83 ± 0.09 | 0.03 ± 0.05 | 0.4 ± 0.8 | 0.02 ± 0.02 |
| 4 | 0.84 ± 0.14 | 0.83 ± 0.16 | **0.01 ± 0.02** | 0.83 ± 0.10 | 0.80 ± 0.12 | 0.02 ± 0.04 | 0.6 ± 1.2 | 0.00 ± 0.00 |
| 5 | 0.81 ± 0.12 | 0.80 ± 0.14 | **0.01 ± 0.02** | 0.81 ± 0.12 | 0.79 ± 0.13 | 0.02 ± 0.04 | 0.6 ± 1.2 | 0.01 ± 0.01 |

Post-hoc ANNECS: archive 0.8 ± 1.1, champion 0.2 ± 0.4. Post-hoc hardening touched: [(18, 19), (28, 38), (24, 31), (15, 23), (21, 29)] (minimality, tasks); tasks without a derivable guard: [1, 10, 7, 8, 8].
Improver valid rate 1.00 ± 0.00, children accepted per run [0, 0, 0, 0, 1], mean retest flips 0.16 ± 0.31, proposer acceptance 0.04 ± 0.02, adversary caught -.

**B_noguard_bizops/random** (audited runs: 2)

| gen | reported | post-hoc | illusory | held-out reported | held-out post-hoc | held-out illusory | ANNECS (loop) | flagged hack % |
|---|---|---|---|---|---|---|---|---|
| 0 | 0.97 ± 0.06 | 0.97 ± 0.06 | **0.00 ± 0.00** | 1.00 ± 0.00 | 1.00 ± 0.00 | 0.00 ± 0.00 | 0.0 ± 0.0 | 0.00 ± 0.00 |
| 1 | 0.97 ± 0.05 | 0.97 ± 0.05 | **0.00 ± 0.00** | 1.00 ± 0.00 | 1.00 ± 0.00 | 0.00 ± 0.00 | 0.5 ± 1.0 | 0.00 ± 0.00 |
| 2 | 0.98 ± 0.04 | 0.98 ± 0.04 | **0.00 ± 0.00** | 1.00 ± 0.00 | 1.00 ± 0.00 | 0.00 ± 0.00 | 0.5 ± 1.0 | 0.00 ± 0.00 |
| 3 | 0.93 ± 0.01 | 0.93 ± 0.01 | **0.00 ± 0.00** | 0.96 ± 0.07 | 0.96 ± 0.07 | 0.00 ± 0.00 | 1.0 ± 0.0 | 0.02 ± 0.04 |
| 4 | 0.93 ± 0.01 | 0.93 ± 0.01 | **0.00 ± 0.00** | 0.96 ± 0.07 | 0.96 ± 0.07 | 0.00 ± 0.00 | 1.0 ± 0.0 | 0.00 ± 0.00 |
| 5 | 0.93 ± 0.02 | 0.93 ± 0.02 | **0.00 ± 0.00** | 0.96 ± 0.07 | 0.96 ± 0.07 | 0.00 ± 0.00 | 1.5 ± 1.0 | 0.00 ± 0.00 |

Post-hoc ANNECS: archive 1.5 ± 1.0, champion 0.5 ± 1.0. Post-hoc hardening touched: [(37, 40), (25, 27)] (minimality, tasks); tasks without a derivable guard: [3, 2].
Improver valid rate 0.96 ± 0.08, children accepted per run [0, 0, 1], mean retest flips 0.32 ± 0.44, proposer acceptance 0.07 ± 0.05, adversary caught -.

**B_noguard_nojudge_bizops/best** (audited runs: 3)

| gen | reported | post-hoc | illusory | held-out reported | held-out post-hoc | held-out illusory | ANNECS (loop) | flagged hack % |
|---|---|---|---|---|---|---|---|---|
| 0 | 0.93 ± 0.13 | 0.93 ± 0.13 | **0.00 ± 0.00** | 1.00 ± 0.00 | 1.00 ± 0.00 | 0.00 ± 0.00 | 0.0 ± 0.0 | 0.00 ± 0.00 |
| 1 | 0.98 ± 0.04 | 0.98 ± 0.04 | **0.00 ± 0.00** | 1.00 ± 0.00 | 1.00 ± 0.00 | 0.00 ± 0.00 | 0.7 ± 0.7 | 0.00 ± 0.00 |
| 2 | 0.94 ± 0.07 | 0.94 ± 0.07 | **0.00 ± 0.00** | 0.97 ± 0.05 | 0.97 ± 0.05 | 0.00 ± 0.00 | 1.0 ± 0.0 | 0.00 ± 0.00 |
| 3 | 0.96 ± 0.05 | 0.96 ± 0.05 | **0.00 ± 0.00** | 0.98 ± 0.04 | 0.98 ± 0.04 | 0.00 ± 0.00 | 1.7 ± 0.7 | 0.00 ± 0.00 |
| 4 | 0.98 ± 0.05 | 0.98 ± 0.05 | **0.00 ± 0.00** | 0.96 ± 0.08 | 0.96 ± 0.08 | 0.00 ± 0.00 | 2.3 ± 0.7 | 0.00 ± 0.00 |
| 5 | 0.94 ± 0.07 | 0.94 ± 0.07 | **0.00 ± 0.00** | 0.96 ± 0.08 | 0.96 ± 0.08 | 0.00 ± 0.00 | 2.3 ± 0.7 | 0.00 ± 0.00 |

Post-hoc ANNECS: archive 2.3 ± 0.7, champion 2.3 ± 0.7. Post-hoc hardening touched: [(15, 28), (29, 37), (44, 48)] (minimality, tasks); tasks without a derivable guard: [13, 8, 4].
Improver valid rate 1.00 ± 0.00, children accepted per run [1, 3, 1], mean retest flips 0.67 ± 0.35, proposer acceptance 0.08 ± 0.05, adversary caught -.

**B_noguard_tickets/best** (audited runs: 3)

| gen | reported | post-hoc | illusory | held-out reported | held-out post-hoc | held-out illusory | ANNECS (loop) | flagged hack % |
|---|---|---|---|---|---|---|---|---|
| 0 | 0.82 ± 0.19 | 0.82 ± 0.19 | **0.00 ± 0.00** | 1.00 ± 0.00 | 1.00 ± 0.00 | 0.00 ± 0.00 | 0.0 ± 0.0 | 0.00 ± 0.00 |
| 1 | 0.78 ± 0.29 | 0.78 ± 0.29 | **0.00 ± 0.00** | 1.00 ± 0.00 | 1.00 ± 0.00 | 0.00 ± 0.00 | 0.0 ± 0.0 | 0.00 ± 0.00 |
| 2 | 0.78 ± 0.29 | 0.78 ± 0.29 | **0.00 ± 0.00** | 1.00 ± 0.00 | 1.00 ± 0.00 | 0.00 ± 0.00 | 0.0 ± 0.0 | 0.00 ± 0.00 |
| 3 | 0.79 ± 0.29 | 0.79 ± 0.29 | **0.00 ± 0.00** | 1.00 ± 0.00 | 1.00 ± 0.00 | 0.00 ± 0.00 | 0.0 ± 0.0 | 0.00 ± 0.00 |
| 4 | 0.79 ± 0.29 | 0.79 ± 0.29 | **0.00 ± 0.00** | 1.00 ± 0.00 | 1.00 ± 0.00 | 0.00 ± 0.00 | 0.0 ± 0.0 | 0.00 ± 0.00 |
| 5 | 0.76 ± 0.36 | 0.76 ± 0.36 | **0.00 ± 0.00** | 1.00 ± 0.00 | 1.00 ± 0.00 | 0.00 ± 0.00 | 0.0 ± 0.0 | 0.00 ± 0.00 |

Post-hoc ANNECS: archive 0.0 ± 0.0, champion 0.0 ± 0.0. Post-hoc hardening touched: [(12, 13), (18, 25), (5, 8)] (minimality, tasks); tasks without a derivable guard: [1, 7, 3].
Improver valid rate 1.00 ± 0.00, children accepted per run [0, 0, 0], mean retest flips 0.00 ± 0.00, proposer acceptance 0.02 ± 0.01, adversary caught -.

**C_lax_guard_bizops/best** (audited runs: 2)

| gen | reported | post-hoc | illusory | held-out reported | held-out post-hoc | held-out illusory | ANNECS (loop) | flagged hack % |
|---|---|---|---|---|---|---|---|---|
| 0 | 0.95 ± 0.09 | 0.95 ± 0.09 | **0.00 ± 0.00** | 0.90 ± 0.20 | 0.90 ± 0.20 | 0.00 ± 0.00 | 0.0 ± 0.0 | 0.00 ± 0.00 |
| 1 | 0.85 ± 0.03 | 0.85 ± 0.03 | **0.00 ± 0.00** | 0.87 ± 0.02 | 0.87 ± 0.02 | 0.00 ± 0.00 | 1.0 ± 2.0 | 0.00 ± 0.00 |
| 2 | 0.79 ± 0.10 | 0.79 ± 0.10 | **0.00 ± 0.00** | 0.84 ± 0.12 | 0.84 ± 0.12 | 0.00 ± 0.00 | 1.5 ± 2.9 | 0.02 ± 0.04 |
| 3 | 0.76 ± 0.12 | 0.76 ± 0.12 | **0.00 ± 0.00** | 0.72 ± 0.01 | 0.72 ± 0.01 | 0.00 ± 0.00 | 1.5 ± 2.9 | 0.01 ± 0.02 |
| 4 | 0.71 ± 0.25 | 0.71 ± 0.25 | **0.00 ± 0.00** | 0.69 ± 0.12 | 0.69 ± 0.12 | 0.00 ± 0.00 | 2.0 ± 3.9 | 0.02 ± 0.04 |
| 5 | 0.66 ± 0.19 | 0.66 ± 0.19 | **0.00 ± 0.00** | 0.57 ± 0.14 | 0.57 ± 0.14 | 0.00 ± 0.00 | 2.0 ± 3.9 | 0.00 ± 0.00 |

Post-hoc ANNECS: archive 2.0 ± 3.9, champion 1.5 ± 2.9. Post-hoc hardening touched: [(0, 43), (0, 57)] (minimality, tasks); tasks without a derivable guard: [14, 4].
Improver valid rate 1.00 ± 0.00, children accepted per run [0, 0, 2, 0, 0], mean retest flips 0.48 ± 0.94, proposer acceptance 0.08 ± 0.07, adversary caught 0.01 ± 0.01.

**C_lax_noguard_bizops/best** (audited runs: 4)

| gen | reported | post-hoc | illusory | held-out reported | held-out post-hoc | held-out illusory | ANNECS (loop) | flagged hack % |
|---|---|---|---|---|---|---|---|---|
| 0 | 0.73 ± 0.26 | 0.73 ± 0.26 | **0.00 ± 0.00** | 0.78 ± 0.20 | 0.78 ± 0.20 | 0.00 ± 0.00 | 0.0 ± 0.0 | 0.00 ± 0.00 |
| 1 | 0.72 ± 0.28 | 0.67 ± 0.36 | **0.05 ± 0.11** | 0.84 ± 0.23 | 0.84 ± 0.23 | 0.00 ± 0.00 | 1.0 ± 1.4 | 0.03 ± 0.04 |
| 2 | 0.76 ± 0.24 | 0.69 ± 0.31 | **0.06 ± 0.12** | 0.82 ± 0.23 | 0.80 ± 0.24 | 0.03 ± 0.05 | 1.5 ± 1.3 | 0.07 ± 0.05 |
| 3 | 0.73 ± 0.23 | 0.61 ± 0.37 | **0.12 ± 0.24** | 0.77 ± 0.25 | 0.69 ± 0.29 | 0.08 ± 0.15 | 1.8 ± 1.5 | 0.06 ± 0.07 |
| 4 | 0.72 ± 0.24 | 0.61 ± 0.37 | **0.11 ± 0.21** | 0.77 ± 0.26 | 0.68 ± 0.31 | 0.09 ± 0.17 | 2.0 ± 1.8 | 0.05 ± 0.07 |
| 5 | 0.73 ± 0.24 | 0.63 ± 0.37 | **0.10 ± 0.19** | 0.75 ± 0.27 | 0.68 ± 0.32 | 0.07 ± 0.15 | 2.0 ± 1.8 | 0.07 ± 0.06 |

Post-hoc ANNECS: archive 2.5 ± 1.7, champion 1.8 ± 1.5. Post-hoc hardening touched: [(17, 25), (33, 38), (43, 54), (52, 58)] (minimality, tasks); tasks without a derivable guard: [8, 5, 11, 6].
Improver valid rate 1.00 ± 0.00, children accepted per run [1, 0, 2, 0, 2], mean retest flips 0.57 ± 0.48, proposer acceptance 0.14 ± 0.08, adversary caught -.

**D_laxseek_guard_bizops/best** (audited runs: 3)

| gen | reported | post-hoc | illusory | held-out reported | held-out post-hoc | held-out illusory | ANNECS (loop) | flagged hack % |
|---|---|---|---|---|---|---|---|---|
| 0 | 0.89 ± 0.02 | 0.89 ± 0.02 | **0.00 ± 0.00** | 1.00 ± 0.00 | 1.00 ± 0.00 | 0.00 ± 0.00 | 0.0 ± 0.0 | 0.03 ± 0.06 |
| 1 | 0.97 ± 0.05 | 0.97 ± 0.05 | **0.00 ± 0.00** | 0.91 ± 0.09 | 0.91 ± 0.09 | 0.00 ± 0.00 | 1.7 ± 2.4 | 0.01 ± 0.02 |
| 2 | 0.95 ± 0.05 | 0.95 ± 0.05 | **0.00 ± 0.00** | 0.91 ± 0.09 | 0.91 ± 0.09 | 0.00 ± 0.00 | 1.7 ± 2.4 | 0.03 ± 0.05 |
| 3 | 0.96 ± 0.04 | 0.96 ± 0.04 | **0.00 ± 0.00** | 0.84 ± 0.06 | 0.84 ± 0.06 | 0.00 ± 0.00 | 2.0 ± 2.0 | 0.05 ± 0.05 |
| 4 | 0.92 ± 0.09 | 0.92 ± 0.09 | **0.00 ± 0.00** | 0.89 ± 0.12 | 0.89 ± 0.12 | 0.00 ± 0.00 | 2.0 ± 2.0 | 0.04 ± 0.04 |
| 5 | 0.94 ± 0.06 | 0.94 ± 0.06 | **0.00 ± 0.00** | 0.92 ± 0.08 | 0.92 ± 0.08 | 0.00 ± 0.00 | 2.3 ± 1.7 | 0.04 ± 0.04 |

Post-hoc ANNECS: archive 2.3 ± 1.7, champion 2.3 ± 1.7. Post-hoc hardening touched: [(0, 29), (0, 21), (0, 26)] (minimality, tasks); tasks without a derivable guard: [5, 10, 1].
Improver valid rate 1.00 ± 0.00, children accepted per run [2, 1, 2], mean retest flips 0.40 ± 0.23, proposer acceptance 0.03 ± 0.03, adversary caught 0.18 ± 0.35.

## S2 verdict (RUNBOOK §6)

**bizops** (gen 5): B illusory 0.011 (>0.1 and not shrinking: **FAIL**), A illusory 0.000 (≈0: **PASS**), champion ANNECS post-hoc A 1.0 ± 1.1 vs B 0.2 ± 0.4

**tickets** (gen 5): B illusory 0.000 (>0.1 and not shrinking: **FAIL**), A illusory 0.000 (≈0: **PASS**), champion ANNECS post-hoc A 0.0 ± 0.0 vs B 0.0 ± 0.0

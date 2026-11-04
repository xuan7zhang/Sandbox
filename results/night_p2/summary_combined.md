# Results
## seed0  (condition: best)
| gen | champion | pass | incl.hacks | held-out | held-out g0 | retest flips | CMP | ANNECS | tasks | novel | hack% | diff | adv caught | hardened | accept% | LLM calls |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 0 | v0 | 0.90 | 0.90 | 0.83 | 0.83 | - | 0.90 | 0 | 10 | 1 | 0.00 | - | 0.00 | 31 | - | 78 |
| 1 | g1c1 | 0.86 | 0.86 | 0.67 | 0.83 | 0/10 | 0.86 | 1 | 14 | 2 | 0.00 | 3 | 0.00 | 11 | 0.16 | 376 |
| 2 | g1c1 | 0.84 | 0.84 | 0.55 | 0.83 | 0/14 | 0.55 | 1 | 17 | 1 | 0.00 | 3 | 0.00 | 7 | 0.12 | 638 |
| 3 | g1c1 | 0.82 | 0.82 | 0.55 | 0.83 | 0/17 | 0.63 | 1 | 18 | 1 | 0.00 | 3 | 0.00 | 1 | 0.02 | 1015 |
| 4 | g1c1 | 0.81 | 0.81 | 0.46 | 0.83 | 0/18 | 0.66 | 1 | 20 | 0 | 0.00 | 3 | 0.00 | 6 | 0.10 | 2074 |
| 5 | g1c1 | 0.80 | 0.80 | 0.47 | 0.83 | 0/20 | 0.68 | 1 | 22 | 1 | 0.02 | 3 | 0.00 | 6 | 0.08 | 2575 |

Re-judged ANNECS: archive-level 1, champion-level 1
Re-judge under current verifiers: 0 episodes re-scored, 0 passes flipped.

| gen | n | old pass | re-judged pass | verifier-attributed |
|---|---|---|---|---|
| 0 | 10 | 0.90 | 0.90 | +0.00 |
| 1 | 42 | 0.81 | 0.81 | +0.00 |
| 2 | 51 | 0.55 | 0.55 | +0.00 |
| 3 | 54 | 0.76 | 0.76 | +0.00 |
| 4 | 60 | 0.75 | 0.75 | +0.00 |
| 5 | 66 | 0.76 | 0.77 | -0.01 |

Held-out tasks re-judged:

| gen | n | old pass | re-judged pass | verifier-attributed |
|---|---|---|---|---|
| 0 | 6 | 0.83 | 0.83 | +0.00 |
| 1 | 9 | 0.67 | 0.67 | +0.00 |
| 2 | 2 | 0.00 | 0.00 | +0.00 |
| 4 | 2 | 0.00 | 0.00 | +0.00 |
| 5 | 2 | 0.50 | 0.50 | +0.00 |

## seed1  (condition: best)
| gen | champion | pass | incl.hacks | held-out | held-out g0 | retest flips | CMP | ANNECS | tasks | novel | hack% | diff | adv caught | hardened | accept% | LLM calls |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 0 | v0 | 0.73 | 0.73 | 0.57 | 0.57 | - | 0.73 | 0 | 11 | 3 | 0.00 | - | 0.00 | 25 | - | 80 |
| 1 | v0 | 0.74 | 0.74 | 0.73 | 0.57 | 0/11 | 0.64 | 0 | 16 | 1 | 0.00 | 2 | 0.00 | 15 | 0.30 | 284 |
| 2 | v0 | 0.74 | 0.74 | 0.79 | 0.57 | 0/16 | 0.53 | 0 | 20 | 1 | 0.00 | 2 | 0.00 | 14 | 0.17 | 596 |
| 3 | v0 | 0.75 | 0.75 | 0.82 | 0.57 | 0/20 | 0.55 | 0 | 24 | 1 | 0.00 | 2 | 0.00 | 13 | 0.21 | 948 |
| 4 | v0 | 0.74 | 0.74 | 0.84 | 0.57 | 1/24 | 0.56 | 0 | 27 | 0 | 0.00 | 2 | 0.00 | 10 | 0.10 | 1402 |
| 5 | v0 | 0.75 | 0.75 | 0.85 | 0.57 | 1/27 | 0.59 | 1 | 28 | 0 | 0.00 | 2 | 0.00 | 3 | 0.04 | 1926 |

Re-judged ANNECS: archive-level 1, champion-level 0
Re-judge under current verifiers: 0 episodes re-scored, 0 passes flipped.

| gen | n | old pass | re-judged pass | verifier-attributed |
|---|---|---|---|---|
| 0 | 11 | 0.73 | 0.73 | +0.00 |
| 1 | 48 | 0.65 | 0.65 | +0.00 |
| 2 | 60 | 0.48 | 0.48 | +0.00 |
| 3 | 72 | 0.67 | 0.67 | +0.00 |
| 4 | 81 | 0.63 | 0.63 | +0.00 |
| 5 | 84 | 0.74 | 0.74 | +0.00 |

Held-out tasks re-judged:

| gen | n | old pass | re-judged pass | verifier-attributed |
|---|---|---|---|---|
| 0 | 7 | 0.57 | 0.57 | +0.00 |
| 1 | 4 | 1.00 | 1.00 | +0.00 |
| 2 | 3 | 1.00 | 1.00 | +0.00 |
| 3 | 3 | 1.00 | 1.00 | +0.00 |
| 4 | 2 | 1.00 | 1.00 | +0.00 |
| 5 | 1 | 1.00 | 1.00 | +0.00 |

## seed2  (condition: best)
| gen | champion | pass | incl.hacks | held-out | held-out g0 | retest flips | CMP | ANNECS | tasks | novel | hack% | diff | adv caught | hardened | accept% | LLM calls |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 0 | v0 | 1.00 | 1.00 | 1.00 | 1.00 | - | 1.00 | 0 | 11 | 0 | 0.00 | - | 0.00 | 38 | - | 79 |
| 1 | g1c1 | 1.00 | 1.00 | 0.91 | 1.00 | 0/11 | 1.00 | 1 | 15 | 1 | 0.00 | 3 | 0.00 | 11 | 0.22 | 320 |
| 2 | g2c0 | 0.89 | 0.89 | 0.77 | 1.00 | 1/15 | 0.89 | 1 | 18 | 2 | 0.00 | 4 | 0.00 | 4 | 0.10 | 658 |
| 3 | g2c0 | 0.86 | 0.86 | 0.71 | 1.00 | 0/18 | 0.81 | 1 | 19 | 1 | 0.04 | 4 | 0.00 | 2 | 0.04 | 953 |
| 4 | g2c0 | 0.86 | 0.86 | 0.71 | 1.00 | 0/19 | 0.83 | 1 | 20 | 0 | 0.00 | 4 | 0.00 | 1 | 0.02 | 1244 |
| 5 | g5c1 | 0.90 | 0.90 | 0.71 | 1.00 | 0/20 | 0.90 | 2 | 20 | 0 | 0.00 | 4 | 0.00 | 0 | 0.00 | 1601 |

Re-judged ANNECS: archive-level 2, champion-level 2
Re-judge under current verifiers: 0 episodes re-scored, 0 passes flipped.

| gen | n | old pass | re-judged pass | verifier-attributed |
|---|---|---|---|---|
| 0 | 11 | 1.00 | 1.00 | +0.00 |
| 1 | 45 | 0.93 | 0.93 | +0.00 |
| 2 | 54 | 0.85 | 0.85 | +0.00 |
| 3 | 57 | 0.81 | 0.84 | -0.04 |
| 4 | 60 | 0.85 | 0.85 | +0.00 |
| 5 | 60 | 0.87 | 0.87 | +0.00 |

Held-out tasks re-judged:

| gen | n | old pass | re-judged pass | verifier-attributed |
|---|---|---|---|---|
| 0 | 8 | 1.00 | 1.00 | +0.00 |
| 1 | 11 | 0.91 | 0.91 | +0.00 |
| 2 | 13 | 0.77 | 0.77 | +0.00 |
| 3 | 1 | 0.00 | 0.00 | +0.00 |
| 5 | 14 | 0.71 | 0.71 | +0.00 |

## seed0  (condition: random:random-improver)
| gen | champion | pass | incl.hacks | held-out | held-out g0 | retest flips | CMP | ANNECS | tasks | novel | hack% | diff | adv caught | hardened | accept% | LLM calls |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 0 | v0 | 1.00 | 1.00 | 1.00 | 1.00 | - | 1.00 | 0 | 11 | 0 | 0.00 | - | 0.00 | 32 | - | 70 |
| 1 | v0 | 1.00 | 1.00 | 1.00 | 1.00 | 0/11 | 0.79 | 0 | 16 | 0 | 0.00 | 3 | 0.00 | 13 | 0.23 | 330 |
| 2 | v0 | 1.00 | 1.00 | 1.00 | 1.00 | 0/16 | 0.88 | 0 | 16 | 0 | 0.00 | 4 | 0.00 | 0 | 0.00 | 553 |
| 3 | v0 | 1.00 | 1.00 | 1.00 | 1.00 | 0/16 | 0.89 | 0 | 16 | 0 | 0.00 | 4 | 0.00 | 0 | 0.00 | 963 |
| 4 | v0 | 1.00 | 1.00 | 1.00 | 1.00 | 0/16 | 0.81 | 0 | 17 | 0 | 0.00 | 4 | 0.00 | 4 | 0.04 | 1154 |
| 5 | v0 | 1.00 | 1.00 | 1.00 | 1.00 | 0/17 | 0.84 | 0 | 17 | 0 | 0.00 | 5 | 0.00 | 0 | 0.00 | 1520 |

Re-judged ANNECS: archive-level 0, champion-level 0
Re-judge under current verifiers: 0 episodes re-scored, 0 passes flipped.

| gen | n | old pass | re-judged pass | verifier-attributed |
|---|---|---|---|---|
| 0 | 11 | 1.00 | 1.00 | +0.00 |
| 1 | 48 | 0.79 | 0.79 | +0.00 |
| 2 | 48 | 1.00 | 1.00 | +0.00 |
| 3 | 48 | 0.96 | 0.96 | +0.00 |
| 4 | 51 | 0.67 | 0.67 | +0.00 |
| 5 | 51 | 1.00 | 1.00 | +0.00 |

Held-out tasks re-judged:

| gen | n | old pass | re-judged pass | verifier-attributed |
|---|---|---|---|---|
| 0 | 7 | 1.00 | 1.00 | +0.00 |
| 1 | 3 | 1.00 | 1.00 | +0.00 |
| 4 | 1 | 1.00 | 1.00 | +0.00 |

## seed1  (condition: random:random-improver)
| gen | champion | pass | incl.hacks | held-out | held-out g0 | retest flips | CMP | ANNECS | tasks | novel | hack% | diff | adv caught | hardened | accept% | LLM calls |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 0 | v0 | 1.00 | 1.00 | 1.00 | 1.00 | - | 1.00 | 0 | 12 | 0 | 0.00 | - | 0.00 | 40 | - | 74 |
| 1 | g1c1 | 1.00 | 1.00 | 1.00 | 1.00 | 0/12 | 1.00 | 1 | 16 | 1 | 0.00 | 3 | 0.00 | 13 | 0.16 | 452 |
| 2 | g1c1 | 1.00 | 1.00 | 1.00 | 1.00 | 0/16 | 1.00 | 1 | 17 | 0 | 0.00 | 4 | 0.00 | 3 | 0.04 | 859 |
| 3 | g1c1 | 1.00 | 1.00 | 1.00 | 1.00 | 0/17 | 1.00 | 1 | 17 | 0 | 0.00 | 5 | 0.00 | 0 | 0.00 | 1245 |
| 4 | g1c1 | 1.00 | 1.00 | 1.00 | 1.00 | 0/17 | 1.00 | 1 | 17 | 0 | 0.00 | 5 | 0.00 | 0 | 0.00 | 1684 |
| 5 | g1c1 | 1.00 | 1.00 | 1.00 | 1.00 | 0/17 | 1.00 | 1 | 17 | 0 | 0.00 | 5 | 0.00 | 0 | 0.00 | 1932 |

Re-judged ANNECS: archive-level 1, champion-level 1
Re-judge under current verifiers: 0 episodes re-scored, 0 passes flipped.

| gen | n | old pass | re-judged pass | verifier-attributed |
|---|---|---|---|---|
| 0 | 12 | 1.00 | 1.00 | +0.00 |
| 1 | 48 | 0.96 | 0.96 | +0.00 |
| 2 | 68 | 0.98 | 0.98 | +0.00 |
| 3 | 51 | 1.00 | 1.00 | +0.00 |
| 4 | 68 | 0.98 | 0.98 | +0.00 |
| 5 | 51 | 0.92 | 0.92 | +0.00 |

Held-out tasks re-judged:

| gen | n | old pass | re-judged pass | verifier-attributed |
|---|---|---|---|---|
| 0 | 8 | 1.00 | 1.00 | +0.00 |
| 1 | 11 | 1.00 | 1.00 | +0.00 |
| 2 | 1 | 1.00 | 1.00 | +0.00 |

## seed2  (condition: random:random-improver)
| gen | champion | pass | incl.hacks | held-out | held-out g0 | retest flips | CMP | ANNECS | tasks | novel | hack% | diff | adv caught | hardened | accept% | LLM calls |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 0 | v0 | 0.92 | 1.00 | 1.00 | 1.00 | - | 0.92 | 0 | 12 | 1 | 0.08 | - | 0.00 | 35 | - | 88 |
| 1 | v0 | 0.97 | 1.00 | 1.00 | 1.00 | 1/12 | 0.85 | 1 | 17 | 0 | 0.02 | 3 | 0.00 | 17 | 0.25 | 638 |
| 2 | v0 | 0.98 | 1.00 | 1.00 | 1.00 | 0/17 | 0.90 | 1 | 18 | 0 | 0.00 | 4 | 0.00 | 2 | 0.02 | 939 |
| 3 | v0 | 0.97 | 1.00 | 1.00 | 1.00 | 1/18 | 0.89 | 1 | 18 | 0 | 0.02 | 5 | 0.00 | 0 | 0.00 | 1453 |
| 4 | v0 | 0.98 | 1.00 | 1.00 | 1.00 | 1/18 | 0.90 | 1 | 19 | 0 | 0.00 | 5 | 0.00 | 3 | 0.03 | 1870 |
| 5 | v0 | 0.98 | 1.00 | 1.00 | 1.00 | 0/19 | 0.91 | 1 | 19 | 0 | 0.00 | 5 | 0.00 | 0 | 0.00 | 2252 |

Re-judged ANNECS: archive-level 1, champion-level 1
Re-judge under current verifiers: 0 episodes re-scored, 0 passes flipped.

| gen | n | old pass | re-judged pass | verifier-attributed |
|---|---|---|---|---|
| 0 | 12 | 0.92 | 1.00 | -0.08 |
| 1 | 51 | 0.86 | 0.88 | -0.02 |
| 2 | 54 | 0.98 | 0.98 | +0.00 |
| 3 | 54 | 0.89 | 0.91 | -0.02 |
| 4 | 57 | 0.96 | 0.96 | +0.00 |
| 5 | 57 | 0.95 | 0.95 | +0.00 |

Held-out tasks re-judged:

| gen | n | old pass | re-judged pass | verifier-attributed |
|---|---|---|---|---|
| 0 | 8 | 1.00 | 1.00 | +0.00 |
| 1 | 4 | 1.00 | 1.00 | +0.00 |
| 4 | 1 | 1.00 | 1.00 | +0.00 |

## seed0  (condition: best)
| gen | champion | pass | incl.hacks | held-out | held-out g0 | retest flips | CMP | ANNECS | tasks | novel | hack% | diff | adv caught | hardened | accept% | LLM calls |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 0 | v0 | 0.82 | 0.82 | 1.00 | 1.00 | - | 0.82 | 0 | 11 | 2 | 0.00 | - | - | - | - | 69 |
| 1 | g1c0 | 1.00 | 1.00 | 0.90 | 1.00 | 0/11 | 1.00 | 2 | 15 | 0 | 0.00 | 3 | - | - | 0.16 | 294 |
| 2 | g1c0 | 0.97 | 0.97 | 0.91 | 1.00 | 0/15 | 0.89 | 2 | 16 | 1 | 0.00 | 4 | - | - | 0.04 | 541 |
| 3 | g1c0 | 0.94 | 0.94 | 0.83 | 1.00 | 0/16 | 0.87 | 2 | 17 | 1 | 0.00 | 4 | - | - | 0.04 | 765 |
| 4 | g1c0 | 0.91 | 0.91 | 0.83 | 1.00 | 0/17 | 0.82 | 2 | 18 | 1 | 0.00 | 4 | - | - | 0.02 | 1018 |
| 5 | g1c0 | 0.88 | 0.88 | 0.77 | 1.00 | 0/18 | 0.81 | 2 | 19 | 1 | 0.00 | 4 | - | - | 0.04 | 1330 |

Re-judged ANNECS: archive-level 2, champion-level 2
Re-judge under current verifiers: 0 episodes re-scored, 0 passes flipped.

| gen | n | old pass | re-judged pass | verifier-attributed |
|---|---|---|---|---|
| 0 | 11 | 0.82 | 0.82 | +0.00 |
| 1 | 45 | 0.91 | 0.91 | +0.00 |
| 2 | 48 | 0.88 | 0.88 | +0.00 |
| 3 | 51 | 0.86 | 0.86 | +0.00 |
| 4 | 54 | 0.76 | 0.76 | +0.00 |
| 5 | 57 | 0.79 | 0.79 | +0.00 |

Held-out tasks re-judged:

| gen | n | old pass | re-judged pass | verifier-attributed |
|---|---|---|---|---|
| 0 | 8 | 1.00 | 1.00 | +0.00 |
| 1 | 10 | 0.90 | 0.90 | +0.00 |
| 2 | 1 | 1.00 | 1.00 | +0.00 |
| 3 | 1 | 0.00 | 0.00 | +0.00 |
| 5 | 1 | 0.00 | 0.00 | +0.00 |

## seed1  (condition: best)
| gen | champion | pass | incl.hacks | held-out | held-out g0 | retest flips | CMP | ANNECS | tasks | novel | hack% | diff | adv caught | hardened | accept% | LLM calls |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 0 | v0 | 0.62 | 1.00 | 0.33 | 0.33 | - | 0.62 | 0 | 8 | 3 | 0.38 | - | - | - | - | 114 |
| 1 | v0 | 0.55 | 0.95 | 0.33 | 0.33 | 1/8 | 0.53 | 2 | 12 | 4 | 0.46 | 2 | - | - | 0.15 | 317 |
| 2 | v0 | 0.53 | 0.91 | 0.30 | 0.33 | 1/12 | 0.49 | 2 | 14 | 2 | 0.44 | 2 | - | - | 0.07 | 680 |
| 3 | v0 | 0.54 | 0.92 | 0.25 | 0.33 | 0/14 | 0.43 | 3 | 16 | 0 | 0.39 | 2 | - | - | 0.10 | 1147 |
| 4 | g4c0 | 0.61 | 0.89 | 0.36 | 0.33 | 1/16 | 0.61 | 3 | 18 | 1 | 0.39 | 2 | - | - | 0.09 | 1809 |
| 5 | g5c0 | 0.65 | 0.75 | 0.56 | 0.33 | 1/18 | 0.65 | 8 | 20 | 2 | 0.25 | 2 | - | - | 0.09 | 2522 |

Re-judged ANNECS: archive-level 10, champion-level 10
Re-judge under current verifiers: 0 episodes re-scored, 0 passes flipped.

| gen | n | old pass | re-judged pass | verifier-attributed |
|---|---|---|---|---|
| 0 | 8 | 0.62 | 1.00 | -0.38 |
| 1 | 24 | 0.50 | 0.92 | -0.42 |
| 2 | 42 | 0.48 | 0.86 | -0.38 |
| 3 | 48 | 0.40 | 0.65 | -0.25 |
| 4 | 54 | 0.52 | 0.85 | -0.33 |
| 5 | 60 | 0.60 | 0.80 | -0.20 |

Held-out tasks re-judged:

| gen | n | old pass | re-judged pass | verifier-attributed |
|---|---|---|---|---|
| 0 | 6 | 0.33 | 0.83 | -0.50 |
| 1 | 3 | 0.33 | 0.67 | -0.33 |
| 2 | 1 | 0.00 | 1.00 | -1.00 |
| 3 | 2 | 0.00 | 1.00 | -1.00 |
| 4 | 14 | 0.36 | 0.86 | -0.50 |
| 5 | 16 | 0.56 | 0.81 | -0.25 |

## seed2  (condition: best)
| gen | champion | pass | incl.hacks | held-out | held-out g0 | retest flips | CMP | ANNECS | tasks | novel | hack% | diff | adv caught | hardened | accept% | LLM calls |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 0 | v0 | 1.00 | 1.00 | 0.86 | 0.86 | - | 1.00 | 0 | 11 | 0 | 0.00 | - | - | - | - | 75 |
| 1 | v0 | 1.00 | 1.00 | 0.75 | 0.86 | 0/11 | 1.00 | 0 | 13 | 0 | 0.00 | 3 | - | - | 0.07 | 329 |
| 2 | g2c0 | 1.00 | 1.00 | 0.75 | 0.86 | 0/13 | 1.00 | 1 | 14 | 1 | 0.00 | 4 | - | - | 0.02 | 564 |
| 3 | g2c0 | 0.96 | 0.96 | 0.75 | 0.86 | 1/14 | 0.92 | 1 | 14 | 0 | 0.03 | 5 | - | - | 0.00 | 764 |
| 4 | g2c0 | 0.93 | 0.93 | 0.70 | 0.86 | 0/14 | 0.88 | 1 | 17 | 1 | 0.00 | 4 | - | - | 0.11 | 1067 |
| 5 | g2c0 | 0.94 | 0.94 | 0.75 | 0.86 | 1/17 | 0.89 | 1 | 20 | 0 | 0.00 | 4 | - | - | 0.10 | 1396 |

Re-judged ANNECS: archive-level 1, champion-level 1
Re-judge under current verifiers: 0 episodes re-scored, 0 passes flipped.

| gen | n | old pass | re-judged pass | verifier-attributed |
|---|---|---|---|---|
| 0 | 11 | 1.00 | 1.00 | +0.00 |
| 1 | 39 | 1.00 | 1.00 | +0.00 |
| 2 | 42 | 0.95 | 0.95 | +0.00 |
| 3 | 42 | 0.91 | 0.93 | -0.02 |
| 4 | 51 | 0.86 | 0.86 | +0.00 |
| 5 | 60 | 0.92 | 0.92 | +0.00 |

Held-out tasks re-judged:

| gen | n | old pass | re-judged pass | verifier-attributed |
|---|---|---|---|---|
| 0 | 7 | 0.86 | 0.86 | +0.00 |
| 1 | 1 | 0.00 | 0.00 | +0.00 |
| 2 | 8 | 0.75 | 0.75 | +0.00 |
| 4 | 2 | 0.50 | 0.50 | +0.00 |
| 5 | 2 | 1.00 | 1.00 | +0.00 |

## seed0  (condition: random:random-improver)
| gen | champion | pass | incl.hacks | held-out | held-out g0 | retest flips | CMP | ANNECS | tasks | novel | hack% | diff | adv caught | hardened | accept% | LLM calls |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 0 | v0 | 1.00 | 1.00 | 0.88 | 0.88 | - | 1.00 | 0 | 12 | 0 | 0.00 | - | - | - | - | 70 |
| 1 | g1c0 | 1.00 | 1.00 | 0.83 | 1.00 | 1/12 | 1.00 | 0 | 17 | 0 | 0.00 | 3 | - | - | 0.27 | 505 |
| 2 | g1c0 | 0.97 | 0.97 | 0.86 | 1.00 | 1/17 | 0.86 | 0 | 20 | 0 | 0.02 | 4 | - | - | 0.12 | 1582 |
| 3 | g1c0 | 0.97 | 0.97 | 0.87 | 1.00 | 1/17 | 0.86 | 0 | 21 | 0 | 0.00 | 5 | - | - | 0.04 | 1877 |
| 4 | g1c0 | 0.98 | 0.98 | 0.87 | 1.00 | 1/21 | 0.82 | 0 | 22 | 0 | 0.00 | 5 | - | - | 0.02 | 2568 |
| 5 | g1c0 | 0.99 | 0.99 | 0.88 | 1.00 | 0/22 | 0.87 | 0 | 23 | 0 | 0.00 | 5 | - | - | 0.04 | 3359 |

Re-judged ANNECS: archive-level 0, champion-level 0
Re-judge under current verifiers: 0 episodes re-scored, 0 passes flipped.

| gen | n | old pass | re-judged pass | verifier-attributed |
|---|---|---|---|---|
| 0 | 12 | 1.00 | 1.00 | +0.00 |
| 1 | 51 | 0.96 | 0.96 | +0.00 |
| 2 | 60 | 0.85 | 0.87 | -0.02 |
| 3 | 43 | 0.95 | 0.95 | +0.00 |
| 4 | 66 | 0.83 | 0.83 | +0.00 |
| 5 | 69 | 1.00 | 1.00 | +0.00 |

Held-out tasks re-judged:

| gen | n | old pass | re-judged pass | verifier-attributed |
|---|---|---|---|---|
| 0 | 8 | 0.88 | 0.88 | +0.00 |
| 1 | 12 | 0.83 | 0.83 | +0.00 |
| 2 | 2 | 1.00 | 1.00 | +0.00 |
| 3 | 1 | 1.00 | 1.00 | +0.00 |
| 5 | 1 | 1.00 | 1.00 | +0.00 |

## seed1  (condition: random:random-improver)
| gen | champion | pass | incl.hacks | held-out | held-out g0 | retest flips | CMP | ANNECS | tasks | novel | hack% | diff | adv caught | hardened | accept% | LLM calls |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 0 | v0 | 1.00 | 1.00 | 0.75 | 0.75 | - | 1.00 | 0 | 12 | 0 | 0.00 | - | - | - | - | 72 |
| 1 | v0 | 1.00 | 1.00 | 0.82 | 0.75 | 0/12 | 0.85 | 0 | 16 | 0 | 0.00 | 3 | - | - | 0.21 | 348 |
| 2 | v0 | 1.00 | 1.00 | 0.86 | 0.75 | 0/16 | 0.86 | 0 | 20 | 0 | 0.00 | 4 | - | - | 0.15 | 851 |
| 3 | v0 | 1.00 | 1.00 | 0.88 | 0.75 | 0/20 | 0.90 | 0 | 22 | 0 | 0.00 | 5 | - | - | 0.11 | 1421 |
| 4 | v0 | 0.99 | 0.99 | 0.83 | 0.75 | 0/22 | 0.91 | 0 | 25 | 1 | 0.00 | 5 | - | - | 0.10 | 2117 |
| 5 | v0 | 0.98 | 0.98 | 0.79 | 0.75 | 0/25 | 0.91 | 0 | 26 | 0 | 0.00 | 5 | - | - | 0.04 | 2924 |

Re-judged ANNECS: archive-level 0, champion-level 0
Re-judge under current verifiers: 0 episodes re-scored, 0 passes flipped.

| gen | n | old pass | re-judged pass | verifier-attributed |
|---|---|---|---|---|
| 0 | 12 | 1.00 | 1.00 | +0.00 |
| 1 | 48 | 0.85 | 0.85 | +0.00 |
| 2 | 60 | 0.92 | 0.92 | +0.00 |
| 3 | 66 | 1.00 | 1.00 | +0.00 |
| 4 | 75 | 0.95 | 0.95 | +0.00 |
| 5 | 78 | 0.95 | 0.95 | +0.00 |

Held-out tasks re-judged:

| gen | n | old pass | re-judged pass | verifier-attributed |
|---|---|---|---|---|
| 0 | 8 | 0.75 | 0.75 | +0.00 |
| 1 | 3 | 1.00 | 1.00 | +0.00 |
| 2 | 3 | 1.00 | 1.00 | +0.00 |
| 3 | 2 | 1.00 | 1.00 | +0.00 |
| 4 | 2 | 0.50 | 0.50 | +0.00 |
| 5 | 1 | 0.00 | 0.00 | +0.00 |

## seed2  (condition: random:random-improver)
| gen | champion | pass | incl.hacks | held-out | held-out g0 | retest flips | CMP | ANNECS | tasks | novel | hack% | diff | adv caught | hardened | accept% | LLM calls |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 0 | v0 | 1.00 | 1.00 | 1.00 | 1.00 | - | 1.00 | 0 | 10 | 0 | 0.00 | - | - | - | - | 63 |
| 1 | v0 | 1.00 | 1.00 | 1.00 | 1.00 | 0/10 | 1.00 | 0 | 12 | 0 | 0.00 | 3 | - | - | 0.08 | 282 |
| 2 | v0 | 1.00 | 1.00 | 1.00 | 1.00 | 0/12 | 0.98 | 0 | 13 | 0 | 0.00 | 4 | - | - | 0.04 | 526 |
| 3 | v0 | 1.00 | 1.00 | 1.00 | 1.00 | 0/13 | 0.95 | 0 | 13 | 0 | 0.00 | 5 | - | - | 0.00 | 861 |
| 4 | v0 | 1.00 | 1.00 | 1.00 | 1.00 | 0/13 | 0.89 | 0 | 13 | 0 | 0.00 | 5 | - | - | 0.00 | 1075 |
| 5 | v0 | 1.00 | 1.00 | 1.00 | 1.00 | 0/13 | 0.90 | 0 | 14 | 0 | 0.00 | 5 | - | - | 0.02 | 1378 |

Re-judged ANNECS: archive-level 0, champion-level 0
Re-judge under current verifiers: 0 episodes re-scored, 0 passes flipped.

| gen | n | old pass | re-judged pass | verifier-attributed |
|---|---|---|---|---|
| 0 | 10 | 1.00 | 1.00 | +0.00 |
| 1 | 36 | 1.00 | 1.00 | +0.00 |
| 2 | 39 | 0.97 | 0.97 | +0.00 |
| 3 | 39 | 0.90 | 0.90 | +0.00 |
| 4 | 39 | 0.80 | 0.80 | +0.00 |
| 5 | 42 | 0.95 | 0.95 | +0.00 |

Held-out tasks re-judged:

| gen | n | old pass | re-judged pass | verifier-attributed |
|---|---|---|---|---|
| 0 | 7 | 1.00 | 1.00 | +0.00 |
| 1 | 2 | 1.00 | 1.00 | +0.00 |
| 2 | 1 | 1.00 | 1.00 | +0.00 |

## Final-generation aggregate (mean ± 95% CI over runs)

| condition | runs | pass | held-out | ANNECS | hack% | LLM calls |
|---|---|---|---|---|---|---|
| best | 6 | 0.82 ± 0.09 | 0.69 ± 0.11 | 2.50 ± 2.19 | 0.05 ± 0.08 | 1892 ± 440 |
| random:random-improver | 6 | 0.99 ± 0.01 | 0.94 ± 0.07 | 0.33 ± 0.41 | 0.00 ± 0.00 | 2228 ± 628 |

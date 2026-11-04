# Idea 2 — final champions re-evaluated on the test set

35 test tasks x 3 reps per agent, same stack as the loop (rule-based + LLM judge). v0 = 0.600 (reps [0.571, 0.629, 0.6]).

| run : champion | reps | mean | − v0 |
|---|---|---|---|
| S_best/seed0:g3c0 | [0.6, 0.571, 0.486] | 0.552 | -0.048 |
| S_best/seed1:g7c0 | [0.571, 0.571, 0.543] | 0.562 | -0.038 |
| S_best/seed2:g7c1 | [0.571, 0.543, 0.543] | 0.552 | -0.048 |
| S_best/seed3:g6c0 | [0.6, 0.6, 0.571] | 0.590 | -0.010 |
| S_best/seed4:g8c0 | [0.6, 0.571, 0.543] | 0.571 | -0.029 |
| S_cmp/seed0:g4c1 | [0.6, 0.571, 0.571] | 0.581 | -0.019 |
| S_cmp/seed1:g8c0 | [0.629, 0.629, 0.629] | 0.629 | +0.029 |
| S_cmp/seed2:g6c1 | [0.543, 0.571, 0.543] | 0.552 | -0.048 |
| S_cmp/seed3:g7c0 | [0.6, 0.629, 0.657] | 0.629 | +0.029 |
| S_cmp/seed4:g8c1 | [0.629, 0.6, 0.571] | 0.600 | +0.000 |
| S_random/seed0:g6c1 | [0.714, 0.771, 0.657] | 0.714 | +0.114 |
| S_random/seed1:g8c0 | [0.6, 0.6, 0.6] | 0.600 | +0.000 |
| S_random/seed2:g7c0 | [0.686, 0.686, 0.6] | 0.657 | +0.057 |
| S_random/seed3:g7c0 | [0.771, 0.686, 0.629] | 0.695 | +0.095 |
| S_random/seed4:g8c0 | [0.6, 0.6, 0.514] | 0.571 | -0.029 |
| S_best_nodiag/seed0:g3c1 | [0.686, 0.657, 0.686] | 0.676 | +0.076 |
| S_best_nodiag/seed1:g8c0 | [0.657, 0.657, 0.686] | 0.667 | +0.067 |
| S_best_nodiag/seed2:g3c0 | [0.629, 0.629, 0.6] | 0.619 | +0.019 |
| S_best_nodiag/seed3:g8c0 | [0.771, 0.657, 0.714] | 0.714 | +0.114 |
| S_best_nodiag/seed4:g8c0 | [0.6, 0.657, 0.686] | 0.648 | +0.048 |
| S_best_m3/seed0:g4c0 | [0.571, 0.629, 0.6] | 0.600 | +0.000 |
| S_best_m3/seed1:g1c0 | [0.657, 0.657, 0.629] | 0.648 | +0.048 |
| S_best_m3/seed2:g3c0 | [0.6, 0.6, 0.571] | 0.590 | -0.010 |
| S_best_nodiag_m3/seed0:g5c0 | [0.714, 0.686, 0.743] | 0.714 | +0.114 |
| S_best_nodiag_m3/seed1:g6c0 | [0.686, 0.714, 0.743] | 0.714 | +0.114 |
| S_best_nodiag_m3/seed2:g2c1 | [0.686, 0.686, 0.714] | 0.695 | +0.095 |
| S_cmp_m3/seed0:g1c0 | [0.571, 0.629, 0.571] | 0.590 | -0.010 |
| S_cmp_m3/seed1:g3c0 | [0.6, 0.543, 0.571] | 0.571 | -0.029 |
| S_cmp_m3/seed2:g1c1 | [0.6, 0.6, 0.6] | 0.600 | +0.000 |
| S_random_m3/seed0:g7c0 | [0.714, 0.771, 0.714] | 0.733 | +0.133 |
| S_random_m3/seed1:g1c0 | [0.629, 0.657, 0.657] | 0.648 | +0.048 |
| S_random_m3/seed2:g2c1 | [0.571, 0.657, 0.657] | 0.629 | +0.029 |
| v0 | [0.571, 0.629, 0.6] | 0.600 | +0.000 |

| condition | runs | mean test (95% CI) | − v0 |
|---|---|---|---|
| S_best | 5 | 0.565 ± 0.020 | -0.035 |
| S_cmp | 5 | 0.598 ± 0.041 | -0.002 |
| S_random | 5 | 0.647 ± 0.076 | +0.047 |
| S_best_nodiag | 5 | 0.665 ± 0.044 | +0.065 |
| S_best_m3 | 3 | 0.613 ± 0.077 | +0.013 |
| S_best_nodiag_m3 | 3 | 0.708 ± 0.027 | +0.108 |
| S_cmp_m3 | 3 | 0.587 ± 0.037 | -0.013 |
| S_random_m3 | 3 | 0.670 ± 0.138 | +0.070 |

Welch t-tests on per-run means (diag = best, cmp; diag-free = random, best_nodiag):

- [accept_margin 1] best - best_nodiag: -0.099 (p=0.0015)
- [accept_margin 1] best - random: -0.082 (p=0.0375)
- [accept_margin 1] cmp - best: +0.033 (p=0.0934)
- [accept_margin 1] (best+cmp) - (random+nodiag): -0.074 (p=0.0008)
- [accept_margin 3] best - best_nodiag: -0.095 (p=0.0236)
- [accept_margin 3] best - random: -0.057 (p=0.2116)
- [accept_margin 3] cmp - best: -0.026 (p=0.29)
- [accept_margin 3] (best+cmp) - (random+nodiag): -0.089 (p=0.0018)

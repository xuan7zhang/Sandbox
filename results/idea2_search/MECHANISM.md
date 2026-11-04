# Idea 2 — mechanism: what the improver changes, with and without diagnostics

| condition | runs | children | rationale names false_claim | rationale: re-read task / side effects | children with ≥3 copied train literals | champion agent.py lines | over-action train | over-action test | test pass by difficulty |
|---|---|---|---|---|---|---|---|---|---|
| v0 | 1 | — | — | — | — | [58] | 5.6% (4/72) | 8.6% (3/35) | d2:0.80, d3:0.62, d4:0.29, d5:0.40 |
| S_best | 5 | 80 | 90% | 42% | 26% | [114, 253, 256, 203, 393] | 5.4% (27/504) | 8.6% (15/175) | d2:0.77, d3:0.47, d4:0.29, d5:0.44 |
| S_best_m3 | 3 | 48 | 98% | 54% | 2% | [199, 89, 89] | 5.0% (34/684) | 8.6% (9/105) | d2:0.80, d3:0.50, d4:0.38, d5:0.47 |
| S_best_nodiag | 5 | 79 | 0% | 71% | 0% | [110, 88, 105, 129, 97] | 0.6% (3/540) | 0.6% (1/175) | d2:0.84, d3:0.40, d4:0.89, d5:0.40 |
| S_best_nodiag_m3 | 3 | 48 | 0% | 85% | 0% | [97, 96, 79] | 0.6% (3/504) | 2.9% (3/105) | d2:0.87, d3:0.42, d4:0.81, d5:0.47 |
| S_cmp | 5 | 80 | 96% | 42% | 24% | [250, 263, 128, 232, 417] | 4.9% (21/432) | 6.9% (12/175) | d2:0.81, d3:0.47, d4:0.43, d5:0.40 |
| S_cmp_m3 | 3 | 48 | 100% | 71% | 19% | [109, 89, 101] | 5.6% (36/648) | 8.6% (9/105) | d2:0.80, d3:0.50, d4:0.29, d5:0.47 |
| S_random | 5 | 79 | 0% | 82% | 0% | [82, 141, 92, 142, 102] | 1.7% (5/288) | 3.4% (6/175) | d2:0.79, d3:0.50, d4:0.71, d5:0.32 |
| S_random_m3 | 3 | 48 | 0% | 65% | 0% | [117, 86, 88] | 4.9% (14/288) | 7.6% (8/105) | d2:0.84, d3:0.50, d4:0.52, d5:0.40 |

over-action = champion sets an order to 'shipped' although the task's reference never ships it (v0 misreads 'confirm the order, which will ship on day N' as a request to ship; shipping decrements stock and trips the scope guard).

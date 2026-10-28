"""rsi-sandbox: a long-horizon self-improvement sandbox.

Layers (see README):
  world     - synthetic stateful tool worlds (the thing the agent acts on)
  solver    - the self-modifiable agent scaffold, run in an isolated subprocess
  proposer  - LLM task generation with hidden verifiers + filters
  verifier  - pluggable verification stack + adversarial exploit agent
  archive   - generations, lineage, rollback, metaproductivity
  metrics   - ANNECS, hacking rate, matched-budget baselines
  loop      - one-generation orchestrator
"""

__version__ = "0.1.0"

#!/usr/bin/env bash
# S1 (RUNBOOK.md §6) on Killarney: a vLLM server for Qwen3-30B-A3B-Instruct-2507 on 2x L40S (TP=2), then
#   1. verifier loophole census on BizOps and on Tickets (proposer only, scripted exploits)
#   2. a 1-generation smoke loop (solver tool calling, improver, held-out tasks) + its report
# Finite job: the server is stopped when the last step returns. Submit from the repo root:
#   mkdir -p runs/slurm && sbatch scripts/slurm_s1.sh
#SBATCH --account=aip-xli135
#SBATCH -J rsi_s1
#SBATCH --gres=gpu:l40s:2
#SBATCH --cpus-per-task=16
#SBATCH --mem=128G
#SBATCH --time=10:00:00
#SBATCH --exclude=kn117
#SBATCH --output=/project/6101776/xzhan576/rsi-sandbox/runs/slurm/%x.%j.out
set -u
P=/project/6101776/xzhan576/rsi-sandbox
VENV_VLLM=/home/xzhan576/projects/aip-xli135/xzhan576/OPSD/.venv  # vllm 0.11.0
MODEL_DIR=/datasets/omni_pretraining/gta2/models/Qwen3-30B-A3B-Instruct-2507
NAME=Qwen/Qwen3-30B-A3B-Instruct-2507
PORT=$((20000 + SLURM_JOB_ID % 20000))  # nodes are shared: avoid other users' :8000
cd $P
echo "[job] $SLURM_JOB_ID on $(hostname) port=$PORT $(date)"
nvidia-smi --query-gpu=name,memory.used,memory.total --format=csv,noheader
export HF_HUB_OFFLINE=1 OPENAI_API_KEY=EMPTY no_proxy=localhost,127.0.0.1 NO_PROXY=localhost,127.0.0.1

VLOG=runs/slurm/vllm.$SLURM_JOB_ID.log
( module load cuda/12.6 2>/dev/null; source $VENV_VLLM/bin/activate
  exec python -m vllm.entrypoints.openai.api_server --model $MODEL_DIR --served-model-name $NAME \
    --tensor-parallel-size 2 --max-model-len 32768 --gpu-memory-utilization 0.90 \
    --enable-auto-tool-choice --tool-call-parser hermes --host 127.0.0.1 --port $PORT ) > $VLOG 2>&1 &
VPID=$!
trap 'kill $VPID 2>/dev/null; wait $VPID 2>/dev/null' EXIT
for i in $(seq 1 120); do
  curl -sf http://127.0.0.1:$PORT/v1/models > /dev/null && break
  kill -0 $VPID 2>/dev/null || { echo "[vllm] exited during startup"; tail -60 $VLOG; exit 1; }
  sleep 10
done
curl -sf http://127.0.0.1:$PORT/v1/models || { echo "[vllm] not ready after 20 min"; tail -60 $VLOG; exit 1; }
echo; echo "[vllm] ready $(date)"

# per-job copy of the config pointing at this job's port
CFG=runs/slurm/vllm_local.$SLURM_JOB_ID.yaml
sed "s#http://localhost:8000/v1#http://127.0.0.1:$PORT/v1#g" configs/vllm_local.yaml > $CFG
grep -q "127.0.0.1:$PORT" $CFG || { echo "[cfg] port substitution failed"; exit 1; }

PY=$P/.venv/bin/python
rc=0
step() { echo "[step] $* $(date +%H:%M:%S)"; "$@" < /dev/null || { echo "[step FAILED rc=$?] $*"; rc=1; }; }
step $PY scripts/audit_verifiers.py $CFG --n 100 --out runs/audit_vllm
step $PY scripts/audit_verifiers.py $CFG --n 100 --world tickets --out runs/audit_vllm_tickets
step $PY scripts/run_loop.py $CFG --generations 1 --run-dir runs/smoke_vllm
[ -s runs/smoke_vllm/generations.jsonl ] && step $PY scripts/report.py runs/smoke_vllm
echo "[job] finished rc=$rc $(date)"
exit $rc

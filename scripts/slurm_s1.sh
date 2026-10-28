#!/usr/bin/env bash
# S1 (RUNBOOK.md §6) on Killarney: a vLLM server for Qwen3-30B-A3B-Instruct-2507 on 2x L40S (TP=2), then
#   1. verifier loophole census on BizOps and on Tickets (proposer only, scripted exploits)
#   2. a 1-generation smoke loop (solver tool calling, improver, held-out tasks) + its report
# Finite job: the server is stopped when the last step returns. Outputs go to /scratch (the aip-xli135
# /project quota is ~97% full and SQLite there has failed with "disk I/O error"). Submit from the repo root:
#   mkdir -p /scratch/xzhan576/rsi-sandbox-runs/slurm && sbatch scripts/slurm_s1.sh
#SBATCH --account=aip-xli135
#SBATCH -J rsi_s1
#SBATCH --gres=gpu:l40s:2
#SBATCH --cpus-per-task=16
#SBATCH --mem=128G
#SBATCH --time=10:00:00
#SBATCH --exclude=kn117
#SBATCH --output=/scratch/xzhan576/rsi-sandbox-runs/slurm/%x.%j.out
set -u
P=/project/6101776/xzhan576/rsi-sandbox
VENV_VLLM=/home/xzhan576/projects/aip-xli135/xzhan576/OPSD/.venv  # vllm 0.11.0
MODEL_DIR=/datasets/omni_pretraining/gta2/models/Qwen3-30B-A3B-Instruct-2507
NAME=Qwen/Qwen3-30B-A3B-Instruct-2507
PORT=$((20000 + SLURM_JOB_ID % 20000))  # nodes are shared: avoid other users' :8000
R=/scratch/xzhan576/rsi-sandbox-runs
mkdir -p $R/slurm
cd $P
echo "[job] $SLURM_JOB_ID on $(hostname) port=$PORT $(date)"
nvidia-smi --query-gpu=name,memory.used,memory.total --format=csv,noheader
export HF_HUB_OFFLINE=1 OPENAI_API_KEY=EMPTY no_proxy=localhost,127.0.0.1 NO_PROXY=localhost,127.0.0.1

# weights may still be downloading when the job starts: wait for every shard in the index (up to 90 min)
for i in $(seq 1 180); do
  if [ -f $MODEL_DIR/model.safetensors.index.json ] && [ -z "$(find $MODEL_DIR -name '*.incomplete' -print -quit)" ] && \
     python3 -c "import json,os,sys; d='$MODEL_DIR'; s=set(json.load(open(d+'/model.safetensors.index.json'))['weight_map'].values()); sys.exit(0 if all(os.path.exists(os.path.join(d,f)) for f in s) else 1)"; then
    break
  fi
  [ $i -eq 1 ] && echo "[weights] waiting for $MODEL_DIR"
  sleep 30
done
[ -f $MODEL_DIR/model.safetensors.index.json ] || { echo "[weights] not complete after 90 min"; exit 1; }

VLOG=$R/slurm/vllm.$SLURM_JOB_ID.log
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
CFG=$R/slurm/vllm_local.$SLURM_JOB_ID.yaml
sed "s#http://localhost:8000/v1#http://127.0.0.1:$PORT/v1#g" configs/vllm_local.yaml > $CFG
grep -q "127.0.0.1:$PORT" $CFG || { echo "[cfg] port substitution failed"; exit 1; }

PY=$P/.venv/bin/python
rc=0
step() { echo "[step] $* $(date +%H:%M:%S)"; "$@" < /dev/null || { echo "[step FAILED rc=$?] $*"; rc=1; }; }
step $PY scripts/audit_verifiers.py $CFG --n 100 --out $R/audit_vllm
step $PY scripts/audit_verifiers.py $CFG --n 100 --world tickets --out $R/audit_vllm_tickets
step $PY scripts/run_loop.py $CFG --generations 1 --run-dir $R/smoke_vllm
[ -s $R/smoke_vllm/generations.jsonl ] && step $PY scripts/report.py $R/smoke_vllm
echo "[job] finished rc=$rc $(date)"
exit $rc

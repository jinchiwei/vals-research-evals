#!/bin/bash
#SBATCH --job-name=pcnsl-pred-controls
#SBATCH --partition=cpu
#SBATCH --cpus-per-task=2
#SBATCH --mem=4G
#SBATCH --time=00:10:00
set -euo pipefail
export OMP_NUM_THREADS=2
export OPENBLAS_NUM_THREADS=2
export MKL_NUM_THREADS=2
cd /mnt/fac/CX500002_DS6/jkw/vals-research-evals/prediction-baselines-v1
/mnt/fac/CX500002_DS6/jkw/envs/neuronetwork/bin/python scripts/run_prediction_baselines.py \
  --dataset /mnt/fac/CX500002_DS6/jkw/vals-research-evals/prediction-data-20261114/dataset.private.json \
  --out results \
  --bootstrap 2000

#!/bin/bash
#SBATCH --job-name=scaling-test
#SBATCH --partition=gpu
#SBATCH --gres=gpu:1
#SBATCH --cpus-per-task=4
#SBATCH --mem=8G
#SBATCH --time=01:00:00
#SBATCH --output=/jobs/scaling-test-%j.log

# =============================================================
# Przykładowy skrypt Slurm do użycia z scale_estimate.py
#
# Kluczowe wymaganie: skrypt musi czytać DATASET_FRACTION
# i używać jej do przycięcia datasetu przed przetwarzaniem.
#
# scale_estimate.py uruchomi ten skrypt z:
#   DATASET_FRACTION=0.1  (lub inną wartością)
#
# Uruchomienie przez scale_estimate.py:
#   python3 /opt/eden-monitor/scale-estimator/scale_estimate.py \
#       /jobs/example_scaling_job.sh --fraction 0.1
# =============================================================

FRACTION="${DATASET_FRACTION:-1.0}"
echo "[job] Start: $(date -Iseconds)"
echo "[job] SLURM_JOB_ID=$SLURM_JOB_ID"
echo "[job] DATASET_FRACTION=$FRACTION"

# =============================================================
# PRZYKŁAD: symulacja obciążenia GPU proporcjonalnego do frakcji danych
#
# W prawdziwym skrypcie zastąp ten blok swoim kodem ML/HPC.
# Jedyna zmiana którą musisz wprowadzić: użyj $FRACTION do przycięcia danych.
#
# Przykład PyTorch (w prawdziwym skrypcie):
#   fraction = float(os.environ.get("DATASET_FRACTION", "1.0"))
#   dataset = MyDataset(...)
#   n = int(len(dataset) * fraction)
#   dataset = torch.utils.data.Subset(dataset, range(n))
# =============================================================

STEPS=$(python3 -c "print(int(100 * $FRACTION))")
echo "[job] Symulacja: $STEPS kroków (proporcjonalnie do DATASET_FRACTION=$FRACTION)"

python3 - <<PYEOF
import time
import os

fraction = float(os.environ.get("DATASET_FRACTION", "1.0"))
steps = int(100 * fraction)

print(f"[python] Przetwarzam {steps} kroków ({fraction*100:.0f}% datasetu)...")

# Symulacja obciążenia proporcjonalnego do frakcji
for i in range(steps):
    time.sleep(0.1)
    if (i + 1) % 10 == 0:
        print(f"[python] Krok {i+1}/{steps}")

print(f"[python] Gotowe.")
PYEOF

echo "[job] Koniec: $(date -Iseconds)"

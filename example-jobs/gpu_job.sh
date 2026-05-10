#!/bin/bash
#SBATCH --job-name=test-gpu
#SBATCH --partition=gpu
#SBATCH --gres=gpu:tesla:1       # 1 GPU symulowane
#SBATCH --cpus-per-task=1
#SBATCH --mem=512M
#SBATCH --time=00:02:00
#SBATCH --output=/tmp/slurm-job-%j.out

echo "================================================"
echo "Job ID:          $SLURM_JOB_ID"
echo "Węzeł:           $(hostname)"
echo "Przydzielone GPU: $SLURM_JOB_GPUS"
echo "================================================"
echo ""
echo "Symulacja obliczeń przez 10 sekund..."
sleep 10
echo "Obliczenia zakończone."

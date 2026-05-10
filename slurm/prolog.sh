#!/bin/bash
# =============================================================
# PROLOG — wywoływany przez slurmd przy STARCIE każdego zadania
# Uruchamiany jako root na węźle obliczeniowym
# MUSI zwrócić exit 0 — inaczej: anulowanie joba + drain węzła
# =============================================================

JOB_MAPPING_DIR="/run/dcgm-exporter/job-mapping"
LOG_FILE="/var/log/slurm/prolog.log"
PG_CONN="postgresql://eden:eden@timescaledb:5432/eden"

# Loguj start (na początku, żeby widzieć nawet jeśli coś pójdzie nie tak)
echo "[prolog] $(date -Iseconds) START job=$SLURM_JOB_ID user=$SLURM_JOB_USER gpus=${SLURM_JOB_GPUS:-brak}" \
    >> "$LOG_FILE"

# =============================================================
# 1. DCGM JOB MAPPING
#
# Zapisujemy plik: /run/dcgm-exporter/job-mapping/JOB_ID
# Zawartość: indeksy GPU przydzielone temu zadaniu
#
# fake-dcgm/exporter.py czyta ten katalog i od teraz
# metryki GPU 0 (lub innych) mają etykietę slurm_job_id="JOB_ID"
# To jest moment od którego Prometheus "widzi" ten job
# =============================================================
mkdir -p "$JOB_MAPPING_DIR"

# Fallback: jeśli SLURM_JOB_GPUS jest puste (np. dev bez prawdziwych GPU)
# — użyj GPU 0
GPU_LIST="${SLURM_JOB_GPUS:-0}"
echo "$GPU_LIST" > "$JOB_MAPPING_DIR/$SLURM_JOB_ID"

echo "[prolog] Mapowanie DCGM: job=$SLURM_JOB_ID → GPU=$GPU_LIST" >> "$LOG_FILE"

# =============================================================
# 2. REJESTRACJA W POSTGRESQL
#
# Wstawiamy rekord do job_runs już przy starcie zadania
# (nie czekamy na zakończenie)
# Epilog zaktualizuje end_time i state
# =============================================================
psql "$PG_CONN" -c "
    INSERT INTO job_runs (
        slurm_job_id, username, partition,
        submit_time, start_time, req_gpus, state
    ) VALUES (
        '$SLURM_JOB_ID',
        '$SLURM_JOB_USER',
        '${SLURM_JOB_PARTITION:-gpu}',
        to_timestamp(${SLURM_JOB_SUBMIT_TIME:-0}),
        to_timestamp(${SLURM_JOB_START_TIME:-0}),
        '${SLURM_JOB_GPUS:-0}',
        'RUNNING'
    )
    ON CONFLICT (slurm_job_id) DO UPDATE
        SET state = 'RUNNING',
            start_time = EXCLUDED.start_time;
" 2>> "$LOG_FILE" || \
    echo "[prolog] WARN: PostgreSQL niedostępny — kontynuuję" >> "$LOG_FILE"

echo "[prolog] OK job=$SLURM_JOB_ID" >> "$LOG_FILE"

# =============================================================
# WAŻNE: zawsze exit 0
# Nawet jeśli PostgreSQL jest niedostępny, zadanie musi się uruchomić
# =============================================================
exit 0

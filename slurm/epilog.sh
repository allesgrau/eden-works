#!/bin/bash
# =============================================================
# EPILOG — wywoływany przez slurmd po ZAKOŃCZENIU zadania
# slurmd czeka na zakończenie Epilogu przed zwolnieniem węzła
# Dlatego: długie operacje uruchamiamy w tle (&)
# =============================================================

JOB_MAPPING_DIR="/run/dcgm-exporter/job-mapping"
LOG_FILE="/var/log/slurm/epilog.log"
PG_CONN="postgresql://eden:eden@timescaledb:5432/eden"

echo "[epilog] $(date -Iseconds) END job=$SLURM_JOB_ID user=$SLURM_JOB_USER exit=${SLURM_JOB_EXIT_CODE:-?}" \
    >> "$LOG_FILE"

# =============================================================
# 1. USUŃ MAPOWANIE DCGM
#
# Od tej chwili metryki GPU przestają być tagowane tym job_id
# Prometheus następnym scrapem zobaczy slurm_job_id=""
# =============================================================
MAPPING_FILE="$JOB_MAPPING_DIR/$SLURM_JOB_ID"
if [ -f "$MAPPING_FILE" ]; then
    rm "$MAPPING_FILE"
    echo "[epilog] Usunięto mapowanie DCGM dla job=$SLURM_JOB_ID" >> "$LOG_FILE"
fi

# =============================================================
# 2. AKTUALIZUJ POSTGRESQL
# =============================================================
psql "$PG_CONN" -c "
    UPDATE job_runs SET
        end_time  = to_timestamp(${SLURM_JOB_END_TIME:-0}),
        state     = 'COMPLETED',
        exit_code = '${SLURM_JOB_EXIT_CODE:-0}'
    WHERE slurm_job_id = '$SLURM_JOB_ID';
" 2>> "$LOG_FILE" || \
    echo "[epilog] WARN: PostgreSQL niedostępny" >> "$LOG_FILE"

# =============================================================
# 3. OBLICZ EFFICIENCY SCORE — W TLE (&)
#
# Kluczowy wzorzec: uruchamiamy scorer asynchronicznie
# Epilog kończy się natychmiast → slurmd zwalnia węzeł
# W prawdziwym systemie: scorer odpytuje Prometheus i sacct
# =============================================================
(
    sleep 8   # czekaj aż slurmdbd zaktualizuje dane po zakończeniu joba

    echo "[scorer] $(date -Iseconds) Obliczam score dla job=$SLURM_JOB_ID" \
        >> "$LOG_FILE"

    # Placeholder: losowy score
    # W przyszłości: odpytaj Prometheus API i sacct, oblicz prawdziwy score
    FAKE_SCORE=$((RANDOM % 60 + 20))

    psql "$PG_CONN" -c "
        UPDATE job_runs
        SET efficiency_score = $FAKE_SCORE
        WHERE slurm_job_id = '$SLURM_JOB_ID';
    " 2>> "$LOG_FILE" || true

    echo "[scorer] job=$SLURM_JOB_ID score=$FAKE_SCORE" >> "$LOG_FILE"
) &
# Ampersand & = uruchom w tle, nie czekaj

echo "[epilog] OK job=$SLURM_JOB_ID (scorer uruchomiony w tle)" >> "$LOG_FILE"

# ZAWSZE exit 0
exit 0

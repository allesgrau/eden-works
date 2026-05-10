#!/usr/bin/env python3
"""
Oblicza efficiency score zadania Slurm.
Uruchamiany z Epilogu: python3 /opt/eden-monitor/slurm-hooks/efficiency_scorer.py JOB_ID DURATION_SECONDS
"""

import sys
import subprocess
import psycopg2
import requests

PROMETHEUS = "http://prometheus:9090"
PG_DSN     = "postgresql://eden:eden@timescaledb:5432/eden"

def get_prometheus_avg(job_id, duration_seconds):
    """Średnia utylizacja GPU podczas trwania zadania."""
    lookback = max(duration_seconds, 60)
    query = f'avg_over_time(DCGM_FI_DEV_GPU_UTIL{{slurm_job_id="{job_id}"}}[{lookback}s])'
    try:
        r = requests.get(f"{PROMETHEUS}/api/v1/query", params={"query": query}, timeout=10)
        results = r.json()["data"]["result"]
        if results:
            values = [float(s["value"][1]) for s in results]
            return sum(values) / len(values)
    except Exception as e:
        print(f"[scorer] Prometheus niedostępny: {e}")
    return None

def get_req_gpus(job_id):
    """Liczba GPU zadeklarowanych przez użytkownika (z sacct)."""
    try:
        result = subprocess.run(
            ["sacct", "-j", job_id, "--format=ReqGRES", "-X", "--parsable2", "--noheader"],
            capture_output=True, text=True, timeout=10
        )
        line = result.stdout.strip().split("\n")[0]
        # Format: "gpu:tesla:2" lub "gpu:2"
        for part in line.split(","):
            if "gpu" in part.lower():
                return int(part.split(":")[-1])
    except Exception:
        pass
    return 1

def calculate_score(avg_util, req_gpus):
    """
    Score 0-100:
    - Baza: średnia utylizacja (np. 75% -> 75 pkt)
    - Kara over-provisioning: każde dodatkowe GPU ponad potrzeby -10 pkt
      (uproszczenie: jeśli util < 50%, zakładamy że 1 GPU wystarczyłoby)
    """
    if avg_util is None:
        return None

    score = avg_util

    # Kara za over-provisioning
    if avg_util < 50 and req_gpus > 1:
        score -= (req_gpus - 1) * 10

    return max(0, min(100, int(score)))

def update_db(job_id, score, avg_util):
    try:
        conn = psycopg2.connect(PG_DSN)
        cur  = conn.cursor()
        cur.execute("""
            UPDATE job_runs
            SET efficiency_score = %s,
                avg_gpu_util     = %s
            WHERE slurm_job_id = %s
        """, (score, avg_util, job_id))
        conn.commit()
        cur.close()
        conn.close()
        print(f"[scorer] job={job_id} score={score} avg_util={avg_util:.1f}%")
    except Exception as e:
        print(f"[scorer] DB error: {e}")

if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Użycie: efficiency_scorer.py JOB_ID DURATION_SECONDS")
        sys.exit(1)

    job_id   = sys.argv[1]
    duration = int(sys.argv[2])

    avg_util = get_prometheus_avg(job_id, duration)
    req_gpus = get_req_gpus(job_id)
    score    = calculate_score(avg_util, req_gpus)

    update_db(job_id, score, avg_util or 0.0)

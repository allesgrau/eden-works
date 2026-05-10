#!/usr/bin/env python3
"""Co 5 minut: pobierz metryki z Prometheus, wstaw do TimescaleDB."""

import time
import requests
import psycopg2

PROMETHEUS = "http://prometheus:9090"
PG_DSN = "postgresql://eden:eden@timescaledb:5432/eden"
INTERVAL = 300  # 5 minut

def fetch_metric(query):
    r = requests.get(f"{PROMETHEUS}/api/v1/query", params={"query": query})
    r.raise_for_status()
    return r.json()["data"]["result"]

def collect_and_store():
    util_data  = fetch_metric("DCGM_FI_DEV_GPU_UTIL")
    power_data = fetch_metric("DCGM_FI_DEV_POWER_USAGE")
    temp_data  = fetch_metric("DCGM_FI_DEV_GPU_TEMP")
    mem_data   = fetch_metric("DCGM_FI_DEV_FB_USED")

    # Zbuduj słowniki: gpu_index -> wartość
    def to_dict(results):
        return {r["metric"].get("gpu_index", "0"): float(r["value"][1]) for r in results}

    power = to_dict(power_data)
    temp  = to_dict(temp_data)
    mem   = to_dict(mem_data)

    conn = psycopg2.connect(PG_DSN)
    cur  = conn.cursor()

    for sample in util_data:
        labels  = sample["metric"]
        gpu_idx = labels.get("gpu_index", "0")
        job_id  = labels.get("slurm_job_id") or None

        cur.execute("""
            INSERT INTO node_snapshots
                (captured_at, node, gpu_index, slurm_job_id,
                 gpu_util, gpu_mem_used_mb, power_w, temp_c)
            VALUES (NOW(), %s, %s, %s, %s, %s, %s, %s)
        """, (
            labels.get("node", "gpu-node-01"),
            int(gpu_idx),
            job_id,
            float(sample["value"][1]),
            mem.get(gpu_idx, 0),
            power.get(gpu_idx, 0),
            temp.get(gpu_idx, 0),
        ))

    conn.commit()
    cur.close()
    conn.close()
    print(f"Zapisano snapshot ({len(util_data)} GPU).")

if __name__ == "__main__":
    print("Snapshot writer startuje...")
    while True:
        try:
            collect_and_store()
        except Exception as e:
            print(f"Błąd: {e}")
        time.sleep(INTERVAL)

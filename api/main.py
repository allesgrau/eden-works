from fastapi import FastAPI, HTTPException
from contextlib import asynccontextmanager
import psycopg2
import psycopg2.extras
import os

PG_DSN = os.getenv("PG_DSN", "postgresql://eden:eden@timescaledb:5432/eden")

def get_conn():
    return psycopg2.connect(PG_DSN, cursor_factory=psycopg2.extras.RealDictCursor)

@asynccontextmanager
async def lifespan(app: FastAPI):
    yield

app = FastAPI(title="Eden Monitor API", lifespan=lifespan)

@app.get("/api/jobs")
def list_jobs():
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT slurm_job_id, username, partition, state,
                       start_time, end_time, req_gpus,
                       efficiency_score, avg_gpu_util
                FROM job_runs
                ORDER BY COALESCE(start_time, created_at) DESC
                LIMIT 50
            """)
            return cur.fetchall()

@app.get("/api/jobs/{job_id}")
def get_job(job_id: str):
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT * FROM job_runs WHERE slurm_job_id = %s",
                (job_id,)
            )
            row = cur.fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Job not found")
    return row

@app.get("/api/stats")
def get_stats():
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT
                    COUNT(*) FILTER (WHERE state = 'RUNNING')  AS running_jobs,
                    COUNT(*) FILTER (WHERE state = 'PENDING')  AS pending_jobs,
                    COUNT(*) FILTER (WHERE state = 'COMPLETED'
                                     AND end_time > NOW() - INTERVAL '24h') AS completed_today,
                    ROUND(AVG(efficiency_score) FILTER (
                        WHERE efficiency_score IS NOT NULL
                        AND   end_time > NOW() - INTERVAL '7 days'
                    )::numeric, 1) AS avg_score_7d
                FROM job_runs
            """)
            return cur.fetchone()

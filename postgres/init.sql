-- Aktywuj rozszerzenie TimescaleDB
CREATE EXTENSION IF NOT EXISTS timescaledb;

-- =====================================================
-- TABELA 1: Zadania Slurm (zwykła tabela relacyjna)
-- Jedna linijka = jedno zadanie
-- =====================================================
CREATE TABLE IF NOT EXISTS job_runs (
    id               BIGSERIAL    PRIMARY KEY,
    slurm_job_id     TEXT         NOT NULL UNIQUE,
    username         TEXT         NOT NULL,
    partition        TEXT,
    submit_time      TIMESTAMPTZ,
    start_time       TIMESTAMPTZ,
    end_time         TIMESTAMPTZ,
    req_gpus         TEXT,         -- zadeklarowane GPU (z SLURM_JOB_GPUS)
    gres_used        TEXT,         -- faktycznie użyte (z sacct)
    state            TEXT DEFAULT 'PENDING',
    exit_code        TEXT,
    efficiency_score SMALLINT,     -- 0-100, obliczony po zakończeniu
    avg_gpu_util     REAL,         -- średnia utylizacja GPU (%)
    avg_power_w      REAL,         -- średni pobór mocy (W)
    created_at       TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_jobs_username   ON job_runs(username);
CREATE INDEX IF NOT EXISTS idx_jobs_start_time ON job_runs(start_time DESC);
CREATE INDEX IF NOT EXISTS idx_jobs_state      ON job_runs(state);

-- =====================================================
-- TABELA 2: Metryki GPU (hypertable TimescaleDB)
-- Jedna linijka = jeden pomiar GPU w jednym momencie
-- =====================================================
CREATE TABLE IF NOT EXISTS node_snapshots (
    captured_at      TIMESTAMPTZ  NOT NULL,
    node             TEXT         NOT NULL,
    gpu_index        SMALLINT     NOT NULL,
    slurm_job_id     TEXT,         -- NULL = GPU bezczynne
    gpu_util         REAL,         -- utylizacja (%)
    gpu_mem_used_mb  REAL,         -- użyta pamięć (MB)
    power_w          REAL,         -- pobór mocy (W)
    temp_c           REAL          -- temperatura (°C)
);

-- Kluczowa komenda: zamień zwykłą tabelę w hypertable
-- chunk_time_interval: dziel na chunki co 7 dni
SELECT create_hypertable(
    'node_snapshots',
    'captured_at',
    chunk_time_interval => INTERVAL '7 days',
    if_not_exists => TRUE
);

-- =====================================================
-- POLITYKA RETENCJI: automatycznie usuń dane > 6 miesięcy
-- TimescaleDB usuwa cały chunk (superszybko) zamiast
-- kasować wiersz po wierszu
-- =====================================================
SELECT add_retention_policy('node_snapshots', INTERVAL '6 months', if_not_exists => TRUE);

-- =====================================================
-- CONTINUOUS AGGREGATE: automatyczne agregaty godzinowe
-- TimescaleDB odświeża je w tle co godzinę
-- Zamiast liczyć AVG na żywo po milionach wierszy —
-- odpytujemy preobliczone wyniki
-- =====================================================
CREATE MATERIALIZED VIEW IF NOT EXISTS node_snapshots_hourly
WITH (timescaledb.continuous) AS
SELECT
    time_bucket('1 hour', captured_at) AS bucket,
    node,
    gpu_index,
    AVG(gpu_util)        AS avg_gpu_util,
    MAX(gpu_util)        AS max_gpu_util,
    AVG(gpu_mem_used_mb) AS avg_mem_used_mb,
    AVG(power_w)         AS avg_power_w,
    AVG(temp_c)          AS avg_temp_c,
    COUNT(*)             AS sample_count
FROM node_snapshots
GROUP BY bucket, node, gpu_index
WITH NO DATA;

SELECT add_continuous_aggregate_policy('node_snapshots_hourly',
    start_offset      => INTERVAL '3 hours',
    end_offset        => INTERVAL '1 hour',
    schedule_interval => INTERVAL '1 hour',
    if_not_exists     => TRUE
);

-- Agregaty godzinowe przechowuj przez 2 lata
SELECT add_retention_policy('node_snapshots_hourly', INTERVAL '2 years', if_not_exists => TRUE);

-- =====================================================
-- PRZYKŁADOWE DANE do testów
-- =====================================================
INSERT INTO job_runs (slurm_job_id, username, partition, submit_time, start_time, end_time, req_gpus, gres_used, state, efficiency_score, avg_gpu_util)
VALUES
    ('1001', 'jan.kowalski', 'gpu', NOW()-'3h'::INTERVAL, NOW()-'3h'::INTERVAL, NOW()-'1h'::INTERVAL, '2', 'gpu:2', 'COMPLETED', 78, 72.3),
    ('1002', 'anna.nowak',   'gpu', NOW()-'5h'::INTERVAL, NOW()-'5h'::INTERVAL, NOW()-'2h'::INTERVAL, '4', 'gpu:4', 'COMPLETED', 11,  8.4),
    ('1003', 'piotr.wiśni',  'gpu', NOW()-'30m'::INTERVAL, NOW()-'25m'::INTERVAL, NULL, '1', NULL, 'RUNNING', NULL, NULL);

INSERT INTO node_snapshots (captured_at, node, gpu_index, slurm_job_id, gpu_util, gpu_mem_used_mb, power_w, temp_c)
SELECT
    NOW() - (i * INTERVAL '5 minutes'),
    'gpu-node-01',
    (i % 4)::SMALLINT,
    CASE WHEN i % 5 = 0 THEN '1001' ELSE NULL END,
    CASE WHEN i % 5 = 0 THEN 60 + random()*30 ELSE random()*3 END,
    CASE WHEN i % 5 = 0 THEN 8000 + random()*8000 ELSE 400 END,
    CASE WHEN i % 5 = 0 THEN 160 + random()*100 ELSE 35 END,
    CASE WHEN i % 5 = 0 THEN 58 + random()*20 ELSE 33 END
FROM generate_series(1, 60) i;
"""
Fake DCGM Exporter

Symuluje metryki GPU w formacie Prometheus.
Kluczowy mechanizm: czyta /run/dcgm-exporter/job-mapping/
  - każdy plik: nazwa = slurm_job_id, zawartość = indeksy GPU (np. "0,2")
  - GPU w mapowaniu dostają etykietę slurm_job_id i symulują obciążenie
  - GPU bez mapowania symulują stan bezczynny

Identyczne zachowanie jak prawdziwy dcgm-exporter NVIDIA.
"""

import os
import time
import math
import random
from http.server import HTTPServer, BaseHTTPRequestHandler

JOB_MAPPING_DIR = "/run/dcgm-exporter/job-mapping"
PORT = 9400
NODE = "gpu-node-01"
NUM_GPUS = 4
GPU_MODELS = ["Tesla A100", "Tesla A100", "Tesla P100", "Tesla P100"]


def read_job_mappings():
    """Czyta katalog mapowania i zwraca {gpu_index_str: job_id}."""
    mappings = {}
    try:
        for filename in os.listdir(JOB_MAPPING_DIR):
            job_id = filename
            filepath = os.path.join(JOB_MAPPING_DIR, filename)
            with open(filepath) as f:
                content = f.read().strip()
                if content:
                    for gpu_idx in content.split(","):
                        mappings[gpu_idx.strip()] = job_id
    except FileNotFoundError:
        pass  # katalog nie istnieje jeszcze — OK
    return mappings


def generate_metrics():
    """Generuje tekst w formacie Prometheus exposition format."""
    job_mappings = read_job_mappings()
    t = time.time()
    lines = []

    # Zbierz wartości dla każdej metryki
    util_samples  = []
    mem_samples   = []
    power_samples = []
    temp_samples  = []

    for i in range(NUM_GPUS):
        gpu_str = str(i)
        job_id  = job_mappings.get(gpu_str, "")

        labels = {
            "gpu_index": gpu_str,
            "modelName": GPU_MODELS[i],
            "node":      NODE,
            "slurm_job_id": job_id,
        }

        if job_id:
            # GPU aktywne: wyższe wartości, oscylujące sinusem (realistyczne)
            util  = 55 + 35 * abs(math.sin(t / 60 + i * 1.3))
            mem   = 10000 + 6000 * abs(math.sin(t / 90 + i * 0.7))
            power = 200 + 80 * abs(math.sin(t / 45 + i * 1.1))
            temp  = 62 + 18 * abs(math.sin(t / 120 + i * 0.9))
        else:
            # GPU bezczynne: minimalne wartości z małym szumem
            util  = random.uniform(0, 2)
            mem   = 400 + random.random() * 100
            power = 35 + random.random() * 8
            temp  = 33 + random.random() * 4

        util_samples.append((labels, util))
        mem_samples.append((labels, mem))
        power_samples.append((labels, power))
        temp_samples.append((labels, temp))

    # Zbuduj tekst odpowiedzi
    def add_metric(name, help_text, samples):
        lines.append(f"# HELP {name} {help_text}")
        lines.append(f"# TYPE {name} gauge")
        for labels, value in samples:
            label_str = ",".join(f'{k}="{v}"' for k, v in labels.items())
            lines.append(f"{name}{{{label_str}}} {value:.2f}")

    add_metric("DCGM_FI_DEV_GPU_UTIL",     "GPU utilization (%).",    util_samples)
    add_metric("DCGM_FI_DEV_FB_USED",      "Framebuffer used (MB).",  mem_samples)
    add_metric("DCGM_FI_DEV_POWER_USAGE",  "Power draw (W).",         power_samples)
    add_metric("DCGM_FI_DEV_GPU_TEMP",     "GPU temperature (C).",    temp_samples)

    return "\n".join(lines) + "\n"


class MetricsHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == "/metrics":
            body = generate_metrics().encode()
            self.send_response(200)
            self.send_header("Content-Type", "text/plain; version=0.0.4")
            self.send_header("Content-Length", len(body))
            self.end_headers()
            self.wfile.write(body)
        else:
            self.send_response(404)
            self.end_headers()

    def log_message(self, fmt, *args):
        pass  # wycisz HTTP logi


if __name__ == "__main__":
    os.makedirs(JOB_MAPPING_DIR, exist_ok=True)
    print(f"Fake DCGM Exporter startuje na :{PORT}/metrics")
    print(f"Symuluje {NUM_GPUS} GPU: {GPU_MODELS}")
    print(f"Mapowania zadań: {JOB_MAPPING_DIR}/")
    server = HTTPServer(("0.0.0.0", PORT), MetricsHandler)
    server.serve_forever()
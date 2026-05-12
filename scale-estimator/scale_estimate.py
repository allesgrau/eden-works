#!/usr/bin/env python3
"""
scale_estimate.py - Estymator zasobów Slurm oparty na skalowaniu datasetu.

Uruchamia zadanie Slurm na ułamku danych (DATASET_FRACTION), mierzy faktyczne
zużycie zasobów przez sacct i Eden API, a następnie estymuje zasoby potrzebne
do uruchomienia na pełnym datasecie.

Wymagania:
  - Uruchamiany wewnątrz kontenera eden-slurm (ma dostęp do sbatch/sacct/squeue)
  - Lub: na węźle z zainstalowanym klientem Slurm i dostępem do sieci eden-net
  - Python 3: requests (zainstalowany w obrazie slurm przez pip)

Użycie:
  python3 scale_estimate.py moj_job.sh
  python3 scale_estimate.py moj_job.sh --fraction 0.25 --safety-margin 0.4
  python3 scale_estimate.py moj_job.sh --fractions 0.1,0.25,0.5

Wymaganie dotyczące skryptu Slurm:
  Twój skrypt musi respektować zmienną środowiskową DATASET_FRACTION.
  Przykład w Pythonie:
      fraction = float(os.environ.get("DATASET_FRACTION", "1.0"))
      dataset = dataset[:int(len(dataset) * fraction)]
"""

import argparse
import subprocess
import time
import sys
import re
from dataclasses import dataclass
from typing import Optional

try:
    import requests
    HAS_REQUESTS = True
except ImportError:
    HAS_REQUESTS = False

EDEN_API = "http://api:8000"


@dataclass
class JobMetrics:
    job_id: str
    elapsed_seconds: int
    max_rss_mb: float
    alloc_cpus: int
    req_gpus: int
    avg_gpu_util: Optional[float] = None


def submit_job(script_path: str, fraction: float) -> str:
    """Submittuje zadanie Slurm z ustawioną DATASET_FRACTION. Zwraca job_id."""
    result = subprocess.run(
        ["sbatch", f"--export=ALL,DATASET_FRACTION={fraction}", script_path],
        capture_output=True, text=True
    )
    if result.returncode != 0:
        raise RuntimeError(f"sbatch nie powiodło się:\n{result.stderr.strip()}")

    match = re.search(r"Submitted batch job (\d+)", result.stdout)
    if not match:
        raise RuntimeError(f"Nie można sparsować job_id z: {result.stdout.strip()}")

    return match.group(1)


def wait_for_job(job_id: str, poll_interval: int = 15, timeout: int = 7200) -> str:
    """Czeka na zakończenie zadania. Zwraca stan końcowy."""
    terminal_states = {"FAILED", "CANCELLED", "TIMEOUT", "OUT_OF_MEMORY", "NODE_FAIL"}
    start = time.time()

    while time.time() - start < timeout:
        result = subprocess.run(
            ["squeue", "-j", job_id, "-h", "-o", "%T"],
            capture_output=True, text=True
        )
        state = result.stdout.strip()

        if not state:
            break  # Zadanie opuściło kolejkę

        print(f"  [{int(time.time() - start):4d}s] Zadanie {job_id}: {state}")

        if state in terminal_states:
            raise RuntimeError(f"Zadanie {job_id} zakończyło się niepomyślnie: {state}")

        time.sleep(poll_interval)

    # Pobierz ostateczny stan z sacct
    result = subprocess.run(
        ["sacct", "-j", job_id, "--format=State", "-X", "--parsable2", "--noheader"],
        capture_output=True, text=True
    )
    return result.stdout.strip().split("\n")[0].split("|")[0]


def parse_elapsed(elapsed_str: str) -> int:
    """Parsuje czas Slurm 'HH:MM:SS' lub 'D-HH:MM:SS' na sekundy."""
    elapsed_str = elapsed_str.strip()
    days = 0
    if "-" in elapsed_str:
        days_str, elapsed_str = elapsed_str.split("-")
        days = int(days_str)
    parts = elapsed_str.split(":")
    h, m, s = int(parts[0]), int(parts[1]), int(parts[2])
    return days * 86400 + h * 3600 + m * 60 + s


def parse_memory(mem_str: str) -> float:
    """Parsuje MaxRSS Slurm (np. '512000K', '4G') na MB."""
    mem_str = mem_str.strip()
    if not mem_str or mem_str == "0":
        return 0.0
    if mem_str.endswith("K"):
        return float(mem_str[:-1]) / 1024
    if mem_str.endswith("M"):
        return float(mem_str[:-1])
    if mem_str.endswith("G"):
        return float(mem_str[:-1]) * 1024
    if mem_str.endswith("T"):
        return float(mem_str[:-1]) * 1024 * 1024
    return float(mem_str) / 1024  # zakładamy KB jeśli brak jednostki


def parse_gpu_count_from_tres(tres_str: str) -> int:
    """Wyciąga liczbę GPU z ReqTRES (np. 'billing=2,cpu=4,gres/gpu=2,mem=8G')."""
    for part in tres_str.split(","):
        part = part.strip()
        if part.startswith("gres/gpu="):
            try:
                return int(part.split("=")[-1])
            except ValueError:
                pass
    return 0


def collect_metrics(job_id: str) -> JobMetrics:
    """Zbiera metryki z sacct i opcjonalnie z Eden API."""
    result = subprocess.run(
        ["sacct", "-j", job_id,
         "--format=JobID,Elapsed,MaxRSS,AllocCPUS,ReqTRES",
         "-X", "--parsable2", "--noheader"],
        capture_output=True, text=True, timeout=30
    )

    lines = [l for l in result.stdout.strip().split("\n") if l]
    if not lines:
        raise RuntimeError(f"sacct nie zwrócił danych dla job {job_id}")

    fields = lines[0].split("|")
    if len(fields) < 5:
        raise RuntimeError(f"Nieoczekiwany format sacct: {lines[0]}")

    elapsed_seconds = parse_elapsed(fields[1])
    max_rss_mb = parse_memory(fields[2])
    alloc_cpus = int(fields[3]) if fields[3].strip() else 1
    req_gpus = parse_gpu_count_from_tres(fields[4])

    # Próba pobrania avg_gpu_util z Eden API
    avg_gpu_util = None
    if HAS_REQUESTS:
        try:
            r = requests.get(f"{EDEN_API}/api/jobs/{job_id}", timeout=5)
            if r.status_code == 200:
                data = r.json()
                avg_gpu_util = data.get("avg_gpu_util")
        except Exception:
            pass  # API niedostępne — nie blokuje działania skryptu

    return JobMetrics(
        job_id=job_id,
        elapsed_seconds=elapsed_seconds,
        max_rss_mb=max_rss_mb,
        alloc_cpus=alloc_cpus,
        req_gpus=req_gpus,
        avg_gpu_util=avg_gpu_util,
    )


def estimate_linear(metrics: JobMetrics, fraction: float, safety_margin: float) -> dict:
    """
    Estymacja liniowa: czas i pamięć skalują się proporcjonalnie do rozmiaru danych.

    Dla pamięci stosujemy bardziej konserwatywne skalowanie (0.5 * skala) bo
    modele ML mają stały narzut (parametry modelu), który nie rośnie z danymi.
    """
    scale = 1.0 / fraction

    estimated_time_s = metrics.elapsed_seconds * scale * (1 + safety_margin)

    # Pamięć: zakładamy że połowa to stały overhead modelu, połowa skaluje liniowo
    static_mem_mb = metrics.max_rss_mb * 0.5
    dynamic_mem_mb = metrics.max_rss_mb * 0.5
    estimated_mem_mb = (static_mem_mb + dynamic_mem_mb * scale) * (1 + safety_margin)

    h = int(estimated_time_s // 3600)
    m = int((estimated_time_s % 3600) // 60)
    s = int(estimated_time_s % 60)

    # Zaokrągl pamięć w górę do 100MB
    mem_mb_rounded = int((estimated_mem_mb + 99) // 100) * 100

    return {
        "method": "linear",
        "fraction_tested": fraction,
        "scale_factor": scale,
        "safety_margin": safety_margin,
        "estimated_time": f"{h:02d}:{m:02d}:{s:02d}",
        "estimated_time_seconds": int(estimated_time_s),
        "estimated_mem_mb": mem_mb_rounded,
        "req_gpus": metrics.req_gpus,
        "alloc_cpus": metrics.alloc_cpus,
        "avg_gpu_util_at_fraction": metrics.avg_gpu_util,
    }


def estimate_power_law(metrics_list: list[tuple[float, JobMetrics]], safety_margin: float) -> dict:
    """
    Estymacja przez dopasowanie prawa potęgowego: T = a * fraction^b.
    Wymaga co najmniej 2 punktów pomiarowych.

    Jeśli b ≈ 1: skalowanie liniowe.
    Jeśli b < 1: sublinearne (dobra wiadomość — np. algorytmy z cachingiem).
    Jeśli b > 1: superlinearne (uwaga — wzrost szybszy niż dane).
    """
    try:
        import math

        fractions = [f for f, _ in metrics_list]
        times = [m.elapsed_seconds for _, m in metrics_list]

        # Fit log-linear: log(T) = log(a) + b * log(fraction)
        log_f = [math.log(f) for f in fractions]
        log_t = [math.log(t) for t in times]

        n = len(log_f)
        sum_x = sum(log_f)
        sum_y = sum(log_t)
        sum_xy = sum(x * y for x, y in zip(log_f, log_t))
        sum_xx = sum(x * x for x in log_f)

        b = (n * sum_xy - sum_x * sum_y) / (n * sum_xx - sum_x ** 2)
        log_a = (sum_y - b * sum_x) / n
        a = math.exp(log_a)

        estimated_time_s = a * (1.0 ** b) * (1 + safety_margin)
        h = int(estimated_time_s // 3600)
        m_val = int((estimated_time_s % 3600) // 60)
        s = int(estimated_time_s % 60)

        # Pamięć — bierzemy z ostatniego pomiaru (przy największej frakcji)
        last_metrics = metrics_list[-1][1]
        last_fraction = metrics_list[-1][0]
        estimated_mem_mb = last_metrics.max_rss_mb * (1.0 / last_fraction) * 0.6 * (1 + safety_margin)
        mem_mb_rounded = int((estimated_mem_mb + 99) // 100) * 100

        scaling_label = "liniowe" if abs(b - 1.0) < 0.15 else ("sublinearne" if b < 1 else "superlinearne")

        return {
            "method": "power_law",
            "exponent_b": round(b, 3),
            "scaling_type": scaling_label,
            "safety_margin": safety_margin,
            "estimated_time": f"{h:02d}:{m_val:02d}:{s:02d}",
            "estimated_time_seconds": int(estimated_time_s),
            "estimated_mem_mb": mem_mb_rounded,
            "req_gpus": last_metrics.req_gpus,
            "alloc_cpus": last_metrics.alloc_cpus,
            "fractions_tested": [f for f, _ in metrics_list],
        }

    except Exception as e:
        print(f"  UWAGA: Dopasowanie prawa potęgowego nie powiodło się ({e}). Używam liniowej estymacji.")
        last_f, last_m = metrics_list[-1]
        return estimate_linear(last_m, last_f, safety_margin)


def print_report(estimates: dict, measured_metrics: JobMetrics, fraction: float):
    print()
    print("=" * 62)
    print("  REKOMENDACJA ZASOBÓW — Eden Scale Estimator")
    print("=" * 62)

    method_label = {"linear": "liniowe", "power_law": "prawo potęgowe"}.get(estimates["method"], estimates["method"])
    print(f"\nMetoda: {method_label} | Pomiar na {fraction*100:.0f}% danych | Margines: {estimates['safety_margin']*100:.0f}%")

    if estimates.get("scaling_type"):
        label_color = {"liniowe": "", "sublinearne": "(DOBRA wiadomość)", "superlinearne": "(UWAGA: szybki wzrost)"}
        print(f"Skalowanie: {estimates['scaling_type']} {label_color.get(estimates.get('scaling_type',''), '')}")

    if estimates.get("avg_gpu_util_at_fraction") is not None:
        util = estimates["avg_gpu_util_at_fraction"]
        warn = " ← NISKA, rozważ optymalizację" if util < 40 else ""
        print(f"Śr. utylizacja GPU przy {fraction*100:.0f}%: {util:.1f}%{warn}")

    print()
    print("Sugerowane parametry #SBATCH:")
    print(f"  #SBATCH --time={estimates['estimated_time']}")
    print(f"  #SBATCH --mem={estimates['estimated_mem_mb']}M")
    if estimates["req_gpus"] > 0:
        print(f"  #SBATCH --gres=gpu:{estimates['req_gpus']}")
    print(f"  #SBATCH --cpus-per-task={estimates['alloc_cpus']}")

    print()
    print("Pomiar bazowy:")
    print(f"  Czas przy {fraction*100:.0f}% danych: {measured_metrics.elapsed_seconds}s")
    print(f"  Max RSS przy {fraction*100:.0f}% danych: {measured_metrics.max_rss_mb:.0f} MB")
    print()
    print("UWAGA: Estymacja zakłada liniowe skalowanie czasu i pamięci z rozmiarem danych.")
    print("Dla algorytmów O(n²) lub innych superlinearnych — prawdziwy koszt będzie wyższy.")
    print("=" * 62)


def main():
    parser = argparse.ArgumentParser(
        description="Eden Scale Estimator: uruchamia zadanie na ułamku danych i estymuje zasoby dla 100%%.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Przykłady:
  python3 scale_estimate.py /jobs/moj_job.sh
  python3 scale_estimate.py /jobs/moj_job.sh --fraction 0.25 --safety-margin 0.4
  python3 scale_estimate.py /jobs/moj_job.sh --fractions 0.1,0.25,0.5

Wymaganie: Twój skrypt musi czytać zmienną DATASET_FRACTION i używać jej do
przycięcia datasetu. Przykład (Python):
  fraction = float(os.environ.get("DATASET_FRACTION", "1.0"))
  data = data[:int(len(data) * fraction)]
        """
    )
    parser.add_argument("script", help="Ścieżka do skryptu Slurm (.sh)")
    parser.add_argument(
        "--fraction", type=float, default=0.1,
        help="Ułamek datasetu (0.01–0.90), domyślnie 0.1 = 10%%"
    )
    parser.add_argument(
        "--fractions", type=str, default=None,
        help="Lista ułamków do pomiaru, np. '0.1,0.25,0.5' (używa prawa potęgowego)"
    )
    parser.add_argument(
        "--safety-margin", type=float, default=0.3,
        help="Margines bezpieczeństwa (domyślnie 0.3 = 30%%)"
    )
    parser.add_argument(
        "--poll-interval", type=int, default=15,
        help="Częstość sprawdzania statusu zadania w sekundach (domyślnie: 15)"
    )
    parser.add_argument(
        "--timeout", type=int, default=7200,
        help="Maksymalny czas oczekiwania na zadanie w sekundach (domyślnie: 7200)"
    )

    args = parser.parse_args()

    fractions_to_test = None
    if args.fractions:
        fractions_to_test = [float(f.strip()) for f in args.fractions.split(",")]
        for f in fractions_to_test:
            if not (0.01 <= f <= 0.90):
                print(f"Błąd: wszystkie frakcje muszą być w przedziale 0.01–0.90 (podano {f})")
                sys.exit(1)
        fractions_to_test = sorted(fractions_to_test)
    else:
        if not (0.01 <= args.fraction <= 0.90):
            print("Błąd: --fraction musi być w przedziale 0.01–0.90")
            sys.exit(1)
        fractions_to_test = [args.fraction]

    if len(fractions_to_test) == 1:
        fraction = fractions_to_test[0]
        print(f"\nEden Scale Estimator")
        print(f"Skrypt:  {args.script}")
        print(f"Frakcja: {fraction*100:.0f}% danych → skalowanie ×{1/fraction:.1f}")
        print(f"Margines bezpieczeństwa: {args.safety_margin*100:.0f}%\n")

        print(f"[1/3] Submituję zadanie z DATASET_FRACTION={fraction}...")
        job_id = submit_job(args.script, fraction)
        print(f"      job_id = {job_id}\n")

        print("[2/3] Czekam na zakończenie zadania...")
        final_state = wait_for_job(job_id, args.poll_interval, args.timeout)
        print(f"\n      Stan końcowy: {final_state}")

        if "COMPLETED" not in final_state:
            print(f"\nZadanie nie zakończyło się pomyślnie ({final_state}). Estymacja niemożliwa.")
            sys.exit(1)

        print("\n[3/3] Zbieram metryki (sacct + Eden API)...")
        metrics = collect_metrics(job_id)

        estimates = estimate_linear(metrics, fraction, args.safety_margin)
        print_report(estimates, metrics, fraction)

    else:
        # Tryb wielokrotnych pomiarów — dopasowanie prawa potęgowego
        print(f"\nEden Scale Estimator (tryb wielokrotnych pomiarów)")
        print(f"Skrypt:  {args.script}")
        print(f"Frakcje: {[f'{f*100:.0f}%' for f in fractions_to_test]}")
        print(f"Margines bezpieczeństwa: {args.safety_margin*100:.0f}%\n")

        results = []
        for i, fraction in enumerate(fractions_to_test):
            print(f"[Pomiar {i+1}/{len(fractions_to_test)}] Frakcja = {fraction*100:.0f}%")
            print(f"  Submituję zadanie z DATASET_FRACTION={fraction}...")
            job_id = submit_job(args.script, fraction)
            print(f"  job_id = {job_id}")
            final_state = wait_for_job(job_id, args.poll_interval, args.timeout)
            print(f"  Stan: {final_state}")

            if "COMPLETED" not in final_state:
                print(f"  Pomiar pominięty (zadanie nie ukończyło się pomyślnie).")
                continue

            metrics = collect_metrics(job_id)
            results.append((fraction, metrics))
            print(f"  Czas: {metrics.elapsed_seconds}s, RAM: {metrics.max_rss_mb:.0f}MB\n")

        if len(results) < 2:
            print("Za mało udanych pomiarów do dopasowania krzywej. Potrzeba co najmniej 2.")
            if results:
                f, m = results[0]
                estimates = estimate_linear(m, f, args.safety_margin)
                print_report(estimates, m, f)
            sys.exit(0 if results else 1)

        estimates = estimate_power_law(results, args.safety_margin)
        last_f, last_m = results[-1]
        print_report(estimates, last_m, last_f)


if __name__ == "__main__":
    main()

# eden-stack

Lokalne środowisko symulujące klaster GPU HPC — zbudowane od zera, warstwa po warstwie.

Stawiasz tutaj prawdziwy stos: kolejkowanie zadań (Slurm), zbieranie metryk GPU (Prometheus + fake DCGM), bazę danych szeregów czasowych (TimescaleDB) i dashboardy (Grafana) — wszystko w kontenerach Docker, bez potrzeby dostępu do fizycznych kart GPU.

Repozytorium służy jako **samodzielne środowisko szkoleniowe** do nauki Dockera, Slurma i najlepszych praktyk zarządzania obliczeniami HPC.

---

## Spis treści

- [eden-stack](#eden-stack)
  - [Spis treści](#spis-treści)
  - [Wymagania wstępne](#wymagania-wstępne)
    - [Weryfikacja środowiska](#weryfikacja-środowiska)
  - [Struktura repozytorium](#struktura-repozytorium)
  - [Kluczowe zasady — TL;DR](#kluczowe-zasady--tldr)
    - [Dane i wolumeny](#dane-i-wolumeny)
    - [Mapowanie zadań GPU](#mapowanie-zadań-gpu)
    - [Sieć kontenerów](#sieć-kontenerów)
    - [Warstwy Dockerfile](#warstwy-dockerfile)
  - [Jak zacząć](#jak-zacząć)

---

## Wymagania wstępne

Przed rozpoczęciem upewnij się, że masz:

| Wymaganie                                                      | Opis                                                              |
| -------------------------------------------------------------- | ----------------------------------------------------------------- | --- |
| **Docker Desktop** (Mac/Windows) lub **Docker Engine** (Linux) | Silnik konteneryzacji — wersja 26+                                |
| **Docker Compose v2**                                          | Wbudowany w Docker Desktop; weryfikacja: `docker compose version` |
| **Terminal**                                                   | Bash lub Zsh                                                      |
| **Edytor tekstu**                                              | VS Code, vim, nano — cokolwiek                                    |
| **Podstawowa znajomość Linuksa**                               | Nawigacja po katalogach, edycja plików, przekierowania `>` i `    | `   |

> **Nie potrzebujesz** karty GPU — fake DCGM Exporter symuluje metryki GPU w formacie identycznym z prawdziwym DCGM NVIDIA.

### Weryfikacja środowiska

```bash
docker --version           # Docker version 26.x.x lub nowszy
docker compose version     # Docker Compose version v2.x.x
```

Jeśli obie komendy działają — możesz zaczynać.

---

## Struktura repozytorium

```
eden-stack/
├── postgres/           # Schemat bazy danych (init.sql)
├── prometheus/         # Konfiguracja scrapowania metryk
├── grafana/            # Dashboardy i datasource provisioning
├── fake-dcgm/          # Symulator metryk GPU (Python)
├── slurm/              # Konfiguracja + skrypty prolog/epilog
├── snapshot-writer/    # Usługa zapisująca snapshoty metryk do bazy
├── example-jobs/       # Przykładowe skrypty Slurm do testów
├── api/                # Warstwa API
├── docker-compose.yml  # Orkiestracja całego stosu
└── TUTORIAL.md         # Instrukcja krok po kroku
```

---

## Kluczowe zasady — TL;DR

### Dane i wolumeny

- **Nigdy nie używaj `docker compose down -v`** chyba że świadomie chcesz skasować dane — flaga `-v` usuwa wolumeny z danymi bazy.
- Dane TimescaleDB są przechowywane w wolumenie Dockera `timescale-data`. Przetrwają restart kontenerów.
- Metryki GPU starsze niż **6 miesięcy** są automatycznie usuwane przez politykę retencji TimescaleDB (chunki, nie wiersz po wierszu).
- Agregaty godzinowe (`node_snapshots_hourly`) są przechowywane przez **2 lata**.

### Mapowanie zadań GPU

Slurm komunikuje się z fake DCGM przez katalog `/run/dcgm-exporter/job-mapping/`:

- Każdy plik = jedno zadanie Slurm (`nazwa_pliku = slurm_job_id`, `zawartość = indeksy GPU`)
- GPU z mapowaniem symulują obciążenie; bez mapowania — stan bezczynny

### Sieć kontenerów

Wszystkie serwisy działają w sieci `eden-net`. Kontenery adresują się **po nazwie serwisu**, nie po `localhost`:

- Baza danych: `timescaledb:5432`
- Prometheus: `prometheus:9090`
- Fake DCGM: `fake-dcgm:9400`

### Warstwy Dockerfile

Rzeczy rzadko zmieniane (instalacja pakietów) — na początku Dockerfile. Kod i konfiguracja — na końcu. Docker cachuje każdą warstwę.

---

## Jak zacząć

Szczegółowa instrukcja krok po kroku — od instalacji Dockera, przez budowanie każdego komponentu, aż po weryfikację przepływu danych end-to-end — znajduje się w:

**[TUTORIAL.md](./TUTORIAL.md)**

Tutorial podzielony jest na trzy części:

| Część       | Zawartość                                                                          | Czas |
| ----------- | ---------------------------------------------------------------------------------- | ---- |
| **Część 1** | Docker od podstaw (kontenery, porty, wolumeny, Dockerfile, Compose)                | ~2 h |
| **Część 2** | Budowanie infrastruktury krok po kroku (baza, metryki, Grafana, Slurm, integracja) | ~4 h |
| **Część 3** | Weryfikacja end-to-end, debugowanie, co dalej                                      | ~1 h |

**Zasada:** żaden plik nie pojawia się magicznie — wszystko tworzysz ręcznie, rozumiejąc każdą linijkę.

---

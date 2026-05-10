# Wybitny poradnik: Budujesz klaster HPC od zera

**Dla kogo:** Znasz Bash i podstawy Linuksa. Nigdy nie używałeś Dockera, Slurma, Prometheusa ani TimescaleDB.

**Co zbudujesz:** Lokalne środowisko symulujące prawdziwy klaster GPU — z kolejkowaniem zadań (Slurm), zbieraniem metryk (Prometheus + DCGM), bazą danych szeregów czasowych (TimescaleDB) i dashboardami (Grafana). Każdy komponent tworzysz od zera, samodzielnie wpisując każdy plik.

**Zasada tego poradnika:** Żaden plik nie pojawia się magicznie. Wszystko tworzysz ręcznie, rozumiejąc każdą linijkę.

**Wymagania:**
- Docker Desktop (Mac/Windows) lub Docker Engine (Linux)
- Edytor tekstu (VS Code, vim, nano — cokolwiek)
- Terminal

**Czas:** 5-8 godzin przy spokojnym tempie z ćwiczeniami.

---

## Spis treści

### Część 1: Docker od podstaw
- [1.1 Instalacja i weryfikacja](#11-instalacja-i-weryfikacja)
- [1.2 Twój pierwszy kontener](#12-twój-pierwszy-kontener)
- [1.3 Kontenery interaktywne i porty](#13-kontenery-interaktywne-i-porty)
- [1.4 Wolumeny — dane które przeżyją kontener](#14-wolumeny--dane-które-przeżyją-kontener)
- [1.5 Twój pierwszy Dockerfile](#15-twój-pierwszy-dockerfile)
- [1.6 Docker Compose — orkiestracja](#16-docker-compose--orkiestracja)

### Część 2: Budujemy infrastrukturę krok po kroku
- [2.1 Struktura projektu](#21-struktura-projektu)
- [2.2 Krok 1 — Baza danych: PostgreSQL + TimescaleDB](#22-krok-1--baza-danych-postgresql--timescaledb)
- [2.3 Krok 2 — Metryki: Fake DCGM + Prometheus](#23-krok-2--metryki-fake-dcgm--prometheus)
- [2.4 Krok 3 — Wizualizacja: Grafana](#24-krok-3--wizualizacja-grafana)
- [2.5 Krok 4 — Kolejkowanie: Slurm](#25-krok-4--kolejkowanie-slurm)
- [2.6 Krok 5 — Integracja: Prolog i Epilog](#26-krok-5--integracja-prolog-i-epilog)

### Część 3: Weryfikacja i debugowanie
- [3.1 Pełny przepływ danych end-to-end](#31-pełny-przepływ-danych-end-to-end)
- [3.2 Co zrobić gdy coś nie działa](#32-co-zrobić-gdy-coś-nie-działa)
- [3.3 Co dalej — samodzielne rozbudowanie systemu](#33-co-dalej--samodzielne-rozbudowanie-systemu)

---

# Część 1: Docker od podstaw

## 1.1 Instalacja i weryfikacja

### Mac / Windows

Pobierz i zainstaluj **Docker Desktop** ze strony `https://www.docker.com/products/docker-desktop/`.
Po instalacji uruchom aplikację — w pasku menu (Mac) lub zasobniku systemowym (Windows) pojawi się ikona wieloryba.

### Linux (Ubuntu/Debian)

```bash
curl -fsSL https://get.docker.com | sh
sudo usermod -aG docker $USER
newgrp docker
```

### Weryfikacja

```bash
docker --version
```
Oczekiwany wynik (wersja może być nowsza):
```
Docker version 26.0.0, build abc1234
```

```bash
docker compose version
```
```
Docker Compose version v2.26.0
```

Jeśli obie komendy działają — możemy zaczynać.

---

## 1.2 Twój pierwszy kontener

### Czym jest kontener

Kontener to izolowany proces działający na Twoim systemie, który ma własny system plików, własne zmienne środowiskowe i własną sieć. W środku "myśli", że jest na osobnym komputerze — nie wie nic o Twoim systemie operacyjnym.

Kluczowa różnica od maszyny wirtualnej: kontener nie emuluje sprzętu. Używa tego samego jądra Linuksa co host. Dzięki temu startuje w ułamku sekundy i zużywa kilkadziesiąt MB RAM zamiast gigabajtów.

```
Wirtualna maszyna              Kontener Docker
┌─────────────────┐            ┌─────────────────┐
│  Twój program   │            │  Twój program   │
│  Biblioteki     │            │  Biblioteki     │
│  System OS      │            ├─────────────────┤
│  (pełny Ubuntu) │            │  Docker Engine  │
├─────────────────┤            ├─────────────────┤
│  Hypervisor     │            │  Twój OS        │
├─────────────────┤            ├─────────────────┤
│  Twój sprzęt    │            │  Twój sprzęt    │
└─────────────────┘            └─────────────────┘
  ~1 GB RAM, 30s start           ~30 MB RAM, <1s start
```

### Hello World

```bash
docker run hello-world
```

Co się dzieje po tej komendzie:
1. Docker szuka obrazu `hello-world` lokalnie — nie ma go
2. Pobiera go z Docker Hub (`https://hub.docker.com`)
3. Tworzy kontener z tego obrazu
4. Uruchamia go — program wypisuje wiadomość i kończy się
5. Kontener zatrzymuje się

```bash
# Sprawdź że kontener istnieje (zatrzymany)
docker ps -a
```
```
CONTAINER ID   IMAGE         COMMAND    CREATED         STATUS                     NAMES
a1b2c3d4e5f6   hello-world   "/hello"   2 seconds ago   Exited (0) 1 second ago    friendly_tesla
```

```bash
# Usuń kontener
docker rm friendly_tesla   # (wstaw swoją nazwę)

# Usuń obraz
docker rmi hello-world
```

### Podstawowe komendy Docker

```bash
docker ps          # działające kontenery
docker ps -a       # wszystkie kontenery (w tym zatrzymane)
docker images      # pobrane obrazy
docker stop NAZWA  # zatrzymaj kontener
docker rm NAZWA    # usuń kontener
docker rmi OBRAZ   # usuń obraz
docker logs NAZWA  # logi kontenera
```

---

## 1.3 Kontenery interaktywne i porty

### Kontener interaktywny

Flagi `-it` oznaczają: `-i` (interactive — trzymaj stdin otwarty) i `-t` (tty — alokuj pseudo-terminal). Razem dają interaktywny shell wewnątrz kontenera.

```bash
docker run -it ubuntu:22.04 bash
```

Teraz jesteś **wewnątrz** kontenera Ubuntu. Twój terminal wygląda inaczej:
```
root@a1b2c3d4e5f6:/#
```

Sprawdź że to naprawdę izolowane środowisko:
```bash
# Wewnątrz kontenera:
cat /etc/os-release    # Ubuntu 22.04, nawet jeśli Twój host to macOS
ls /                   # system plików kontenera, nie Twojego hosta
ps aux                 # tylko procesy z kontenera
exit                   # wyjdź z kontenera
```

### Mapowanie portów

Kontenery mają własną sieć i własne porty — nie są dostępne z zewnątrz bez jawnego mapowania.

Uruchom Nginx (serwer HTTP):
```bash
docker run -d --name moj-nginx -p 8080:80 nginx
```

Flagi:
- `-d` — detached (w tle, nie blokuje terminala)
- `--name moj-nginx` — nadaj nazwę (zamiast losowej)
- `-p 8080:80` — mapuj port 8080 na hoście na port 80 w kontenerze

```bash
curl http://localhost:8080
# Zobaczysz HTML strony powitalnej Nginx
```

```bash
# Zatrzymaj i usuń
docker stop moj-nginx
docker rm moj-nginx
```

Format mapowania portów: `-p PORT_HOSTA:PORT_KONTENERA`

Możesz uruchomić 3 kontenery Nginx na różnych portach hosta, ale wszystkie wewnątrz słuchają na porcie 80:
```bash
docker run -d -p 8081:80 nginx
docker run -d -p 8082:80 nginx
docker run -d -p 8083:80 nginx
# każdy z nich odpowiada na innym porcie hosta
```

Posprzątnij:
```bash
docker stop $(docker ps -q)
docker rm $(docker ps -aq)
```

---

## 1.4 Wolumeny — dane które przeżyją kontener

**Problem:** Dane zapisane wewnątrz kontenera znikają gdy kontener jest usuwany.

**Dowód:**
```bash
docker run -it ubuntu:22.04 bash
# Wewnątrz kontenera:
echo "moje dane" > /tmp/test.txt
cat /tmp/test.txt
exit

# Uruchom ponownie (NOWY kontener z tego samego obrazu)
docker run -it ubuntu:22.04 bash
cat /tmp/test.txt
# cat: /tmp/test.txt: No such file or directory
exit
```

Plik zniknął — bo każdy `docker run` tworzy nowy kontener ze świeżego obrazu.

### Rozwiązanie: Wolumeny

**Wolumin nazwany** — zarządzany przez Docker, dane przetrwają usunięcie kontenera:

```bash
# Utwórz wolumin
docker volume create moje-dane

# Użyj woluminu: -v NAZWA_WOLUMINU:ŚCIEŻKA_W_KONTENERZE
docker run -it -v moje-dane:/data ubuntu:22.04 bash
# Wewnątrz:
echo "te dane przetrwają" > /data/test.txt
exit

# Nowy kontener, ten sam wolumin
docker run -it -v moje-dane:/data ubuntu:22.04 bash
cat /data/test.txt
# te dane przetrwają
exit
```

**Bind mount** — montujesz katalog z Twojego hosta bezpośrednio do kontenera:

```bash
mkdir /tmp/moj-katalog
echo "plik z hosta" > /tmp/moj-katalog/plik.txt

docker run -it -v /tmp/moj-katalog:/data ubuntu:22.04 bash
# Wewnątrz:
cat /data/plik.txt       # plik z hosta
echo "nowy" > /data/nowy.txt
exit

ls /tmp/moj-katalog      # nowy.txt jest na hoście!
```

Bind mount jest idealny do plików konfiguracyjnych które chcesz edytować bez przebudowywania kontenera.

---

## 1.5 Twój pierwszy Dockerfile

Zamiast pobierać gotowe obrazy, możemy budować własne. Dockerfile to przepis — lista instrukcji dla Dockera.

### Prosty przykład

Utwórz nowy katalog i plik:

```bash
mkdir ~/docker-nauka && cd ~/docker-nauka
```

Utwórz plik `Dockerfile` (bez rozszerzenia):

```dockerfile
# FROM — od jakiego obrazu zaczynamy. Zawsze pierwszy.
FROM ubuntu:22.04

# ENV — ustaw zmienną środowiskową
# noninteractive wyłącza pytania apt (np. o strefę czasową)
ENV DEBIAN_FRONTEND=noninteractive

# RUN — wykonaj komendę podczas BUDOWANIA obrazu
# Łączymy komendy przez && żeby zmniejszyć liczbę warstw
RUN apt-get update && apt-get install -y \
    curl \
    python3 \
    && rm -rf /var/lib/apt/lists/*

# WORKDIR — ustaw katalog roboczy (jak cd, ale trwały)
WORKDIR /app

# COPY — skopiuj plik z hosta do obrazu
# Format: COPY ŹRÓDŁO_NA_HOŚCIE MIEJSCE_W_OBRAZIE
COPY skrypt.py .

# CMD — komenda wykonywana gdy kontener startuje
# Można nadpisać przez docker run ... KOMENDA
CMD ["python3", "skrypt.py"]
```

Utwórz `skrypt.py`:

```python
import subprocess
result = subprocess.run(['python3', '--version'], capture_output=True, text=True)
print(f"Python działa: {result.stdout.strip()}")
print("Kontener zbudowany z Dockerfile!")
```

Zbuduj i uruchom:

```bash
# Zbuduj obraz i nazwij go "moj-obraz"
# Kropka na końcu = kontekst budowania (katalog z Dockerfile)
docker build -t moj-obraz .

# Sprawdź że obraz istnieje
docker images | grep moj-obraz

# Uruchom
docker run moj-obraz
```

Powinieneś zobaczyć:
```
Python działa: Python 3.10.x
Kontener zbudowany z Dockerfile!
```

### Warstwy obrazu — dlaczego kolejność instrukcji ma znaczenie

Docker cachuje każdą warstwę. Jeśli warstwa nie zmieniła się — nie jest przebudowywana.

```bash
# Zmień skrypt.py (dodaj jedną linię) i przebuduj
echo 'print("nowa linia")' >> skrypt.py
docker build -t moj-obraz .
```

Zauważysz w logach `---> Using cache` dla `RUN apt-get install` — pakiety nie są instalowane ponownie, bo ta warstwa się nie zmieniła. Tylko `COPY skrypt.py .` i `CMD` są przetworzone od nowa.

**Wniosek:** Rzeczy które zmieniają się rzadko (instalacja pakietów) dawaj na początku Dockerfile. Rzeczy które zmieniasz często (kod, konfiguracja) — na końcu.

### Instrukcje Dockerfile które będziemy używać

| Instrukcja | Opis | Przykład |
|---|---|---|
| `FROM` | Obraz bazowy | `FROM ubuntu:22.04` |
| `RUN` | Komenda podczas budowania | `RUN apt-get install -y curl` |
| `COPY` | Kopiuj pliki do obrazu | `COPY config.yml /etc/app/` |
| `ENV` | Zmienna środowiskowa | `ENV PORT=8080` |
| `WORKDIR` | Katalog roboczy | `WORKDIR /app` |
| `ENTRYPOINT` | Komenda startowa (nie nadpisywalna) | `ENTRYPOINT ["/start.sh"]` |
| `CMD` | Domyślne argumenty (nadpisywalne) | `CMD ["--debug"]` |
| `EXPOSE` | Dokumentuje port (nie otwiera!) | `EXPOSE 8080` |

Posprzątaj:
```bash
cd ~
docker rmi moj-obraz
rm -rf ~/docker-nauka
```

---

## 1.6 Docker Compose — orkiestracja

Uruchamianie wielu kontenerów przez `docker run` z mnóstwem flag szybko staje się nieznośne. Docker Compose pozwala opisać cały stos w jednym pliku YAML.

### Prosty przykład: aplikacja + baza danych

Utwórz katalog testowy:

```bash
mkdir ~/compose-nauka && cd ~/compose-nauka
```

Utwórz `docker-compose.yml`:

```yaml
# Wersja składni pliku (nie wersja Dockera)
version: '3.8'

services:
  # Serwis bazy danych
  baza:
    image: postgres:16        # gotowy obraz z Docker Hub
    environment:              # zmienne środowiskowe do kontenera
      POSTGRES_USER: uzytkownik
      POSTGRES_PASSWORD: haslo
      POSTGRES_DB: moja_baza
    volumes:
      - dane-bazy:/var/lib/postgresql/data   # wolumin nazwany
    healthcheck:              # jak sprawdzić czy serwis jest gotowy
      test: ["CMD", "pg_isready", "-U", "uzytkownik"]
      interval: 3s
      retries: 10

  # Serwis aplikacji
  aplikacja:
    image: ubuntu:22.04
    depends_on:
      baza:
        condition: service_healthy   # czekaj aż baza przejdzie healthcheck
    command: bash -c "apt-get install -qq postgresql-client > /dev/null && psql postgresql://uzytkownik:haslo@baza/moja_baza -c 'SELECT version();'"

# Wolumeny zarządzane przez Docker
volumes:
  dane-bazy:
```

Uruchom:

```bash
docker compose up
```

Obserwuj co się dzieje:
1. Docker pobiera obrazy `postgres:16` i `ubuntu:22.04`
2. Startuje kontener `baza` i czeka aż `pg_isready` zwróci sukces
3. Dopiero potem startuje `aplikacja`
4. `aplikacja` łączy się z bazą przez hostname `baza` (nie `localhost`!)
5. Wypisuje wersję PostgreSQL i kończy się

Kluczowa lekcja: **kontenery w tej samej sieci Compose adresują się po nazwie serwisu**. Kontener `aplikacja` nie wie jaki jest adres IP `baza` — Docker DNS tłumaczy `baza` na właściwy adres.

```bash
# Zatrzymaj i usuń (Ctrl+C jeśli nadal działa, potem:)
docker compose down

# Usuń też wolumeny
docker compose down -v
cd ~ && rm -rf ~/compose-nauka
```

### Najważniejsze komendy Docker Compose

```bash
docker compose up           # uruchom serwisy (na pierwszym planie)
docker compose up -d        # uruchom w tle (detached)
docker compose up -d --build  # przebuduj obrazy i uruchom
docker compose down         # zatrzymaj i usuń kontenery
docker compose down -v      # j.w. + usuń wolumeny
docker compose ps           # status serwisów
docker compose logs         # logi wszystkich serwisów
docker compose logs -f SERWIS  # logi konkretnego serwisu (na żywo)
docker compose exec SERWIS bash  # shell w działającym serwisie
docker compose build SERWIS      # przebuduj tylko jeden serwis
```

---

# Część 2: Budujemy infrastrukturę krok po kroku

Teraz budujesz prawdziwy system. Każdy krok dodaje jeden komponent — testujesz go i dopiero potem przechodzisz dalej.

## 2.1 Struktura projektu

Utwórz katalog projektu. Możesz użyć istniejącego `dev/` lub stworzyć świeży:

```bash
mkdir -p ~/eden-stack/{postgres,prometheus,grafana/provisioning/datasources,fake-dcgm,slurm/hooks,example-jobs}
cd ~/eden-stack
```

Będziemy dodawać pliki do tej struktury krok po kroku.

---

## 2.2 Krok 1 — Baza danych: PostgreSQL + TimescaleDB

### Czym jest TimescaleDB

PostgreSQL to relacyjna baza danych — świetna do tabel z zadaniami, użytkownikami, wynikami. Ale przechowywanie milionów próbek metryk GPU (jedna co 5 minut, 4 GPU, przez rok = ~420 000 wierszy) sprawia że zwykła tabela staje się wolna.

TimescaleDB to **rozszerzenie do PostgreSQL** które dodaje jeden kluczowy typ tabeli: **hypertable**. Hypertable automatycznie dzieli dane na chunki według czasu (np. co tydzień). Zapytanie o dane z ostatniego tygodnia skanuje jeden chunk, nie całą tabelę.

Instalacja: jeden pakiet apt na hoście lub — w naszym przypadku — gotowy obraz Docker.

### Utwórz schemat bazy

Utwórz plik `postgres/init.sql`. Ten plik PostgreSQL wykona automatycznie przy pierwszym uruchomieniu:

```bash
cat > postgres/init.sql << 'EOF'
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
EOF
```

### Utwórz docker-compose.yml (tylko baza)

```bash
cat > docker-compose.yml << 'EOF'
version: '3.8'

services:
  timescaledb:
    image: timescale/timescaledb:latest-pg16
    container_name: eden-timescaledb
    environment:
      POSTGRES_USER: eden
      POSTGRES_PASSWORD: eden
      POSTGRES_DB: eden
    volumes:
      - ./postgres/init.sql:/docker-entrypoint-initdb.d/init.sql
      - timescale-data:/var/lib/postgresql/data
    ports:
      - "5432:5432"
    networks:
      - eden-net
    healthcheck:
      test: ["CMD", "pg_isready", "-U", "eden"]
      interval: 5s
      retries: 10

volumes:
  timescale-data:

networks:
  eden-net:
    driver: bridge
EOF
```

### Uruchom i przetestuj

```bash
docker compose up -d timescaledb
docker compose logs -f timescaledb
# Czekaj aż zobaczysz: "database system is ready to accept connections"
# Ctrl+C żeby zatrzymać logi (kontener nadal działa)
```

### Eksploruj TimescaleDB

```bash
docker exec -it eden-timescaledb psql -U eden -d eden
```

Jesteś w psql. Wykonaj:

```sql
-- Lista tabel
\dt

-- Czy node_snapshots jest hypertable?
SELECT * FROM timescaledb_information.hypertables;

-- Chunki (partycje tygodniowe)
SELECT chunk_name, range_start, range_end
FROM timescaledb_information.chunks
WHERE hypertable_name = 'node_snapshots';

-- Przykładowe dane
SELECT * FROM job_runs;

-- Metryki z ostatniej godziny
SELECT captured_at, gpu_index, gpu_util, power_w
FROM node_snapshots
WHERE captured_at > NOW() - INTERVAL '1 hour'
ORDER BY captured_at DESC
LIMIT 10;

-- Rozmiar hypertable
SELECT pg_size_pretty(hypertable_size('node_snapshots'));

-- Wyjdź
\q
```

### Ćwiczenie: wstaw dane i obserwuj chunki

```sql
-- Wstaw dane z 3 różnych tygodni
INSERT INTO node_snapshots (captured_at, node, gpu_index, gpu_util, power_w, temp_c)
SELECT
    NOW() - (i * INTERVAL '10 minutes'),
    'gpu-node-01', (i % 4)::SMALLINT,
    50 + random()*40, 150 + random()*100, 55 + random()*20
FROM generate_series(1, 3024) i;  -- 3 tygodnie co 10 min

-- Ile chunków powstało?
SELECT COUNT(*) FROM timescaledb_information.chunks WHERE hypertable_name = 'node_snapshots';
-- Powinno być 3 (jeden na tydzień)

-- Odśwież agregaty godzinowe
CALL refresh_continuous_aggregate('node_snapshots_hourly', NULL, NULL);

-- Sprawdź agregaty
SELECT bucket, gpu_index, avg_gpu_util, avg_power_w
FROM node_snapshots_hourly
ORDER BY bucket DESC
LIMIT 8;
```

Zatrzymaj kontener na chwilę (wrócimy do niego):
```bash
docker compose down
# NIE używaj -v — chcemy zachować dane w wolumenie
```

---

## 2.3 Krok 2 — Metryki: Fake DCGM + Prometheus

### Czym jest DCGM

DCGM (Data Center GPU Manager) to demon NVIDIA który zbiera metryki kart GPU z sub-sekundową dokładnością i wystawia je w formacie Prometheus. Wymaga fizycznej karty NVIDIA — lokalnie go nie uruchomimy.

Napiszemy własny exporter w Pythonie który:
- Wystawia te same metryki (te same nazwy, te same etykiety)
- Reaguje na ten sam mechanizm mapowania zadań co prawdziwy DCGM
- Działa bez GPU

### Czym jest Prometheus

Prometheus to system monitorowania działający na zasadzie **pull**: sam co jakiś czas odpytuje (scrapuje) serwisy wystawiające metryki. Przechowuje dane i udostępnia je przez PromQL — język zapytań.

Format metryk który Prometheus rozumie (Prometheus exposition format):

```
# HELP DCGM_FI_DEV_GPU_UTIL GPU utilization (%)
# TYPE DCGM_FI_DEV_GPU_UTIL gauge
DCGM_FI_DEV_GPU_UTIL{gpu_index="0",node="gpu-node-01",slurm_job_id=""} 1.23
DCGM_FI_DEV_GPU_UTIL{gpu_index="1",node="gpu-node-01",slurm_job_id="1003"} 78.45
```

Każda linia: `NAZWA{etykieta="wartość",...} WARTOŚĆ`

### Napisz fake DCGM exporter

```bash
cat > fake-dcgm/exporter.py << 'EOF'
#!/usr/bin/env python3
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
EOF
```

```bash
cat > fake-dcgm/Dockerfile << 'EOF'
FROM python:3.11-slim
WORKDIR /app
COPY exporter.py .
CMD ["python3", "exporter.py"]
EOF
```

### Napisz konfigurację Prometheusa

```bash
cat > prometheus/prometheus.yml << 'EOF'
global:
  scrape_interval: 15s       # odpytuj źródła co 15 sekund
  evaluation_interval: 15s   # ewaluuj reguły alertów co 15 sekund

scrape_configs:
  # Nasz fake DCGM exporter
  - job_name: 'dcgm'
    static_configs:
      - targets: ['fake-dcgm:9400']   # hostname = nazwa serwisu w Compose

  # Prometheus sam się monitoruje
  - job_name: 'prometheus'
    static_configs:
      - targets: ['localhost:9090']
EOF
```

### Rozbuduj docker-compose.yml

Dodaj dwa nowe serwisy do istniejącego pliku. Zastąp jego zawartość:

```bash
cat > docker-compose.yml << 'EOF'
version: '3.8'

services:
  timescaledb:
    image: timescale/timescaledb:latest-pg16
    container_name: eden-timescaledb
    environment:
      POSTGRES_USER: eden
      POSTGRES_PASSWORD: eden
      POSTGRES_DB: eden
    volumes:
      - ./postgres/init.sql:/docker-entrypoint-initdb.d/init.sql
      - timescale-data:/var/lib/postgresql/data
    ports:
      - "5432:5432"
    networks:
      - eden-net
    healthcheck:
      test: ["CMD", "pg_isready", "-U", "eden"]
      interval: 5s
      retries: 10

  fake-dcgm:
    build: ./fake-dcgm
    container_name: eden-fake-dcgm
    volumes:
      - dcgm-mapping:/run/dcgm-exporter/job-mapping:ro   # :ro = tylko do odczytu
    ports:
      - "9400:9400"
    networks:
      - eden-net

  prometheus:
    image: prom/prometheus:latest
    container_name: eden-prometheus
    volumes:
      - ./prometheus/prometheus.yml:/etc/prometheus/prometheus.yml
    ports:
      - "9090:9090"
    networks:
      - eden-net

volumes:
  timescale-data:
  dcgm-mapping:      # wolumin współdzielony: slurm zapisuje, fake-dcgm czyta

networks:
  eden-net:
    driver: bridge
EOF
```

### Uruchom i przetestuj

```bash
docker compose up -d --build fake-dcgm prometheus
```

**Test 1: metryki są dostępne**

```bash
curl http://localhost:9400/metrics
```

Powinieneś zobaczyć ~16 linii z metrykami DCGM. GPU mają `slurm_job_id=""` (brak aktywnych zadań).

**Test 2: Prometheus scrapuje metryki**

Otwórz `http://localhost:9090/targets` w przeglądarce. Serwis `dcgm` powinien mieć status `UP`.

**Test 3: zapytanie PromQL**

Na stronie `http://localhost:9090/graph` wpisz w polu Expression:

```promql
DCGM_FI_DEV_GPU_UTIL
```

Kliknij **Execute**. Zobaczysz 4 wiersze — po jednym na każde GPU.

### Naucz się PromQL

PromQL to język zapytań do metryk Prometheus. Ćwicz w `http://localhost:9090/graph`.

**Filtrowanie po etykiecie:**
```promql
# Tylko GPU numer 0
DCGM_FI_DEV_GPU_UTIL{gpu_index="0"}

# GPU przypisane do aktywnych zadań (etykieta nie jest pusta)
DCGM_FI_DEV_GPU_UTIL{slurm_job_id!=""}

# GPU bezczynne (bez zadania)
DCGM_FI_DEV_GPU_UTIL{slurm_job_id=""}
```

**Agregacje:**
```promql
# Suma poboru mocy wszystkich GPU
sum(DCGM_FI_DEV_POWER_USAGE)

# Średnia utylizacja, pogrupowana po modelu GPU
avg by (modelName) (DCGM_FI_DEV_GPU_UTIL)

# Maksimum temperatury
max(DCGM_FI_DEV_GPU_TEMP)
```

**Funkcje na zakresie czasu:**
```promql
# Wartości z ostatnich 5 minut (range vector — używany z funkcjami)
DCGM_FI_DEV_GPU_UTIL[5m]

# Średnia z ostatnich 10 minut
avg_over_time(DCGM_FI_DEV_GPU_UTIL[10m])

# Maksimum z ostatniej godziny
max_over_time(DCGM_FI_DEV_GPU_UTIL[1h])
```

**Warunki — podstawa alertów:**
```promql
# GPU z utylizacją poniżej 10% przy aktywnym zadaniu
DCGM_FI_DEV_GPU_UTIL{slurm_job_id!=""} < 10

# GPU z temperaturą powyżej 80°C
DCGM_FI_DEV_GPU_TEMP > 80
```

**Test z ręcznym mapowaniem:**

Zasymuluj aktywne zadanie bez Slurma — stwórz plik mapowania ręcznie:

```bash
# Wolumin jest zarządzany przez Docker — musisz wejść do kontenera który go używa
# fake-dcgm ma wolumin :ro, więc użyj pomocniczego kontenera do zapisu
docker run --rm -v eden-stack_dcgm-mapping:/mapping alpine \
  sh -c 'echo "0,1" > /mapping/9999'

# Sprawdź metryki — GPU 0 i 1 powinny mieć slurm_job_id="9999" i wyższe wartości
curl -s http://localhost:9400/metrics | grep GPU_UTIL
```

```promql
# W Prometheus — zapytaj o GPU z aktywnym zadaniem
DCGM_FI_DEV_GPU_UTIL{slurm_job_id!=""}
```

```bash
# Usuń mapowanie — GPU wracają do idle
docker run --rm -v eden-stack_dcgm-mapping:/mapping alpine rm /mapping/9999
```

---

## 2.4 Krok 3 — Wizualizacja: Grafana

### Czym jest Grafana

Grafana to platforma do tworzenia dashboardów. Łączy się ze źródłami danych (Prometheus, PostgreSQL, wiele innych) i pozwala budować wykresy, tabele i alerty przez GUI.

### Konfiguracja automatyczna (provisioning)

Grafana może ładować konfigurację z plików — zamiast klikać przez GUI, opisujesz źródła danych w YAML. Pliki z katalogu `provisioning/` są ładowane automatycznie przy starcie.

```bash
cat > grafana/provisioning/datasources/datasources.yml << 'EOF'
apiVersion: 1

datasources:
  - name: Prometheus
    type: prometheus
    access: proxy
    url: http://prometheus:9090   # hostname = nazwa serwisu Compose
    isDefault: true
    editable: true

  - name: TimescaleDB
    type: postgres
    url: timescaledb:5432
    database: eden
    user: eden
    secureJsonData:
      password: eden
    jsonData:
      sslmode: disable
      postgresVersion: 1600
      timescaledb: true
    editable: true
EOF
```

### Dodaj Grafanę do docker-compose.yml

Dopisz serwis grafana (zastąp cały plik):

```bash
cat > docker-compose.yml << 'EOF'
version: '3.8'

services:
  timescaledb:
    image: timescale/timescaledb:latest-pg16
    container_name: eden-timescaledb
    environment:
      POSTGRES_USER: eden
      POSTGRES_PASSWORD: eden
      POSTGRES_DB: eden
    volumes:
      - ./postgres/init.sql:/docker-entrypoint-initdb.d/init.sql
      - timescale-data:/var/lib/postgresql/data
    ports:
      - "5432:5432"
    networks:
      - eden-net
    healthcheck:
      test: ["CMD", "pg_isready", "-U", "eden"]
      interval: 5s
      retries: 10

  fake-dcgm:
    build: ./fake-dcgm
    container_name: eden-fake-dcgm
    volumes:
      - dcgm-mapping:/run/dcgm-exporter/job-mapping:ro
    ports:
      - "9400:9400"
    networks:
      - eden-net

  prometheus:
    image: prom/prometheus:latest
    container_name: eden-prometheus
    volumes:
      - ./prometheus/prometheus.yml:/etc/prometheus/prometheus.yml
    ports:
      - "9090:9090"
    networks:
      - eden-net

  grafana:
    image: grafana/grafana:latest
    container_name: eden-grafana
    environment:
      GF_SECURITY_ADMIN_USER: admin
      GF_SECURITY_ADMIN_PASSWORD: admin
    volumes:
      - ./grafana/provisioning:/etc/grafana/provisioning
      - grafana-data:/var/lib/grafana
    ports:
      - "3000:3000"
    networks:
      - eden-net
    depends_on:
      - prometheus

volumes:
  timescale-data:
  dcgm-mapping:
  grafana-data:

networks:
  eden-net:
    driver: bridge
EOF
```

```bash
docker compose up -d grafana
```

### Zbuduj dashboard od zera

Otwórz `http://localhost:3000` — login: `admin` / `admin`.

**Krok 1:** Kliknij **Dashboards** (ikona siatki) → **New** → **New dashboard** → **Add visualization**

**Krok 2:** Wybierz źródło danych: **Prometheus**

**Panel 1: Utylizacja GPU w czasie**

W polu "Metric" wpisz: `DCGM_FI_DEV_GPU_UTIL`

Kliknij **Run queries** — zobaczysz 4 linie. Żeby miały czytelne nazwy:
- Rozwiń sekcję **Options**
- W **Legend** wpisz: `GPU {{gpu_index}} ({{modelName}})`

Kliknij **Apply**.

**Panel 2: Pobór mocy**

Dodaj nowy panel. Zapytanie: `sum(DCGM_FI_DEV_POWER_USAGE)`. Tytuł: "Sumaryczny pobór mocy (W)".

**Panel 3: Tabela zadań z PostgreSQL**

Dodaj panel, zmień źródło na **TimescaleDB**. Wpisz SQL:

```sql
SELECT
  start_time  AS "Start",
  username    AS "Użytkownik",
  req_gpus    AS "GPU (dekl.)",
  state       AS "Stan",
  efficiency_score AS "Efektywność (%)",
  avg_gpu_util     AS "Śr. GPU (%)"
FROM job_runs
ORDER BY COALESCE(start_time, NOW()) DESC
LIMIT 20
```

Zmień typ panelu na **Table**.

**Krok 3:** Zapisz dashboard: ikona dyskietki → wpisz nazwę "Eden Monitor".

Ustaw auto-refresh: prawy górny róg → ikona zegara → "5s".

---

## 2.5 Krok 4 — Kolejkowanie: Slurm

To najbardziej złożony komponent. Slurm jest oprogramowaniem HPC które normalnie instaluje się na węzłach obliczeniowych klastra. My uruchomimy go w kontenerze Docker w trybie jednego węzła.

### Architektura Slurma

```
┌─────────────────────────────────────────────────────┐
│              Kontener eden-slurm                    │
│                                                     │
│  munged ─── autentykacja między demonami            │
│     │                                               │
│  slurmdbd ── baza danych zadań ──► MySQL            │
│     │         (slurm_acct_db)    (osobny kontener)  │
│     │                                               │
│  slurmctld ── kontroler klastra                     │
│     │         (przyjmuje sbatch, zarządza kolejką)  │
│     │                                               │
│  slurmd ───── demon węzłowy                         │
│               (uruchamia zadania, wywołuje          │
│                Prolog.sh i Epilog.sh)               │
└─────────────────────────────────────────────────────┘
```

### Utwórz pliki konfiguracyjne Slurma

**slurm.conf** — główna konfiguracja:

```bash
cat > slurm/slurm.conf << 'EOF'
# Nazwa klastra (pojawi się w sacct i nagłówkach)
ClusterName=eden-dev

# Host kontrolera (MUSI pasować do hostname: w docker-compose.yml)
SlurmctldHost=slurm-node

# Podstawowa konfiguracja
MpiDefault=none
ProctrackType=proctrack/pgid      # pgid zamiast cgroup (cgroup wymaga specjalnych uprawnień w Docker)
TaskPlugin=task/none               # bez izolacji zasobów (uproszczenie dla dev)
ReturnToService=2                  # automatycznie odblokuj węzeł po awarii

# Pliki PID i logi
SlurmctldPidFile=/var/run/slurmctld.pid
SlurmdPidFile=/var/run/slurmd.pid
SlurmdSpoolDir=/var/spool/slurmd
StateSaveLocation=/var/spool/slurmctld
SlurmUser=slurm
SlurmctldLogFile=/var/log/slurm/slurmctld.log
SlurmdLogFile=/var/log/slurm/slurmd.log

# RACHUNKOWOŚĆ: połącz z slurmdbd
AccountingStorageType=accounting_storage/slurmdbd
AccountingStorageHost=localhost
AccountingStoragePort=6819

# Kluczowe: śledź faktyczne zużycie GPU w rachunkowości
# Bez tej linii: sacct nie pokaże GresUsed (faktycznie użyte GPU)
AccountingStorageTRES=gres/gpu,cpu,mem

# Monitorowanie zużycia CPU/RAM przez slurmstepd
JobAcctGatherType=jobacct_gather/linux
JobAcctGatherFrequency=30

# GRES: zadeklaruj GPU jako zasób generyczny
GresTypes=gpu

# LIFECYCLE HOOKS: nasze skrypty
Prolog=/opt/eden-monitor/slurm-hooks/prolog.sh
Epilog=/opt/eden-monitor/slurm-hooks/epilog.sh

# Planowanie zadań
SchedulerType=sched/backfill
SelectType=select/cons_tres
SelectTypeParameters=CR_Core

# WĘZEŁ: wartości CPU/pamięci są zastępowane w entrypoint.sh przez
# wynik `slurmd -C` — dopasowanie do rzeczywistego sprzętu kontenera.
# Nie zmieniaj tej linii ręcznie; zmień tylko Gres= jeśli potrzebujesz.
NodeName=slurm-node CPUs=4 RealMemory=8000 Gres=gpu:tesla:4 State=UNKNOWN

# PARTYCJA: kolejka zadań
# Default=YES: jeśli użytkownik nie poda --partition, trafi tutaj
PartitionName=gpu Nodes=slurm-node Default=YES MaxTime=INFINITE State=UP
EOF
```

**slurmdbd.conf** — konfiguracja demona bazy danych:

```bash
cat > slurm/slurmdbd.conf << 'EOF'
AuthType=auth/munge
DbdAddr=localhost
DbdHost=localhost
DbdPort=6819
SlurmUser=slurm
LogFile=/var/log/slurm/slurmdbd.log
PidFile=/var/run/slurmdbd.pid

# Połączenie z MySQL (osobny kontener)
StorageType=accounting_storage/mysql
StorageHost=mysql
StoragePort=3306
StorageUser=slurm
StoragePass=slurm
StorageLoc=slurm_acct_db
EOF
```

**gres.conf** — definicja zasobów generycznych (GPU):

```bash
cat > slurm/gres.conf << 'EOF'
# AutoDetect=off: wyłącz wykrywanie sprzętu przez nvidia-smi
# Konieczne gdy nie ma fizycznych GPU
AutoDetect=off

# Slurm 21.08 (Ubuntu 22.04) wymaga parametru File= żeby prawidłowo
# zarejestrować GPU w slurmctld. Sama opcja Count= bez File= jest ignorowana
# i węzeł trafia w stan inval z błędem "gres/gpu count reported lower than configured".
# Puste pliki placeholder /dev/nvidia[0-3] tworzymy w entrypoint.sh.
Name=gpu Type=tesla File=/dev/nvidia[0-3]
EOF
```

### Napisz skrypt startowy kontenera

```bash
cat > slurm/entrypoint.sh << 'EOF'
#!/bin/bash
set -e

echo "=== Eden Dev: uruchamianie Slurma ==="

# -----------------------------------------------
# 1. MUNGE — autentykacja między demonami Slurma
#    Każdy demon Slurma uwierzytelnia żądania przez
#    kryptograficzne tokeny munge. Bez działającego
#    munged — żadna komunikacja między demonami nie działa.
# -----------------------------------------------
mkdir -p /var/run/munge /var/log/munge
chown munge:munge /var/run/munge

if [ ! -f /etc/munge/munge.key ]; then
    echo "[munge] Generowanie klucza autentykacji..."
    dd if=/dev/urandom bs=1 count=1024 > /etc/munge/munge.key 2>/dev/null
    chown munge:munge /etc/munge/munge.key
    chmod 400 /etc/munge/munge.key
fi

sudo -u munge /usr/sbin/munged --force
sleep 1
echo "[munge] OK"

# -----------------------------------------------
# 2. MYSQL — slurmdbd potrzebuje działającej bazy
#    Czekamy aż MySQL zaakceptuje połączenia
# -----------------------------------------------
echo "[mysql] Czekam na MySQL..."
until mysqladmin ping -h mysql -u slurm -pslurm --silent 2>/dev/null; do
    sleep 2
    echo "[mysql] Czekam..."
done
echo "[mysql] OK"

# -----------------------------------------------
# 3. Katalogi i uprawnienia
# -----------------------------------------------
mkdir -p /var/spool/slurmctld /var/spool/slurmd /var/log/slurm \
         /run/dcgm-exporter/job-mapping
chown slurm:slurm /var/spool/slurmctld /var/spool/slurmd /var/log/slurm

# Utwórz puste pliki logów, żeby tail -f działał zanim pojawi się pierwszy job
touch /var/log/slurm/prolog.log /var/log/slurm/epilog.log

# -----------------------------------------------
# 3b. AUTO-DETEKCJA TOPOLOGII CPU
#
# Slurm wymaga dokładnego dopasowania między slurm.conf a hardware.
# Niezgodność (np. CPUs=4 gdy maszyna ma 10) powoduje stan inval węzła.
# slurmd -C wykrywa rzeczywistą topologię — łatamy slurm.conf w locie,
# żeby konfiguracja pasowała niezależnie od maszyny (Mac, Linux, CI).
# -----------------------------------------------
DETECTED=$(slurmd -C 2>/dev/null | head -1)
if [ -n "$DETECTED" ]; then
    CPUS=$(echo "$DETECTED"    | grep -o 'CPUs=[0-9]*')
    BOARDS=$(echo "$DETECTED"  | grep -o 'Boards=[0-9]*')
    SOCKETS=$(echo "$DETECTED" | grep -o 'SocketsPerBoard=[0-9]*')
    CORES=$(echo "$DETECTED"   | grep -o 'CoresPerSocket=[0-9]*')
    THREADS=$(echo "$DETECTED" | grep -o 'ThreadsPerCore=[0-9]*')
    MEM=$(echo "$DETECTED"     | grep -o 'RealMemory=[0-9]*')
    sed -i "s|^NodeName=slurm-node.*|NodeName=slurm-node $CPUS $BOARDS $SOCKETS $CORES $THREADS $MEM Gres=gpu:tesla:4 State=UNKNOWN|" \
        /etc/slurm/slurm.conf
    echo "[slurm.conf] Topologia CPU: $CPUS $SOCKETS $CORES $THREADS $MEM"
fi

# -----------------------------------------------
# 4. SLURMDBD — demon bazy danych Slurma
#    Musi startować przed slurmctld
# -----------------------------------------------
echo "[slurmdbd] Uruchamianie..."
slurmdbd
sleep 3

# Zainicjuj klaster i użytkownika root w bazie rachunkowości
sacctmgr -i add cluster eden-dev 2>/dev/null || true
sacctmgr -i add account root Description=root Organization=eden 2>/dev/null || true
sacctmgr -i add user root account=root adminlevel=Administrator 2>/dev/null || true
echo "[slurmdbd] OK"

# -----------------------------------------------
# 5. SLURMCTLD — kontroler klastra
#    Zarządza kolejką i przydziela zasoby
# -----------------------------------------------
echo "[slurmctld] Uruchamianie..."
slurmctld
sleep 3
echo "[slurmctld] OK"

# -----------------------------------------------
# 6. SLURMD — demon węzłowy
#    Uruchamia zadania, wywołuje Prolog/Epilog
#
#    gres.conf używa File=/dev/nvidia[0-3]. Tworzymy puste placeholder-y
#    zanim slurmd wystartuje — wystarczy że pliki istnieją; bez fizycznych
#    GPU nie są otwierane.
# -----------------------------------------------
for i in 0 1 2 3; do
    touch /dev/nvidia$i 2>/dev/null || true
done

echo "[slurmd] Uruchamianie..."
slurmd
sleep 2

# Odblokuj węzeł (może być w stanie drain po poprzednim restarcie)
scontrol update NodeName=slurm-node State=IDLE 2>/dev/null || true
echo "[slurmd] OK"

echo ""
echo "============================================"
echo " Slurm gotowy. Przykładowe komendy:"
echo "   sbatch /jobs/gpu_job.sh    # wyślij job"
echo "   squeue                     # kolejka"
echo "   sacct -a                   # historia"
echo "============================================"
echo ""

# Trzymaj kontener przy życiu, streamuj logi Slurma
tail -f /var/log/slurm/slurmctld.log /var/log/slurm/slurmd.log
EOF

chmod +x slurm/entrypoint.sh
```

### Napisz Dockerfile dla Slurma

```bash
cat > slurm/Dockerfile << 'EOF'
FROM ubuntu:22.04

ENV DEBIAN_FRONTEND=noninteractive

# Zainstaluj Slurm, munge i narzędzia pomocnicze
RUN apt-get update && apt-get install -y \
    slurm-wlm \
    slurmdbd \
    munge \
    mysql-client \
    postgresql-client \
    python3 \
    sudo \
    procps \
    && rm -rf /var/lib/apt/lists/*

# Utwórz wymagane katalogi
RUN mkdir -p \
    /var/spool/slurmctld \
    /var/spool/slurmd \
    /var/log/slurm \
    /run/munge \
    /run/dcgm-exporter/job-mapping \
    /opt/eden-monitor/slurm-hooks \
    /jobs \
    && chown slurm:slurm /var/spool/slurmctld /var/spool/slurmd /var/log/slurm

# Skopiuj konfigurację
COPY slurm.conf    /etc/slurm/slurm.conf
COPY slurmdbd.conf /etc/slurm/slurmdbd.conf
COPY gres.conf     /etc/slurm/gres.conf

# slurmdbd.conf musi mieć uprawnienia 600 (zawiera hasło do bazy)
RUN chmod 600 /etc/slurm/slurmdbd.conf

COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

ENTRYPOINT ["/entrypoint.sh"]
EOF
```

### Utwórz przykładowy job

```bash
cat > example-jobs/gpu_job.sh << 'EOF'
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
echo "Symulacja obliczeń przez 40 sekund..."
sleep 40
echo "Obliczenia zakończone."
EOF
```

### Dodaj MySQL i Slurm do docker-compose.yml

Zastąp cały docker-compose.yml finalną wersją:

```bash
cat > docker-compose.yml << 'EOF'
version: '3.8'

services:
  # MySQL dla slurmdbd (bazy rachunkowości Slurma)
  mysql:
    image: mysql:8.0
    container_name: eden-mysql
    environment:
      MYSQL_ROOT_PASSWORD: root
      MYSQL_DATABASE: slurm_acct_db
      MYSQL_USER: slurm
      MYSQL_PASSWORD: slurm
    volumes:
      - mysql-data:/var/lib/mysql
    networks:
      - eden-net
    healthcheck:
      test: ["CMD", "mysqladmin", "ping", "-h", "localhost", "-u", "slurm", "-pslurm"]
      interval: 5s
      timeout: 5s
      retries: 20

  # PostgreSQL + TimescaleDB dla naszej bazy analitycznej
  timescaledb:
    image: timescale/timescaledb:latest-pg16
    container_name: eden-timescaledb
    environment:
      POSTGRES_USER: eden
      POSTGRES_PASSWORD: eden
      POSTGRES_DB: eden
    volumes:
      - ./postgres/init.sql:/docker-entrypoint-initdb.d/init.sql
      - timescale-data:/var/lib/postgresql/data
    ports:
      - "5432:5432"
    networks:
      - eden-net
    healthcheck:
      test: ["CMD", "pg_isready", "-U", "eden"]
      interval: 5s
      retries: 10

  # Slurm: slurmctld + slurmd + slurmdbd w jednym kontenerze
  slurm:
    build: ./slurm
    container_name: eden-slurm
    hostname: slurm-node        # MUSI pasować do NodeName w slurm.conf
    privileged: true            # Slurm potrzebuje zarządzać procesami
    depends_on:
      mysql:
        condition: service_healthy
      timescaledb:
        condition: service_healthy
    volumes:
      # Bind mount katalogu (nie pojedynczych plików!).
      # Docker Desktop na macOS nie potrafi niezawodnie montować
      # pojedynczych plików — tworzy katalog zamiast pliku.
      # Montując cały katalog hooks/ unikamy tego problemu.
      - ./slurm/hooks:/opt/eden-monitor/slurm-hooks
      - ./example-jobs:/jobs
      # Współdzielony wolumin z fake-dcgm
      - dcgm-mapping:/run/dcgm-exporter/job-mapping
    networks:
      - eden-net

  # Symulator metryk GPU
  fake-dcgm:
    build: ./fake-dcgm
    container_name: eden-fake-dcgm
    volumes:
      - dcgm-mapping:/run/dcgm-exporter/job-mapping:ro
    ports:
      - "9400:9400"
    networks:
      - eden-net

  # System zbierania metryk
  prometheus:
    image: prom/prometheus:latest
    container_name: eden-prometheus
    volumes:
      - ./prometheus/prometheus.yml:/etc/prometheus/prometheus.yml
    ports:
      - "9090:9090"
    networks:
      - eden-net

  # Wizualizacja
  grafana:
    image: grafana/grafana:latest
    container_name: eden-grafana
    environment:
      GF_SECURITY_ADMIN_USER: admin
      GF_SECURITY_ADMIN_PASSWORD: admin
    volumes:
      - ./grafana/provisioning:/etc/grafana/provisioning
      - grafana-data:/var/lib/grafana
    ports:
      - "3000:3000"
    networks:
      - eden-net
    depends_on:
      - prometheus

volumes:
  mysql-data:
  timescale-data:
  dcgm-mapping:
  grafana-data:

networks:
  eden-net:
    driver: bridge
EOF
```

### Uruchom i przetestuj Slurm

```bash
docker compose up -d --build slurm
docker compose logs -f slurm
```

Czekaj na komunikat `Slurm gotowy`. Potem:

```bash
# Wejdź do kontenera Slurma
docker exec -it eden-slurm bash

# Sprawdź stan węzła
scontrol show node slurm-node

# Sprawdź partycje
sinfo

# Sprawdź status klastra w rachunkowości
sacctmgr show cluster

# Wyślij zadanie testowe
sbatch /jobs/gpu_job.sh
# Submitted batch job 1

# Obserwuj kolejkę
watch squeue

# Po zakończeniu — historia
sacct -j 1 --format=JobID,JobName,User,State,Elapsed,ReqGRES,ExitCode -X
```

---

## 2.6 Krok 5 — Integracja: Prolog i Epilog

To jest serce całego systemu. Prolog i Epilog łączą Slurm z resztą infrastruktury.

### Jak działają

Gdy `slurmd` uruchamia zadanie:
1. Wywołuje `prolog.sh` jako root — musi zwrócić `exit 0`
2. Uruchamia zadanie użytkownika
3. Gdy zadanie się kończy: wywołuje `epilog.sh` jako root
4. Zwalnia zasoby dla kolejnego zadania

**Kluczowe zmienne środowiskowe dostępne w Prologu:**

| Zmienna | Przykład | Opis |
|---|---|---|
| `SLURM_JOB_ID` | `42` | Unikalny ID zadania |
| `SLURM_JOB_USER` | `jan.kowalski` | Użytkownik |
| `SLURM_JOB_GPUS` | `0,2` | Indeksy przydzielonych GPU |
| `SLURM_JOB_PARTITION` | `gpu` | Partycja |
| `SLURM_JOB_START_TIME` | `1715000000` | Czas startu (epoch) |
| `SLURM_JOB_SUBMIT_TIME` | `1714999990` | Czas zgłoszenia (epoch) |

W Epilogu dodatkowo:

| Zmienna | Przykład | Opis |
|---|---|---|
| `SLURM_JOB_END_TIME` | `1715001000` | Czas zakończenia (epoch) |
| `SLURM_JOB_EXIT_CODE` | `0:0` | Kod wyjścia (kod:sygnał) |

### Napisz Prolog

```bash
cat > slurm/hooks/prolog.sh << 'EOF'
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
EOF
```

### Napisz Epilog

```bash
cat > slurm/hooks/epilog.sh << 'EOF'
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
EOF
```

### Przeładuj konfigurację Slurma

Katalog `slurm/hooks/` jest zamontowany jako bind mount — zmiany plików `prolog.sh` i `epilog.sh` na hoście są natychmiast widoczne w kontenerze bez przebudowy obrazu. Ale Slurm musi wiedzieć o zmianach w konfiguracji:

```bash
docker exec eden-slurm scontrol reconfigure
```

Sprawdź czy Prolog i Epilog są zarejestrowane:

```bash
docker exec eden-slurm scontrol show config | grep -E "Prolog|Epilog"
```

Powinieneś zobaczyć:
```
Epilog                  = /opt/eden-monitor/slurm-hooks/epilog.sh
Prolog                  = /opt/eden-monitor/slurm-hooks/prolog.sh
```

---

# Część 3: Weryfikacja i debugowanie

## 3.1 Pełny przepływ danych end-to-end

### Przygotowanie — otwórz 4 terminale

**Terminal A — obserwuj kolejkę Slurma:**
```bash
watch -n1 'docker exec eden-slurm squeue -o "%.6i %.8u %.8j %.8T %.6M"'
```

**Terminal B — obserwuj mapowania DCGM:**
```bash
watch -n1 'echo "Pliki mapowania:" && docker exec eden-slurm ls -la /run/dcgm-exporter/job-mapping/'
```

**Terminal C — obserwuj metryki GPU:**
```bash
watch -n2 'curl -s http://localhost:9400/metrics | grep "GPU_UTIL" | grep -v "^#"'
```

**Terminal D — obserwuj logi Prolog/Epilog:**
```bash
# Pliki logów są tworzone automatycznie przez entrypoint.sh przy starcie.
# Jeśli mimo to tail zgłosi "No such file" — utwórz je ręcznie:
# docker exec eden-slurm touch /var/log/slurm/prolog.log /var/log/slurm/epilog.log
docker exec eden-slurm tail -f /var/log/slurm/prolog.log /var/log/slurm/epilog.log
```

### Wyślij zadanie i obserwuj

W nowym terminalu:

```bash
docker exec eden-slurm sbatch /jobs/gpu_job.sh
```

Co powinieneś obserwować po kolei:

**Natychmiast:**
- Terminal A: job pojawia się jako `PENDING`, potem `RUNNING`
- Terminal D: `[prolog] START job=X user=root gpus=0`
- Terminal D: `[prolog] Mapowanie DCGM: job=X → GPU=0`
- Terminal B: pojawia się plik `X` w katalogu mapowania

**Po ~15 sekundach (następny scrape Prometheusa):**
- Terminal C: GPU 0 ma wyższe wartości i `slurm_job_id="X"`

**Po 40 sekundach (koniec zadania):**
- Terminal A: job znika z kolejki
- Terminal D: `[epilog] END job=X`
- Terminal B: plik `X` znika z katalogu mapowania
- Terminal C: GPU 0 wraca do idle (`slurm_job_id=""`)

**Po ~50 sekundach (scorer w tle):**
- Terminal D: `[scorer] job=X score=XX`

### Sprawdź PostgreSQL

```bash
docker exec -it eden-timescaledb psql -U eden -d eden -c \
  "SELECT slurm_job_id, username, state, efficiency_score FROM job_runs ORDER BY created_at DESC LIMIT 5;"
```

### Sprawdź sacct — historia w Slurm

```bash
docker exec eden-slurm sacct -a \
  --format=JobID,User,State,Elapsed,ReqGRES,GresUsed,ExitCode -X
```

### Ćwiczenie: rozkaz Prolog żeby zawiódł

**WAŻNE:** To pokazuje dlaczego Prolog musi zwracać 0.

Zmień `exit 0` na `exit 1` na końcu `slurm/hooks/prolog.sh`. Potem:

```bash
docker exec eden-slurm scontrol reconfigure
docker exec eden-slurm sbatch /jobs/gpu_job.sh
```

Obserwuj w Terminal A — job przechodzi w stan `FAILED` natychmiast. Sprawdź stan węzła:

```bash
docker exec eden-slurm scontrol show node slurm-node | grep "State="
```

Węzeł powinien być w stanie `DRAIN` lub `DOWN` — Slurm go zablokował!

Napraw:
1. Przywróć `exit 0` w `prolog.sh`
2. Odblokuj węzeł:

```bash
docker exec eden-slurm scontrol update NodeName=slurm-node State=RESUME
```

---

## 3.2 Co zrobić gdy coś nie działa

### Kontener Slurm nie startuje

```bash
docker compose logs slurm | tail -50
```

Najczęstsze przyczyny:
- MySQL nie jest gotowa — entrypoint czeka, ale może być timeout
- Błąd w `slurm.conf` — sprawdź: `docker exec eden-slurm slurmd -D -vvv 2>&1 | head -30`

### Węzeł w stanie drain/down

```bash
docker exec eden-slurm sinfo    # sprawdź stan
docker exec eden-slurm scontrol update NodeName=slurm-node State=IDLE
```

### Prolog nie wykonuje się

```bash
# Sprawdź czy ścieżki są poprawne
docker exec eden-slurm scontrol show config | grep -E "Prolog|Epilog"

# Sprawdź czy skrypt jest wykonywalny
docker exec eden-slurm ls -la /opt/eden-monitor/slurm-hooks/
```

### Fake DCGM nie taguje metryk job_id

```bash
# Sprawdź czy wolumin jest zamontowany w obu kontenerach
docker inspect eden-slurm | grep -A3 dcgm-mapping
docker inspect eden-fake-dcgm | grep -A3 dcgm-mapping

# Sprawdź czy plik mapowania istnieje (podczas działającego joba)
docker exec eden-slurm ls /run/dcgm-exporter/job-mapping/
```

### PostgreSQL nie przyjmuje połączeń z Prologu

```bash
# Test połączenia z kontenera Slurma
docker exec eden-slurm pg_isready -h timescaledb -U eden

# Sprawdź log Prologu
docker exec eden-slurm cat /var/log/slurm/prolog.log
```

### Węzeł w stanie `inval` — błąd topologii CPU

```
error: Setting node slurm-node state to DRAIN with reason:gres/gpu count reported lower than configured (0 < 4)
```

Dwa możliwe powody:

**a) Topologia CPU niezgodna z hardware** — `entrypoint.sh` powinien to wykryć i naprawić automatycznie. Jeśli problem nadal występuje:

```bash
# Sprawdź rzeczywistą topologię sprzętu
docker exec eden-slurm slurmd -C

# Wynik wyglądać tak:
# NodeName=slurm-node CPUs=10 Boards=1 SocketsPerBoard=1 CoresPerSocket=10 ...
# Porównaj z NodeName= w /etc/slurm/slurm.conf
docker exec eden-slurm grep NodeName /etc/slurm/slurm.conf
```

**b) Brak plików `/dev/nvidiaX`** — `entrypoint.sh` tworzy je przed startem slurmd. Sprawdź czy istnieją:

```bash
docker exec eden-slurm ls -la /dev/nvidia{0,1,2,3}
```

Jeśli nie ma — wejdź do kontenera i utwórz ręcznie:
```bash
docker exec eden-slurm bash -c 'for i in 0 1 2 3; do touch /dev/nvidia$i; done'
docker exec eden-slurm scontrol update NodeName=slurm-node State=RESUME
```

### Skrypty hook widoczne jako katalogi (`d?????????`) — macOS

Docker Desktop na macOS nie potrafi niezawodnie bind-mountować pojedynczych plików — montuje katalog zamiast pliku. Objaw: `Operation not permitted` przy próbie odczytu.

Tutorial używa `./slurm/hooks:/opt/eden-monitor/slurm-hooks` (katalog, nie pliki) właśnie po to, żeby uniknąć tego problemu. Jeśli jednak kopiowałeś komendy ze starszej wersji tutoriala z indywidualnymi mountami, zaktualizuj `docker-compose.yml`.

### Pełny reset środowiska

```bash
docker compose down -v    # zatrzymaj i usuń WSZYSTKIE wolumeny
docker compose up -d --build
```

---

## 3.3 Co dalej — samodzielne rozbudowanie systemu

Masz działający szkielet. Poniżej konkretne zadania do samodzielnej implementacji.

### Zadanie A: Prawdziwy Efficiency Scorer

Zastąp placeholder losowego score w Epilogu prawdziwym skryptem Python.

#### Krok 1 — Utwórz `slurm/hooks/efficiency_scorer.py`

Skrypt musi być w `slurm/hooks/` — to katalog zamontowany jako bind mount do kontenera (`/opt/eden-monitor/slurm-hooks/`), nie w `slurm/`.

```python
#!/usr/bin/env python3
"""
Oblicza efficiency score zadania Slurm.
Uruchamiany z Epilogu: python3 efficiency_scorer.py JOB_ID DURATION_SECONDS
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
      (jeśli util < 50%, zakładamy że 1 GPU wystarczyłoby)
    """
    if avg_util is None:
        return None
    score = avg_util
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
```

#### Krok 2 — Dodaj biblioteki do `slurm/Dockerfile`

Dodaj `python3-pip` do listy pakietów i zainstaluj zależności w tej samej warstwie:

```dockerfile
RUN apt-get update && apt-get install -y \
    slurm-wlm \
    slurmdbd \
    munge \
    mysql-client \
    postgresql-client \
    python3 \
    python3-pip \
    sudo \
    procps \
    && pip3 install --no-cache-dir psycopg2-binary requests \
    && rm -rf /var/lib/apt/lists/*
```

#### Krok 3 — Zaktualizuj sekcję `# 3.` w `slurm/hooks/epilog.sh`

Zastąp blok z losowym score:

```bash
# =============================================================
# 3. OBLICZ EFFICIENCY SCORE (synchronicznie)
#
# Scorer odpytuje Prometheus i aktualizuje job_runs w PostgreSQL.
# Uruchamiamy synchronicznie — Docker bez pełnego init (np. tini)
# ubija procesy w tle przed zakończeniem ich działania.
# =============================================================
DURATION=$(( ${SLURM_JOB_END_TIME:-0} - ${SLURM_JOB_START_TIME:-0} ))

echo "[scorer] $(date -Iseconds) Obliczam score dla job=$SLURM_JOB_ID" >> "$LOG_FILE"
python3 /opt/eden-monitor/slurm-hooks/efficiency_scorer.py \
    "$SLURM_JOB_ID" "$DURATION" >> "$LOG_FILE" 2>&1

echo "[epilog] OK job=$SLURM_JOB_ID" >> "$LOG_FILE"
```

> **Uwaga o uruchamianiu w tle:** Tutorial sugeruje `( ... ) &`. W Docker bez `tini` jako PID 1 procesy osierocone są ubijane gdy epilog kończy pracę — `setsid` nie pomaga. Scorer synchroniczny działa niezawodnie kosztem kilku sekund opóźnienia przed zwolnieniem węzła.

#### Krok 4 — Przebuduj i przetestuj

```bash
docker compose up -d --build slurm
docker exec eden-slurm sbatch /jobs/gpu_job.sh
docker exec eden-slurm tail -f /var/log/slurm/epilog.log
```

Oczekiwany wynik:
```
[epilog] ... END job=X user=root exit=0:0
[epilog] Usunięto mapowanie DCGM dla job=X
[scorer] ... Obliczam score dla job=X
[scorer] job=X score=61 avg_util=61.1%
[epilog] OK job=X
```

### Zadanie B: Snapshot Writer

Serwis który co 5 minut pobiera metryki z Prometheus i wstawia do `node_snapshots`. Działa jako **osobny kontener** — nie wewnątrz Slurma.

#### Krok 1 — Utwórz `snapshot-writer/snapshot_writer.py`

```python
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
```

#### Krok 2 — Utwórz `snapshot-writer/Dockerfile`

```dockerfile
FROM python:3.11-slim
RUN pip install --no-cache-dir psycopg2-binary requests
ENV PYTHONUNBUFFERED=1
WORKDIR /app
COPY snapshot_writer.py .
CMD ["python3", "snapshot_writer.py"]
```

#### Krok 3 — Dodaj serwis do `docker-compose.yml`

```yaml
  snapshot-writer:
    build: ./snapshot-writer
    container_name: eden-snapshot-writer
    networks:
      - eden-net
    depends_on:
      timescaledb:
        condition: service_healthy
      prometheus:
        condition: service_started
    restart: unless-stopped
```

```bash
docker compose up -d --build snapshot-writer
docker compose logs snapshot-writer
# Snapshot writer startuje...
# Zapisano snapshot (4 GPU).
```

### Zadanie C: Alert w Prometheusie

Utwórz `prometheus/alerts.yml`:

```yaml
groups:
  - name: gpu_efficiency
    rules:
      - alert: IdleGPUWithActiveJob
        expr: DCGM_FI_DEV_GPU_UTIL{slurm_job_id!=""} < 5
        for: 10m
        labels:
          severity: warning
        annotations:
          summary: "GPU {{ $labels.gpu_index }} bezczynne przy aktywnym zadaniu"
          description: "Job {{ $labels.slurm_job_id }} używa GPU na {{ $value }}% przez ostatnie 10 minut"

      - alert: GPUOverheating
        expr: DCGM_FI_DEV_GPU_TEMP > 85
        for: 5m
        labels:
          severity: critical
        annotations:
          summary: "GPU {{ $labels.gpu_index }} przegrzewa się ({{ $value }}°C)"
```

Dodaj do `prometheus/prometheus.yml`:
```yaml
rule_files:
  - /etc/prometheus/alerts.yml
```

Zaktualizuj wolumen Prometheusa w `docker-compose.yml`:
```yaml
volumes:
  - ./prometheus/prometheus.yml:/etc/prometheus/prometheus.yml
  - ./prometheus/alerts.yml:/etc/prometheus/alerts.yml
```

### Zadanie D: FastAPI backend

Utwórz nowy serwis `api/` z FastAPI który wystawia dane z PostgreSQL jako REST API. Endpointy:
- `GET /api/jobs` — ostatnie 50 zadań
- `GET /api/jobs/{job_id}` — szczegóły zadania
- `GET /api/stats` — statystyki klastra (aktywne GPU, zadania w kolejce)

Podpowiedź do `docker-compose.yml`:
```yaml
api:
  build: ./api
  ports:
    - "8000:8000"
  networks:
    - eden-net
  depends_on:
    timescaledb:
      condition: service_healthy
```

---

## Podsumowanie — co zbudowałeś

```
sbatch gpu_job.sh
    │
    ▼
slurmctld  →  przydziela GPU 0 do job_id=X
    │
    ▼
slurmd  →  wywołuje prolog.sh
    │
    ├──► tworzy /run/dcgm-exporter/job-mapping/X = "0"
    │         │
    │         ▼
    │    fake-dcgm czyta plik
    │    metryki GPU 0 dostają etykietę slurm_job_id="X"
    │         │
    │         ▼
    │    Prometheus scrapuje co 15s
    │    metryki w bazie TSDB z etykietą slurm_job_id="X"
    │         │
    │         ▼
    │    Grafana wyświetla wykres utylizacji dla job X
    │
    ├──► INSERT INTO job_runs (job_id=X, state=RUNNING)
    │
    ▼
uruchamia zadanie użytkownika (sleep 40)
    │
    ▼  (po 40 sekundach)
slurmd  →  wywołuje epilog.sh
    │
    ├──► usuwa /run/dcgm-exporter/job-mapping/X
    │    (metryki GPU wracają do slurm_job_id="")
    │
    ├──► UPDATE job_runs SET state=COMPLETED
    │
    └──► (w tle &) oblicza efficiency_score
         UPDATE job_runs SET efficiency_score=73

slurmd  →  zwalnia GPU dla kolejnego zadania
```

---

*Tutorial przygotowany przez Koło Naukowe Data Science, MiNI PW.*

*Masz pytanie? Coś nie działa? Sprawdź sekcję [3.2 Co zrobić gdy coś nie działa](#32-co-zrobić-gdy-coś-nie-działa)*

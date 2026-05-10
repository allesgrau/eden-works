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
    python3-pip \
    sudo \
    procps \
    && pip3 install --no-cache-dir psycopg2-binary requests \
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

# Ustaw właściciela plików konfiguracyjnych na slurm
RUN chown slurm:slurm /etc/slurm/slurm.conf /etc/slurm/slurmdbd.conf /etc/slurm/gres.conf

# slurmdbd.conf musi mieć uprawnienia 600 (zawiera hasło do bazy)
RUN chmod 600 /etc/slurm/slurmdbd.conf

COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

ENTRYPOINT ["/entrypoint.sh"]

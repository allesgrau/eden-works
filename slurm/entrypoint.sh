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
# slurmd -C wykrywa rzeczywistą topologię — łatamy slurm.conf w locie.
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
#    Slurm 21.08 wymaga File=/dev/nvidiaX w gres.conf.
#    Tworzymy puste pliki placeholder zanim slurmd ostartuje —
#    wystarczy że istnieją; bez prawdziwych GPU nie są czytane.
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

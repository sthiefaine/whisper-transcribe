FROM ubuntu:22.04

# Variables d'environnement
ENV DEBIAN_FRONTEND=noninteractive
ENV WHISPER_PATH=/opt/whisper.cpp
ENV MODEL_NAME=large-v3
ENV MODEL_PATH=${WHISPER_PATH}/models/ggml-${MODEL_NAME}.bin

# Installation des dépendances système
RUN apt-get update && apt-get install -y \
    build-essential \
    cmake \
    git \
    wget \
    curl \
    python3 \
    python3-pip \
    python3-venv \
    ffmpeg \
    && rm -rf /var/lib/apt/lists/*

# Cloner whisper.cpp
RUN git clone https://github.com/ggerganov/whisper.cpp.git ${WHISPER_PATH}

# Compiler whisper.cpp
WORKDIR ${WHISPER_PATH}
RUN make && \
    ls -la build/bin/ && \
    echo "✅ Whisper.cpp compilé avec succès"

# Télécharger le modèle MODEL_NAME avec retry
RUN for i in 1 2 3; do \
        echo "Tentative $i de téléchargement du modèle ${MODEL_NAME}..."; \
        bash ./models/download-ggml-model.sh ${MODEL_NAME} && break; \
        echo "Échec du téléchargement, nouvelle tentative..."; \
        sleep 5; \
    done

# Créer un environnement virtuel Python
RUN python3 -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Installer les dépendances Python
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copier le script serveur
COPY server.py .

# Créer un utilisateur non-root
RUN useradd -m -u 1000 whisper && \
    chown -R whisper:whisper ${WHISPER_PATH}

# Créer les dossiers de logs et work avec les bons droits
RUN mkdir -p /var/log/whisper /var/log/whisper/work && \
    chmod 777 /var/log/whisper /var/log/whisper/work

USER whisper

EXPOSE 8080

HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8080/health || exit 1

# Configuration pour éviter l'OOM killer
RUN echo 'vm.overcommit_memory=1' >> /etc/sysctl.conf || true
RUN echo 'vm.oom_kill_allocating_task=1' >> /etc/sysctl.conf || true

# Script de lancement robuste
COPY <<EOF /opt/start.sh
#!/bin/bash
set -e

# Augmenter les limites de processus
ulimit -c unlimited
ulimit -n 65536

# Configurer la mémoire virtuelle si possible
echo 1 > /proc/sys/vm/overcommit_memory 2>/dev/null || true

# Fonction de monitoring en arrière-plan
monitor_memory() {
    while true; do
        memory_usage=\$(cat /proc/meminfo | grep MemAvailable | awk '{print \$2}')
        if [ \$memory_usage -lt 1048576 ]; then  # Less than 1GB available
            echo "WARNING: Low memory detected: \${memory_usage}KB available"
        fi
        sleep 60
    done
}

# Lancer le monitoring en arrière-plan
monitor_memory &
MONITOR_PID=\$!

# Fonction de nettoyage
cleanup() {
    echo "Cleaning up..."
    kill \$MONITOR_PID 2>/dev/null || true
    exit 0
}

trap cleanup SIGTERM SIGINT

# Lancer l'application principale
exec python3 server.py
EOF

RUN chmod +x /opt/start.sh

CMD ["/opt/start.sh"]

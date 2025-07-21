FROM ubuntu:22.04

# Variables d'environnement
ENV DEBIAN_FRONTEND=noninteractive
ENV WHISPER_PATH=/opt/whisper.cpp
ENV MODEL_NAME=large-v3-turbo-q8_0
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

# Télécharger le modèle large-v3-turbo-q8_0 avec retry
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

# Créer le dossier de logs avec les bons droits
RUN mkdir -p /var/log/whisper && chmod 777 /var/log/whisper

USER whisper

EXPOSE 8080

HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8080/health || exit 1

CMD ["python3", "server.py"]

FROM nginx:alpine

# Supprimer la configuration par défaut qui cause des conflits
RUN rm -f /etc/nginx/conf.d/default.conf

# Créer les dossiers nécessaires avec les bonnes permissions
RUN mkdir -p /var/log/whisper && \
    mkdir -p /var/cache/nginx && \
    mkdir -p /run && \
    chmod -R 777 /var/log/whisper && \
    chmod -R 777 /var/cache/nginx && \
    chmod 777 /run

# Copier la configuration nginx
COPY nginx.conf /etc/nginx/nginx.conf

# Exposer le port
EXPOSE 80

# Démarrer nginx
CMD ["nginx", "-g", "daemon off;"]


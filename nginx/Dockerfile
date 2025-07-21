FROM nginx:alpine

RUN addgroup -S whisper && adduser -S whisper -G whisper

RUN mkdir -p /var/log/whisper && chown -R whisper:whisper /var/log/whisper && chmod -R 777 /var/log/whisper

RUN mkdir -p /var/cache/nginx && chmod -R 777 /var/cache/nginx

COPY nginx.conf /etc/nginx/nginx.conf

USER whisper


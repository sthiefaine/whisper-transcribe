FROM nginx:alpine

RUN addgroup -S whisper && adduser -S whisper -G whisper

COPY nginx.conf /etc/nginx/nginx.conf

USER whisper


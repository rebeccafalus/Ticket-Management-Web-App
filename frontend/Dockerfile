FROM nginxinc/nginx-unprivileged:1.29.3-alpine3.22

USER root

RUN apk upgrade --no-cache

COPY --chown=101:101 index.html /usr/share/nginx/html/index.html

USER 101

EXPOSE 8080
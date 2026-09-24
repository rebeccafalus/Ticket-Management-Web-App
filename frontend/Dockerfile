FROM nginxinc/nginx-unprivileged:1.29.3-alpine3.22

USER root
RUN apk upgrade --no-cache
USER 101

COPY --chown=101:101 index.html /usr/share/nginx/html/index.html

EXPOSE 8080
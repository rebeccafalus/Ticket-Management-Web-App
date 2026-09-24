FROM nginx:1.29.3-alpine3.22

RUN apk upgrade --no-cache

COPY index.html /usr/share/nginx/html/index.html

# Create non-root user
RUN addgroup -S app && \
    adduser -S app -G app

# Use non-privileged port
RUN sed -i 's/listen       80;/listen       8080;/' /etc/nginx/conf.d/default.conf

RUN chown -R app:app \
    /usr/share/nginx/html \
    /var/cache/nginx \
    /var/log/nginx \
    /etc/nginx

USER app

EXPOSE 8080
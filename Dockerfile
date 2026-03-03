
FROM python:3.11-alpine AS builder

RUN apk add --no-cache \
    gcc \
    musl-dev \
    libsodium-dev \
    curl

COPY requirements.txt .

ENV PYTHONUSERBASE=/app/.local
RUN pip install --no-cache-dir --user --no-warn-script-location \
    --no-compile \
    -r requirements.txt

FROM python:3.11-alpine

COPY --from=builder /app/.local /app/.local
ENV PATH=/app/.local/bin:$PATH \
    PYTHONUSERBASE=/app/.local

RUN apk add --no-cache \
    curl \
    supervisor \
    libsodium \
    libsodium-dev \
    bash \
    && rm -rf /var/cache/apk/*

RUN adduser -D -u 1000 appuser

RUN mkdir -p /var/log/supervisor /etc/supervisor/conf.d /data /app /var/run/supervisor

COPY supervisord-agent.conf /etc/supervisor/conf.d/
COPY supervisord-console.conf /etc/supervisor/conf.d/
COPY syncer.sh /syncer.sh
COPY entrypoint.sh /entrypoint.sh
COPY app/ /app/

RUN chmod +x /syncer.sh /entrypoint.sh && \
    chown -R appuser:appuser /data /var/log/supervisor /app /etc/supervisor/conf.d /app/.local /var/run/supervisor

WORKDIR /app

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

ENTRYPOINT ["/entrypoint.sh"]
CMD ["console"]
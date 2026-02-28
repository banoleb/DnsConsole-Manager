FROM python:3.11-slim

RUN apt-get update && apt-get install -y \
    gcc \
    curl \
    libsodium-dev \
    supervisor

RUN  apt-get clean && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .

RUN pip install --no-cache-dir -r requirements.txt

RUN mkdir -p /var/log/supervisor /etc/supervisor/conf.d
COPY supervisord-agent.conf /etc/supervisor/conf.d/supervisord-agent.conf
COPY supervisord-console.conf /etc/supervisor/conf.d/supervisord-console.conf

COPY syncer.sh .
RUN chmod +x /syncer.sh

RUN mkdir -p /data
WORKDIR /app
COPY app/ .

COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

ENV PYTHONUNBUFFERED=1

ENTRYPOINT ["/entrypoint.sh"]

CMD ["console"]

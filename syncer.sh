#!/bin/bash

HOST="${CONSOLE_HOST:-127.0.0.1}"
PORT="${CONSOLE_port:-5000}"
TOKEN="${DNSDIST_SYNCER_TOKEN}"
echo "start sync worker $HOST:$PORT"
while true; do
    curl --silent --output /dev/null -H "Authorization: Bearer $TOKEN" -X GET "http://$HOST:$PORT/api/startsync"
    sleep 10
done

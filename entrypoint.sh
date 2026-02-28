#!/bin/bash
set -e

# Default command is console
COMMAND="${1:-console}"

case "$COMMAND" in
    agent)
        echo "Starting dnsdist Web API Server..."
        exec /usr/bin/supervisord -c "/etc/supervisor/conf.d/supervisord-agent.conf"
        ;;
    console)
        echo "Starting dnsdist Web Console..."
        exec /usr/bin/supervisord -c "/etc/supervisor/conf.d/supervisord-console.conf"
        ;;
    *)
esac

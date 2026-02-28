#!/usr/bin/env python3
"""
WSGI entry point for dnsdist Web Console

This module provides the WSGI application interface for production deployment
using Gunicorn or other WSGI servers.

Usage with Gunicorn (4 workers):
    gunicorn --workers 4 --bind 0.0.0.0:5000 wsgi:app

The application can also be configured via environment variables:
    - CONSOLE_HOST: Host to bind to (default: 0.0.0.0)
    - CONSOLE_PORT: Port to listen on (default: 5000)
    - DATABASE_URL: Database connection string
    - LOG_LEVEL: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)

Note: In a multi-worker setup, each worker imports this module and gets
its own app instance with its own database connection. This is correct
behavior for WSGI applications.
"""

import logging

# Set up basic logging before importing app
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

try:
    from console import app
except Exception as e:
    logger.error(f"Failed to initialize application: {e}")
    logger.error("Please check your configuration and database connectivity")
    # Re-raise the exception so Gunicorn knows initialization failed
    raise

if __name__ == "__main__":
    # This allows running the app directly for development
    # For production, use: gunicorn wsgi:app
    from settings import settings
    app.run(
        host=settings.CONSOLE_HOST,
        port=settings.CONSOLE_PORT,
        debug=settings.DEBUG
    )

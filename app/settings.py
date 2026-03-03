#!/usr/bin/env python3
"""
Configuration settings for dnsdist Web API
All settings can be overridden via environment variables
"""

import logging
import os


class Settings:
    """Configuration settings with defaults and environment variable support"""
    TIMEOUT_AGENT = int(os.environ.get('TIMEOUT_AGENT', 3))
    # Web API Server settings
    WEBAPI_PORT = int(os.environ.get('WEBAPI_PORT', '8080'))
    WEBAPI_HOST = os.environ.get('WEBAPI_HOST', '0.0.0.0')

    # Console settings
    CONSOLE_PORT = int(os.environ.get('CONSOLE_PORT', '5000'))
    CONSOLE_HOST = os.environ.get('CONSOLE_HOST', '0.0.0.0')

    # DNSDist console connection settings
    DNSDIST_CONSOLE_HOST = os.environ.get('DNSDIST_CONSOLE_HOST', '127.0.0.1')
    DNSDIST_CONSOLE_PORT = int(os.environ.get('DNSDIST_CONSOLE_PORT', '5199'))
    DNSDIST_KEY = os.environ.get('DNSDIST_KEY')  # Encryption key for console (optional)

    # Authentication settings
    WEBAPI_TOKEN = os.environ.get('WEBAPI_TOKEN')  # Web API authentication token (optional)

    # Database settings
    DATABASE_URL = os.environ.get('DATABASE_URL', 'sqlite:///dnsdist_webapi.db')
    # DATABASE_URL = os.environ.get('DATABASE_URL', 'postgresql://psqlmaster:psqlmaster@192.168.0.160/distapi')

    # Logging settings
    LOG_LEVEL = os.environ.get('LOG_LEVEL', 'INFO').upper()
    LOG_FORMAT = os.environ.get('LOG_FORMAT', '%(asctime)s - %(name)s - %(levelname)s - %(message)s')

    # Debug mode
    DEBUG = os.environ.get('DEBUG', 'false').lower() in ('true', '1', 'yes')

    # Victoria Metrics settings
    VICTORIA_METRICS_ENABLED = os.environ.get('VICTORIA_METRICS_ENABLED', 'false').lower() in ('true', '1', 'yes')
    VICTORIA_METRICS_HOST = os.environ.get('VICTORIA_METRICS_HOST', 'localhost')
    VICTORIA_METRICS_PORT = int(os.environ.get('VICTORIA_METRICS_PORT', '8428'))
    VICTORIA_METRICS_URL = os.environ.get('VICTORIA_METRICS_URL', '/api/v1/import/prometheus')

    @classmethod
    def get_log_level(cls):
        """Get the logging level object from the LOG_LEVEL setting"""
        level_map = {
            'DEBUG': logging.DEBUG,
            'INFO': logging.INFO,
            'WARNING': logging.WARNING,
            'ERROR': logging.ERROR,
            'CRITICAL': logging.CRITICAL
        }
        return level_map.get(cls.LOG_LEVEL, logging.INFO)

    @classmethod
    def configure_logging(cls):
        """Configure logging based on settings"""
        logging.basicConfig(
            level=cls.get_log_level(),
            format=cls.LOG_FORMAT
        )

settings = Settings()

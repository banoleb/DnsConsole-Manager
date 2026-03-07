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

    # -------------------------------------------------------------------------
    # Authentication settings
    # -------------------------------------------------------------------------

    # Web API token (legacy, optional)
    WEBAPI_TOKEN = os.environ.get('WEBAPI_TOKEN')

    # Flask session secret key – MUST be changed in production
    SECRET_KEY = os.environ.get('SECRET_KEY', 'change-me-in-production')

    # Local username/password authentication
    # Set AUTH_ENABLED=false to disable the login form entirely (e.g. when
    # using OIDC as the sole auth method or running in a fully-trusted network).
    AUTH_ENABLED = os.environ.get('AUTH_ENABLED', 'true').lower() in ('true', '1', 'yes')

    # -------------------------------------------------------------------------
    # OpenID Connect (OIDC / OAuth 2.0) SSO settings
    # -------------------------------------------------------------------------
    # Set OIDC_ENABLED=true to activate SSO via any OpenID Connect provider
    # (e.g. Keycloak, Azure AD, Google, Okta, Authentik …).
    OIDC_ENABLED = os.environ.get('OIDC_ENABLED', 'false').lower() in ('true', '1', 'yes')

    # Base URL of the OIDC provider.
    # The discovery document is fetched from <OIDC_PROVIDER_URL>/.well-known/openid-configuration
    # Examples:
    #   Keycloak : https://sso.example.com/realms/myrealm
    #   Google   : https://accounts.google.com
    #   Azure AD : https://login.microsoftonline.com/<tenant-id>/v2.0
    OIDC_PROVIDER_URL = os.environ.get('OIDC_PROVIDER_URL', '')

    # OAuth 2.0 client credentials (register your app in the OIDC provider)
    OIDC_CLIENT_ID = os.environ.get('OIDC_CLIENT_ID', '')
    OIDC_CLIENT_SECRET = os.environ.get('OIDC_CLIENT_SECRET', '')

    # Full redirect URI that the provider will call after authentication.
    # Must match the redirect URI registered in the OIDC provider exactly.
    # Example: http://dnsconsole.example.com/auth/callback
    OIDC_REDIRECT_URI = os.environ.get('OIDC_REDIRECT_URI', '')

    # Space-separated list of OIDC scopes to request.
    # 'openid' is required; add 'groups' or provider-specific scopes as needed.
    OIDC_SCOPES = os.environ.get('OIDC_SCOPES', 'openid email profile')

    # Optional: name of the claim in the ID token / userinfo response that
    # contains the list of groups the user belongs to.
    # Common values: 'groups' (Keycloak, Authentik), 'roles', 'group_membership'
    OIDC_GROUPS_CLAIM = os.environ.get('OIDC_GROUPS_CLAIM', 'groups')

    # Optional: if non-empty, only users that belong to this group (as reported
    # by OIDC_GROUPS_CLAIM) are allowed to log in.
    # Example: OIDC_REQUIRED_GROUP=network
    OIDC_REQUIRED_GROUP = os.environ.get('OIDC_REQUIRED_GROUP', '')

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

#!/usr/bin/env python3
"""
dnsdist Web API Server
A lightweight HTTP API server that accepts JSON-formatted CLI commands
and executes them via dnsdist's console using the dnsdist_console library.

Usage:
    python3 webapi-agent.py [--port PORT] [--console-host HOST] [--console-port PORT] [--key KEY] [--webtoken TOKEN]

Default HTTP port: 8080
Default console host: 127.0.0.1
Default console port: 5199
Default key: None (no encryption)
Default webtoken: None (only validates token is non-empty, does not validate token value)
"""

import argparse
import base64
import json
import logging
import secrets
import socket
import struct
import time
from datetime import datetime
from http.server import BaseHTTPRequestHandler, HTTPServer
from ipaddress import IPv4Address
from urllib.parse import urlparse

import libnacl
import libnacl.utils
from settings import settings

# Configure logging
settings.configure_logging()
logger = logging.getLogger('dnsdist-webapi')


# Generate a secure random token
def Createtoken(type=32):
    token = secrets.token_urlsafe(type)
    logger.info(f"Secure token: {token}")


def validate_ipv4_address(address: str) -> bool:
    try:
        IPv4Address(address)
        return True
    except ValueError:
        return False


class DNSDistConsole:
    def __init__(self, key, host="127.0.0.1", port=5199):
        """Initialize DNSDist console connection with authentication"""
        self.console_host = host
        self.console_port = port
        self.console_key = base64.b64decode(key)

        self.client_nonce = libnacl.utils.rand_nonce()
        self.server_nonce = None
        self.write_nonce = None
        self.read_nonce = None
        self.socket_connection = None
        self.socket_timeout = 3.0  # Increased from 1.0 to be more tolerant

        self.establish_connection()

    def encrypt_message(self, message, nonce):
        """Encrypt message for console communication"""
        encoded_message = message.encode('utf-8')
        return libnacl.crypto_secretbox(encoded_message, nonce, self.console_key)

    def decrypt_message(self, encrypted_data, nonce):
        """Decrypt message from console response"""
        decrypted_result = libnacl.crypto_secretbox_open(encrypted_data, nonce, self.console_key)
        return decrypted_result.decode('utf-8')

    def increment_nonce(self, nonce):
        """Increment nonce value for next operation"""
        nonce_value = int.from_bytes(nonce[:4], "big")
        nonce_value += 1
        return nonce_value.to_bytes(4, byteorder='big') + nonce[4:]

    def disconnect(self):
        """Close socket connection"""
        if self.socket_connection is not None:
            try:
                self.socket_connection.close()
            except Exception as e:
                logging.error(f"error: {e}")
            self.socket_connection = None

    def establish_connection(self):
        """Establish connection to DNSDist console"""
        # prepare socket
        if validate_ipv4_address(self.console_host):
            self.socket_connection = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        else:
            self.socket_connection = socket.socket(socket.AF_INET6, socket.SOCK_STREAM)
        self.socket_connection.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
        self.socket_connection.settimeout(self.socket_timeout)

        try:
            # connect to the server
            self.socket_connection.connect((self.console_host, self.console_port))
            # send our nonce
            self.socket_connection.send(self.client_nonce)

            # waiting to receive server nonce
            self.server_nonce = self.socket_connection.recv(len(self.client_nonce))
            if len(self.server_nonce) != len(self.client_nonce):
                raise Exception("incorrect nonce size")

            # init reading and writing nonce
            half_nonce_length = int(len(self.client_nonce) / 2)
            self.read_nonce = self.client_nonce[0:half_nonce_length] + self.server_nonce[half_nonce_length:]
            self.write_nonce = self.server_nonce[0:half_nonce_length] + self.client_nonce[half_nonce_length:]
            # send empty command to check if the handshake is ok
            try:
                self.execute_command(command="")
            except Exception as error:
                raise Exception("handshake error: %s" % error)
        except Exception as error:
            self.disconnect()
            raise Exception(f"Connection error: {error}")

    def ensure_connection(self):
        """Check connection and reconnect if necessary"""
        if self.socket_connection is None:
            self.establish_connection()
            return True
        return False

    def execute_command(self, command, max_retries=2):
        """Execute command on DNSDist console and return output with auto-reconnect"""
        retry_count = 0
        last_error = None

        while retry_count <= max_retries:
            try:
                # Try to reconnect if socket is None
                self.ensure_connection()

                # encrypt command
                encrypted_command = self.encrypt_message(command, self.write_nonce)

                # send data size header
                self.socket_connection.send(struct.pack("!I", len(encrypted_command)))
                # send encrypted command
                self.socket_connection.send(encrypted_command)

                # waiting to receive data size
                size_data = self.socket_connection.recv(4)
                if not size_data:
                    raise Exception("no response size received")

                # unpack response size
                (response_size,) = struct.unpack("!I", size_data)
                # waiting to receive response according to the response size
                response_data = self.socket_connection.recv(response_size)
                while len(response_data) < response_size:
                    response_data += self.socket_connection.recv(response_size - len(response_data))
                # decrypt data
                decrypted_response = self.decrypt_message(response_data, self.read_nonce)
                # increment nonce for next command
                self.read_nonce = self.increment_nonce(nonce=self.read_nonce)
                self.write_nonce = self.increment_nonce(nonce=self.write_nonce)
                # return response output
                return decrypted_response
            except (BrokenPipeError, socket.error) as socket_error:
                # Socket related error - attempt reconnection
                last_error = socket_error
                retry_count += 1
                self.disconnect()
                if retry_count <= max_retries:
                    time.sleep(1)  # Small delay before retry
                    # Will reconnect on next loop iteration
            except Exception as error:
                # Other errors, just raise
                raise Exception(f"Command error: {error}")

        # If we get here, we've exhausted our retries
        raise Exception(f"Failed after {max_retries} retries: {last_error}")


class DNSDistClient:
    """Client for communicating with dnsdist via dnsdist_console library"""

    def __init__(self, host='127.0.0.1', port=5199, key=None):
        """
        Initialize dnsdist console client

        Args:
            host: dnsdist console host (default: 127.0.0.1)
            port: dnsdist console port (default: 5199)
            key: encryption key for console authentication
        """
        self.host = host
        self.port = port
        self.key = key
        self.console = None

    def _get_console(self):
        """Get or create console connection"""
        if self.console is None:
            # dnsdist_console.DNSDistConsole requires a key parameter
            # If no key is provided, use an empty string
            console_key = self.key if self.key is not None else ''
            self.console = DNSDistConsole(key=console_key, host=self.host, port=self.port)
        return self.console

    def execute_command(self, command):
        """Execute a command via dnsdist console"""
        try:
            console = self._get_console()
            result = console.execute_command(command=command)
            return True, result

        except ConnectionRefusedError:
            return False, "Connection refused. Is dnsdist running with controlSocket enabled?"
        except Exception as e:
            return False, f"Error executing command: {str(e)}"


class APIHandler(BaseHTTPRequestHandler):
    """HTTP request handler for the dnsdist Web API"""

    dnsdist_client = None
    web_token = None  # Expected web token for authentication

    def _set_cors_headers(self):
        """Set CORS headers for cross-origin requests"""
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type, X-API-Key')

    def _send_json_response(self, status_code, data):
        """Send a JSON response"""
        self.send_response(status_code)
        self.send_header('Content-Type', 'application/json')
        self._set_cors_headers()
        self.end_headers()
        self.wfile.write(json.dumps(data).encode('utf-8'))

    def do_OPTIONS(self):
        """Handle OPTIONS requests for CORS"""
        self.send_response(200)
        self._set_cors_headers()
        self.end_headers()

    def do_GET(self):
        """Handle GET requests"""
        parsed_path = urlparse(self.path)
        current_time = datetime.now()
        time_str = current_time.strftime("%H:%M:%S")

        # Health check endpoint
        if parsed_path.path == '/health':
            self._send_json_response(200, {
                'status': 'ok',
                'version': 'v0.0.2',
                'service_time': time_str
            })
            return

        # Info endpoint
        if parsed_path.path == '/api/v1/info':
            self._send_json_response(200, {
                'version': 'v0.0.2',
                'service_time': time_str,
                'endpoints': [
                    'POST /api/v1/command - Execute dnsdist CLI commands',
                    'GET  /api/v1/info    - Get API information',
                    'GET  /health         - Health check'
                ]
            })
            return

        # Default response
        self._send_json_response(404, {
            'success': False,
            'error': 'Endpoint not found'
        })

    def do_POST(self):
        """Handle POST requests"""
        parsed_path = urlparse(self.path)

        # Command execution endpoint
        if parsed_path.path == '/api/v1/command':
            try:
                # Check for agent token in headers
                agent_token = self.headers.get('X-Agent-Token')
                if not agent_token:
                    self._send_json_response(401, {
                        'success': False,
                        'error': 'Missing X-Agent-Token header'
                    })
                    logger.warning('Command request rejected: Missing X-Agent-Token header')
                    return

                # Basic token validation - validate against configured web token
                # First check if token is empty
                if not agent_token.strip():
                    self._send_json_response(401, {
                        'success': False,
                        'error': 'Invalid agent token'
                    })
                    logger.warning('Command request rejected: Empty agent token')
                    return

                # If web token is configured, validate it
                if self.web_token:
                    # Use constant-time comparison to prevent timing attacks
                    if not secrets.compare_digest(agent_token, self.web_token):
                        self._send_json_response(401, {
                            'success': False,
                            'error': 'Invalid agent token'
                        })
                        logger.warning('Command request rejected: Invalid agent token')
                        return

                # Read request body
                content_length = int(self.headers.get('Content-Length', 0))
                body = self.rfile.read(content_length).decode('utf-8')

                # Parse JSON
                try:
                    data = json.loads(body)
                except json.JSONDecodeError as e:
                    self._send_json_response(400, {
                        'success': False,
                        'error': f'Invalid JSON: {str(e)}'
                    })
                    return

                # Validate command field
                if 'command' not in data:
                    self._send_json_response(400, {
                        'success': False,
                        'error': 'Missing "command" field in request'
                    })
                    return

                command = data['command']
                logger.info(f'Executing command: {command}')

                # Execute command via dnsdist
                success, result = self.dnsdist_client.execute_command(command)

                if success:
                    self._send_json_response(200, {
                        'success': True,
                        'command': command,
                        'result': result
                    })
                else:
                    self._send_json_response(500, {
                        'success': False,
                        'command': command,
                        'error': result
                    })

            except Exception as e:
                logger.error(f'Error processing request: {str(e)}')
                self._send_json_response(500, {
                    'success': False,
                    'error': f'Internal server error: {str(e)}'
                })
            return

        # Default response
        self._send_json_response(404, {
            'success': False,
            'error': 'Endpoint not found'
        })

    def log_message(self, format, *args):
        """Override to use custom logger"""
        logger.info(f"{self.client_address[0]} - {format % args}")


def main():
    parser = argparse.ArgumentParser(description='dnsdist Web API Server')
    parser.add_argument('--port', type=int, default=settings.WEBAPI_PORT,
                        help=f'HTTP port to listen on (default: {settings.WEBAPI_PORT})')
    parser.add_argument('--console-host', type=str, default=settings.DNSDIST_CONSOLE_HOST,
                        help=f'dnsdist console host (default: {settings.DNSDIST_CONSOLE_HOST})')
    parser.add_argument('--console-port', type=int, default=settings.DNSDIST_CONSOLE_PORT,
                        help=f'dnsdist console port (default: {settings.DNSDIST_CONSOLE_PORT})')
    parser.add_argument('--host', type=str, default=settings.WEBAPI_HOST,
                        help=f'Host to bind to (default: {settings.WEBAPI_HOST})')
    parser.add_argument('--key', type=str, default=settings.DNSDIST_KEY,
                        help='Encryption key for dnsdist console '
                             'authentication (if setKey() is configured). '
                             'Can also use DNSDIST_KEY environment variable.')
    parser.add_argument('--webtoken', type=str, default=settings.WEBAPI_TOKEN,
                        help='Web API authentication token. Clients must '
                             'provide this token in the X-Agent-Token header. '
                             'Can also use WEBAPI_TOKEN environment variable.')
    parser.add_argument('--create_token', action='store_true', help='Create new token example: 32 or 64 ')

    # Backward compatibility
    parser.add_argument('--socket', type=str, default=None,
                        help='[DEPRECATED] Use --console-host and --console-port instead. Format: host:port')

    args = parser.parse_args()

    if args.create_token:
        Createtoken(32)
        return
    # Handle backward compatibility with --socket
    console_host = args.console_host
    console_port = args.console_port
    if args.socket:
        logger.warning('--socket is deprecated. Please use --console-host and --console-port instead.')
        if ':' in args.socket:
            parts = args.socket.split(':')
            console_host = parts[0]
            console_port = int(parts[1])
        else:
            logger.error('Invalid socket format. Expected host:port')
            return

    # Get encryption key from argument (already has env default from settings)
    key = args.key

    # Get web token from argument (already has env default from settings)
    web_token = args.webtoken

    # Initialize dnsdist client
    APIHandler.dnsdist_client = DNSDistClient(host=console_host, port=console_port, key=key)
    APIHandler.web_token = web_token

    # Start HTTP server
    server_address = (args.host, args.port)
    httpd = HTTPServer(server_address, APIHandler)

    logger.info(f'Starting dnsdist Web API server on {args.host}:{args.port}')
    logger.info(f'Using dnsdist console: {console_host}:{console_port}')
    if key:
        logger.info('Using encryption key for console authentication')
    if web_token:
        logger.info('Web token authentication enabled')
    else:
        logger.info('No web token configured - authentication will only verify token is non-empty')
    logger.info('Available endpoints:')
    logger.info('  POST /api/v1/command - Execute dnsdist CLI commands')
    logger.info('  GET  /api/v1/info    - Get API information')
    logger.info('  GET  /health         - Health check')
    logger.info('')
    logger.info('Example usage:')
    logger.info(f'  curl -X POST http://localhost:{args.port}/api/v1/command \\')
    logger.info('    -H "Content-Type: application/json" \\')
    if web_token:
        logger.info('    -H "X-Agent-Token: <your-token>" \\')
    else:
        logger.info('    -H "X-Agent-Token: your-token-here" \\')
    logger.info('    -d \'{"command": "showServers()"}\'')

    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        logger.info('Shutting down server...')
        httpd.shutdown()


if __name__ == '__main__':
    main()

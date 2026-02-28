#!/usr/bin/env python3
"""
Tests for webapi-agent.py endpoints
"""

# Import the module under test
import importlib.util
import os
import sys
import time
from http.server import HTTPServer
from threading import Thread
from unittest.mock import Mock

import pytest
import requests

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

spec = importlib.util.spec_from_file_location("webapi_server", "webapi-agent.py")
webapi_server = importlib.util.module_from_spec(spec)
spec.loader.exec_module(webapi_server)

APIHandler = webapi_server.APIHandler
DNSDistClient = webapi_server.DNSDistClient


@pytest.fixture
def mock_dnsdist_client():
    """Fixture to mock DNSDistClient"""
    mock_client = Mock(spec=DNSDistClient)
    return mock_client


@pytest.fixture
def test_server(mock_dnsdist_client):
    """Fixture to create a test HTTP server"""
    # Configure the handler with mock client
    APIHandler.dnsdist_client = mock_dnsdist_client
    APIHandler.web_token = "test-token"

    # Start server in a thread
    server = HTTPServer(('localhost', 0), APIHandler)
    port = server.server_port

    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()

    # Wait for server to start
    time.sleep(0.1)

    yield f"http://localhost:{port}", mock_dnsdist_client

    # Cleanup
    server.shutdown()


class TestHealthEndpoint:
    """Tests for GET /health endpoint"""

    def test_health_endpoint_returns_ok(self, test_server):
        """Test that /health returns status ok"""
        url, _ = test_server
        response = requests.get(f"{url}/health")

        assert response.status_code == 200
        data = response.json()
        assert data['status'] == 'ok'
        assert 'version' in data
        assert 'service_time' in data

    def test_health_endpoint_has_cors_headers(self, test_server):
        """Test that /health has CORS headers"""
        url, _ = test_server
        response = requests.get(f"{url}/health")

        assert 'Access-Control-Allow-Origin' in response.headers
        assert response.headers['Access-Control-Allow-Origin'] == '*'


class TestInfoEndpoint:
    """Tests for GET /api/v1/info endpoint"""

    def test_info_endpoint_returns_version(self, test_server):
        """Test that /api/v1/info returns version and endpoints"""
        url, _ = test_server
        response = requests.get(f"{url}/api/v1/info")

        assert response.status_code == 200
        data = response.json()
        assert 'version' in data
        assert 'service_time' in data
        assert 'endpoints' in data
        assert isinstance(data['endpoints'], list)
        assert len(data['endpoints']) > 0

    def test_info_endpoint_has_cors_headers(self, test_server):
        """Test that /api/v1/info has CORS headers"""
        url, _ = test_server
        response = requests.get(f"{url}/api/v1/info")

        assert 'Access-Control-Allow-Origin' in response.headers


class TestCommandEndpoint:
    """Tests for POST /api/v1/command endpoint"""

    def test_command_endpoint_success(self, test_server):
        """Test successful command execution"""
        url, mock_client = test_server

        # Mock successful command execution
        mock_client.execute_command.return_value = (True, "Server list output")

        response = requests.post(
            f"{url}/api/v1/command",
            headers={
                'Content-Type': 'application/json',
                'X-Agent-Token': 'test-token'
            },
            json={'command': 'showServers()'}
        )

        assert response.status_code == 200
        data = response.json()
        assert data['success'] is True
        assert data['command'] == 'showServers()'
        assert data['result'] == "Server list output"

        # Verify the command was called
        mock_client.execute_command.assert_called_once_with('showServers()')

    def test_command_endpoint_missing_token(self, test_server):
        """Test command endpoint without token"""
        url, _ = test_server

        response = requests.post(
            f"{url}/api/v1/command",
            headers={'Content-Type': 'application/json'},
            json={'command': 'showServers()'}
        )

        assert response.status_code == 401
        data = response.json()
        assert data['success'] is False
        assert 'Missing X-Agent-Token' in data['error']

    def test_command_endpoint_invalid_token(self, test_server):
        """Test command endpoint with invalid token"""
        url, _ = test_server

        response = requests.post(
            f"{url}/api/v1/command",
            headers={
                'Content-Type': 'application/json',
                'X-Agent-Token': 'wrong-token'
            },
            json={'command': 'showServers()'}
        )

        assert response.status_code == 401
        data = response.json()
        assert data['success'] is False
        assert 'Invalid agent token' in data['error']

    def test_command_endpoint_missing_command_field(self, test_server):
        """Test command endpoint without command field"""
        url, _ = test_server

        response = requests.post(
            f"{url}/api/v1/command",
            headers={
                'Content-Type': 'application/json',
                'X-Agent-Token': 'test-token'
            },
            json={'not_a_command': 'showServers()'}
        )

        assert response.status_code == 400
        data = response.json()
        assert data['success'] is False
        assert 'Missing "command" field' in data['error']

    def test_command_endpoint_invalid_json(self, test_server):
        """Test command endpoint with invalid JSON"""
        url, _ = test_server

        response = requests.post(
            f"{url}/api/v1/command",
            headers={
                'Content-Type': 'application/json',
                'X-Agent-Token': 'test-token'
            },
            data='invalid json{'
        )

        assert response.status_code == 400
        data = response.json()
        assert data['success'] is False
        assert 'Invalid JSON' in data['error']

    def test_command_endpoint_execution_error(self, test_server):
        """Test command endpoint when execution fails"""
        url, mock_client = test_server

        # Mock failed command execution
        mock_client.execute_command.return_value = (False, "Connection refused")

        response = requests.post(
            f"{url}/api/v1/command",
            headers={
                'Content-Type': 'application/json',
                'X-Agent-Token': 'test-token'
            },
            json={'command': 'showServers()'}
        )

        assert response.status_code == 500
        data = response.json()
        assert data['success'] is False
        assert data['command'] == 'showServers()'
        assert 'Connection refused' in data['error']


class TestOptionsEndpoint:
    """Tests for OPTIONS endpoint (CORS preflight)"""

    def test_options_endpoint(self, test_server):
        """Test OPTIONS endpoint for CORS preflight"""
        url, _ = test_server

        response = requests.options(f"{url}/api/v1/command")

        assert response.status_code == 200
        assert 'Access-Control-Allow-Origin' in response.headers
        assert 'Access-Control-Allow-Methods' in response.headers
        assert 'Access-Control-Allow-Headers' in response.headers


class TestNotFoundEndpoint:
    """Tests for 404 responses"""

    def test_get_nonexistent_endpoint(self, test_server):
        """Test GET request to nonexistent endpoint"""
        url, _ = test_server

        response = requests.get(f"{url}/api/v1/nonexistent")

        assert response.status_code == 404
        data = response.json()
        assert data['success'] is False
        assert 'Endpoint not found' in data['error']

    def test_post_nonexistent_endpoint(self, test_server):
        """Test POST request to nonexistent endpoint"""
        url, _ = test_server

        response = requests.post(
            f"{url}/api/v1/nonexistent",
            headers={
                'Content-Type': 'application/json',
                'X-Agent-Token': 'test-token'
            },
            json={'command': 'test'}
        )

        assert response.status_code == 404
        data = response.json()
        assert data['success'] is False
        assert 'Endpoint not found' in data['error']

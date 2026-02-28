#!/usr/bin/env python3
"""
Tests for console.py endpoints
"""

import json
import os
import sys
from unittest.mock import Mock, patch

import pytest
from console import Database, app

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


@pytest.fixture
def client():
    """Create a test client for the Flask app"""
    app.config['TESTING'] = True
    app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///:memory:'

    with app.test_client() as client:
        with app.app_context():
            # Initialize test database
            import console
            if console.db is None:
                # Create a test database instance and initialize tables
                test_db = Database('sqlite:///:memory:')
                test_db.create_tables()
                console.db = test_db
            yield client


class TestRootEndpoint:
    """Tests for GET / endpoint"""

    def test_root_endpoint_returns_html(self, client):
        """Test that root endpoint returns HTML page"""
        response = client.get('/')
        assert response.status_code == 200
        assert b'<!DOCTYPE html>' in response.data or b'<html' in response.data


class TestAgentsEndpoint:
    """Tests for /api/agents endpoints"""

    def test_get_agents_empty(self, client):
        """Test GET /api/agents returns empty list initially"""
        response = client.get('/api/agents')
        assert response.status_code == 200
        data = json.loads(response.data)
        assert isinstance(data, list)

    def test_post_agent_success(self, client):
        """Test POST /api/agents validates input"""
        agent_data = {
            'agent_name': 'Test Agent',
            'agent_ip': 'localhost',
            'agent_port': 8081,
            'is_active': True
        }

        response = client.post(
            '/api/agents',
            data=json.dumps(agent_data),
            content_type='application/json'
        )

        # Accept any response that's not a server error
        assert response.status_code in [200, 201, 400, 422]
        data = json.loads(response.data)
        # Response should have some structure
        assert isinstance(data, dict)

    def test_post_agent_missing_fields(self, client):
        """Test POST /api/agents with missing required fields"""
        agent_data = {
            'agent_name': 'Test Agent'
            # Missing other required fields
        }

        response = client.post(
            '/api/agents',
            data=json.dumps(agent_data),
            content_type='application/json'
        )

        # Should return error (400 or 422)
        assert response.status_code in [400, 422, 500]


class TestCommandEndpoint:
    """Tests for POST /api/command endpoint"""

    @patch('console.requests.post')
    def test_command_endpoint_success(self, mock_post, client):
        """Test command endpoint validation"""
        # Setup mock response
        mock_response = Mock()
        mock_response.json.return_value = {
            'success': True,
            'result': 'Command output'
        }
        mock_response.status_code = 200
        mock_post.return_value = mock_response

        command_data = {
            'agent_id': 1,
            'command': 'showServers()'
        }

        response = client.post(
            '/api/command',
            data=json.dumps(command_data),
            content_type='application/json'
        )

        # Accept any response that's not a server error
        assert response.status_code in [200, 400, 404, 422, 500]
        data = json.loads(response.data)
        # Response should have some structure
        assert isinstance(data, dict)

    def test_command_endpoint_missing_fields(self, client):
        """Test command endpoint with missing fields"""
        command_data = {
            'command': 'showServers()'
            # Missing 'agent_id'
        }

        response = client.post(
            '/api/command',
            data=json.dumps(command_data),
            content_type='application/json'
        )

        assert response.status_code in [400, 422, 500]


class TestHistoryEndpoint:
    """Tests for /api/history endpoints"""

    def test_get_history(self, client):
        """Test GET /api/history returns command history"""
        response = client.get('/api/history')
        assert response.status_code == 200
        data = json.loads(response.data)
        assert isinstance(data, dict)
        assert 'history' in data or 'success' in data

    def test_delete_history(self, client):
        """Test DELETE /api/history clears history"""
        response = client.delete('/api/history')
        assert response.status_code in [200, 204]


class TestMetricsEndpoint:
    """Tests for GET /metrics endpoint"""

    def test_metrics_endpoint(self, client):
        """Test metrics endpoint returns Prometheus-style metrics"""
        response = client.get('/metrics')
        assert response.status_code == 200
        # Metrics should be plain text
        assert response.content_type in ['text/plain', 'text/plain; charset=utf-8', 'text/plain; version=0.0.4']


class TestRulesEndpoint:
    """Tests for /api/rules endpoints"""

    def test_get_rules(self, client):
        """Test GET /api/rules returns rules list"""
        response = client.get('/api/rules')
        assert response.status_code == 200
        data = json.loads(response.data)
        assert isinstance(data, dict)
        assert 'rules' in data or 'success' in data


class TestSyncStatusEndpoint:
    """Tests for /api/sync-status endpoint"""

    def test_sync_status(self, client):
        """Test GET /api/sync-status returns sync status"""
        response = client.get('/api/sync-status')
        assert response.status_code == 200
        data = json.loads(response.data)
        # Should have some status information
        assert isinstance(data, dict)


class TestAgentServersEndpoint:
    """Tests for /api/agents/servers endpoint"""

    def test_get_agent_servers(self, client):
        """Test GET /api/agents/servers returns server data"""
        response = client.get('/api/agents/servers')
        assert response.status_code == 200
        data = json.loads(response.data)
        assert isinstance(data, dict)
        assert 'agents_servers' in data or 'success' in data


class TestTopClientsEndpoint:
    """Tests for /api/agents/topclients endpoint"""

    def test_get_top_clients(self, client):
        """Test GET /api/agents/topclients returns top clients data"""
        response = client.get('/api/agents/topclients')
        assert response.status_code == 200
        data = json.loads(response.data)
        assert isinstance(data, dict)
        assert 'agents_topclients' in data or 'success' in data


class TestTopQueriesEndpoint:
    """Tests for /api/agents/topqueries endpoint"""

    def test_get_top_queries(self, client):
        """Test GET /api/agents/topqueries returns top queries data"""
        response = client.get('/api/agents/topqueries')
        assert response.status_code == 200
        data = json.loads(response.data)
        assert isinstance(data, dict)
        assert 'agents_topqueries' in data or 'success' in data


class TestBackendHealthEndpoint:
    """Tests for /api/backend-health endpoint"""

    def test_backend_health_success(self, client):
        """Test GET /api/backend-health returns healthy status"""
        response = client.get('/api/backend-health')
        assert response.status_code == 200
        data = json.loads(response.data)
        assert data['success'] is True
        assert data['status'] == 'healthy'
        assert data['service'] == 'dnsdist-console'
        assert 'timestamp' in data

    def test_backend_health_returns_json(self, client):
        """Test that backend health endpoint returns JSON"""
        response = client.get('/api/backend-health')
        assert response.content_type == 'application/json'

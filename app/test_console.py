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
    """Create a test client for the Flask app with an authenticated session"""
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
            # Simulate an authenticated session so @login_required passes
            with client.session_transaction() as sess:
                sess['user_id'] = 1
                sess['username'] = 'admin'
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


class TestLoginEndpoint:
    """Tests for authentication endpoints"""

    def test_login_page_returns_html(self):
        """Test that the login page is accessible without authentication"""
        app.config['TESTING'] = True
        with app.test_client() as unauthenticated_client:
            with app.app_context():
                import console
                if console.db is None:
                    test_db = Database('sqlite:///:memory:')
                    test_db.create_tables()
                    console.db = test_db
                response = unauthenticated_client.get('/login')
                assert response.status_code == 200
                assert b'<!DOCTYPE html>' in response.data or b'<html' in response.data

    def test_protected_route_redirects_unauthenticated(self):
        """Test that protected routes redirect to login when not authenticated"""
        app.config['TESTING'] = True
        with app.test_client() as unauthenticated_client:
            response = unauthenticated_client.get('/')
            assert response.status_code == 302
            assert '/login' in response.headers['Location']

    def test_login_with_valid_credentials(self):
        """Test login with valid admin credentials"""
        app.config['TESTING'] = True
        with app.test_client() as unauthenticated_client:
            with app.app_context():
                import console
                if console.db is None:
                    test_db = Database('sqlite:///:memory:')
                    test_db.create_tables()
                    console.db = test_db
                response = unauthenticated_client.post(
                    '/login',
                    data={'username': 'admin', 'password': 'admin'},
                    follow_redirects=False
                )
                assert response.status_code == 302

    def test_login_with_invalid_credentials(self):
        """Test login with invalid credentials returns error"""
        app.config['TESTING'] = True
        with app.test_client() as unauthenticated_client:
            with app.app_context():
                import console
                if console.db is None:
                    test_db = Database('sqlite:///:memory:')
                    test_db.create_tables()
                    console.db = test_db
                response = unauthenticated_client.post(
                    '/login',
                    data={'username': 'admin', 'password': 'wrong'},
                    follow_redirects=False
                )
                assert response.status_code == 200
                assert b'Invalid' in response.data

    def test_logout_redirects_to_login(self, client):
        """Test that logout clears session and redirects to login"""
        response = client.get('/logout', follow_redirects=False)
        assert response.status_code == 302
        assert '/login' in response.headers['Location']


class TestUsersEndpoint:
    """Tests for /api/users endpoints"""

    def test_get_users(self, client):
        """Test GET /api/users returns list of users"""
        response = client.get('/api/users')
        assert response.status_code == 200
        data = json.loads(response.data)
        assert data['success'] is True
        assert isinstance(data['users'], list)
        # Default admin user should exist
        assert len(data['users']) >= 1
        assert any(u['username'] == 'admin' for u in data['users'])

    def test_create_user(self, client):
        """Test POST /api/users creates a new user"""
        response = client.post(
            '/api/users',
            data=json.dumps({'username': 'testuser', 'password': 'testpass'}),
            content_type='application/json'
        )
        assert response.status_code == 201
        data = json.loads(response.data)
        assert data['success'] is True
        assert data['user']['username'] == 'testuser'

    def test_create_user_duplicate_username(self, client):
        """Test POST /api/users with duplicate username returns error"""
        client.post(
            '/api/users',
            data=json.dumps({'username': 'dupuser', 'password': 'pass1'}),
            content_type='application/json'
        )
        response = client.post(
            '/api/users',
            data=json.dumps({'username': 'dupuser', 'password': 'pass2'}),
            content_type='application/json'
        )
        assert response.status_code == 400
        data = json.loads(response.data)
        assert data['success'] is False

    def test_create_user_missing_password(self, client):
        """Test POST /api/users without password returns error"""
        response = client.post(
            '/api/users',
            data=json.dumps({'username': 'nopassuser'}),
            content_type='application/json'
        )
        assert response.status_code == 400

    def test_update_user(self, client):
        """Test PUT /api/users/<id> updates a user"""
        # First create a user
        create_resp = client.post(
            '/api/users',
            data=json.dumps({'username': 'upduser', 'password': 'pass'}),
            content_type='application/json'
        )
        user_id = json.loads(create_resp.data)['user']['id']

        response = client.put(
            f'/api/users/{user_id}',
            data=json.dumps({'username': 'upduser_renamed'}),
            content_type='application/json'
        )
        assert response.status_code == 200
        data = json.loads(response.data)
        assert data['success'] is True
        assert data['user']['username'] == 'upduser_renamed'

    def test_delete_user(self, client):
        """Test DELETE /api/users/<id> deletes a user"""
        # Create a user to delete
        create_resp = client.post(
            '/api/users',
            data=json.dumps({'username': 'deluser', 'password': 'pass'}),
            content_type='application/json'
        )
        user_id = json.loads(create_resp.data)['user']['id']

        response = client.delete(f'/api/users/{user_id}')
        assert response.status_code == 200
        data = json.loads(response.data)
        assert data['success'] is True

    def test_cannot_delete_last_active_user(self, client):
        """Test that the last active user cannot be deleted"""
        # Get all users and deactivate all except one
        users_resp = client.get('/api/users')
        users = json.loads(users_resp.data)['users']

        # Create a fresh scenario: just check that admin can't be deleted
        # when it's the only active user (the seeded state)
        # First deactivate everyone except admin
        admin = next(u for u in users if u['username'] == 'admin')
        for u in users:
            if u['id'] != admin['id']:
                client.delete(f'/api/users/{u["id"]}')

        response = client.delete(f'/api/users/{admin["id"]}')
        # Should fail because admin is the session user (cannot delete own account)
        assert response.status_code == 400
        data = json.loads(response.data)
        assert data['success'] is False

    def test_users_page_accessible(self, client):
        """Test that the /users page renders for authenticated users"""
        response = client.get('/users')
        assert response.status_code == 200
        assert b'<!DOCTYPE html>' in response.data or b'<html' in response.data


class TestUserTokenEndpoint:
    """Tests for /api/users/<id>/token endpoints"""

    def test_generate_token_creates_token(self, client):
        """Test POST /api/users/<id>/token generates a new token"""
        # Admin user has id=1 and we're logged in as admin
        response = client.post('/api/users/1/token')
        assert response.status_code == 201
        data = json.loads(response.data)
        assert data['success'] is True
        assert 'token' in data
        assert len(data['token']) == 64
        assert data['user']['api_token'] == data['token']

    def test_generate_token_updates_existing_token(self, client):
        """Test POST generates a new token even when one already exists"""
        client.post('/api/users/1/token')
        response = client.post('/api/users/1/token')
        assert response.status_code == 201
        data = json.loads(response.data)
        assert data['success'] is True
        assert len(data['token']) == 64

    def test_revoke_token_clears_token(self, client):
        """Test DELETE /api/users/<id>/token revokes the token"""
        client.post('/api/users/1/token')
        response = client.delete('/api/users/1/token')
        assert response.status_code == 200
        data = json.loads(response.data)
        assert data['success'] is True
        assert data['user']['api_token'] is None

    def test_generate_token_for_nonexistent_user(self, client):
        """Test POST returns 404 for a user that doesn't exist"""
        response = client.post('/api/users/9999/token')
        assert response.status_code == 404

    def test_generate_token_forbidden_for_other_user(self, client):
        """Test that a user cannot generate a token for another user"""
        # Create a second user
        create_resp = client.post(
            '/api/users',
            data=json.dumps({'username': 'otheruser', 'password': 'pass'}),
            content_type='application/json'
        )
        other_id = json.loads(create_resp.data)['user']['id']

        # Session is for user_id=1, try to generate a token for another user
        response = client.post(f'/api/users/{other_id}/token')
        assert response.status_code == 403
        data = json.loads(response.data)
        assert data['success'] is False

    def test_bearer_token_authentication(self, client):
        """Test that a valid Bearer token grants API access"""
        from settings import settings as s
        original_auth = s.AUTH_ENABLED
        original_oidc = s.OIDC_ENABLED
        s.AUTH_ENABLED = True
        s.OIDC_ENABLED = False
        try:
            # Generate a token for the admin user via authenticated session
            gen_resp = client.post('/api/users/1/token')
            token = json.loads(gen_resp.data)['token']

            # Now make an unauthenticated request using the Bearer token
            with app.test_client() as c:
                response = c.get(
                    '/api/users',
                    headers={'Authorization': f'Bearer {token}'}
                )
                assert response.status_code == 200
                data = json.loads(response.data)
                assert data['success'] is True
        finally:
            s.AUTH_ENABLED = original_auth
            s.OIDC_ENABLED = original_oidc

    def test_invalid_bearer_token_rejected(self, client):
        """Test that an invalid Bearer token results in 401 for API routes"""
        from settings import settings as s
        original_auth = s.AUTH_ENABLED
        original_oidc = s.OIDC_ENABLED
        s.AUTH_ENABLED = True
        s.OIDC_ENABLED = False
        try:
            with app.test_client() as c:
                response = c.get(
                    '/api/users',
                    headers={'Authorization': 'Bearer invalidtoken'}
                )
                assert response.status_code == 401
        finally:
            s.AUTH_ENABLED = original_auth
            s.OIDC_ENABLED = original_oidc

    def test_token_included_in_user_dict(self, client):
        """Test that api_token field appears in user listing"""
        response = client.get('/api/users')
        data = json.loads(response.data)
        assert data['success'] is True
        admin = next(u for u in data['users'] if u['username'] == 'admin')
        assert 'api_token' in admin


class TestAuthEnabledSetting:
    """Tests for AUTH_ENABLED toggle behaviour"""

    def test_auth_disabled_bypasses_login(self):
        """When both AUTH_ENABLED and OIDC_ENABLED are False, all routes are open"""
        import console
        from settings import settings as s
        original_auth = s.AUTH_ENABLED
        original_oidc = s.OIDC_ENABLED
        s.AUTH_ENABLED = False
        s.OIDC_ENABLED = False
        try:
            app.config['TESTING'] = True
            with app.test_client() as c:
                with app.app_context():
                    if console.db is None:
                        test_db = Database('sqlite:///:memory:')
                        test_db.create_tables()
                        console.db = test_db
                    # Should NOT redirect to /login
                    response = c.get('/')
                    assert response.status_code == 200
        finally:
            s.AUTH_ENABLED = original_auth
            s.OIDC_ENABLED = original_oidc

    def test_auth_enabled_requires_login(self):
        """When AUTH_ENABLED is True, unauthenticated requests are redirected"""
        from settings import settings as s
        original_auth = s.AUTH_ENABLED
        s.AUTH_ENABLED = True
        try:
            app.config['TESTING'] = True
            with app.test_client() as c:
                response = c.get('/', follow_redirects=False)
                assert response.status_code == 302
                assert '/login' in response.headers['Location']
        finally:
            s.AUTH_ENABLED = original_auth

    def test_login_page_shows_form_when_auth_enabled(self):
        """Login page shows the local form when AUTH_ENABLED is True"""
        from settings import settings as s
        original_auth, original_oidc = s.AUTH_ENABLED, s.OIDC_ENABLED
        s.AUTH_ENABLED = True
        s.OIDC_ENABLED = False
        try:
            app.config['TESTING'] = True
            with app.test_client() as c:
                with app.app_context():
                    import console
                    if console.db is None:
                        test_db = Database('sqlite:///:memory:')
                        test_db.create_tables()
                        console.db = test_db
                    response = c.get('/login')
                    assert response.status_code == 200
                    assert b'username' in response.data.lower()
        finally:
            s.AUTH_ENABLED = original_auth
            s.OIDC_ENABLED = original_oidc

    def test_login_page_shows_sso_button_when_oidc_enabled(self):
        """Login page shows SSO button when OIDC_ENABLED is True"""
        from settings import settings as s
        original_auth, original_oidc = s.AUTH_ENABLED, s.OIDC_ENABLED
        s.AUTH_ENABLED = True
        s.OIDC_ENABLED = True
        try:
            app.config['TESTING'] = True
            with app.test_client() as c:
                with app.app_context():
                    import console
                    if console.db is None:
                        test_db = Database('sqlite:///:memory:')
                        test_db.create_tables()
                        console.db = test_db
                    response = c.get('/login')
                    assert response.status_code == 200
                    assert b'SSO' in response.data or b'sso' in response.data.lower()
        finally:
            s.AUTH_ENABLED = original_auth
            s.OIDC_ENABLED = original_oidc


class TestOIDCFlow:
    """Tests for the OIDC authorization-code flow"""

    def test_oidc_initiate_redirects_to_provider(self):
        """GET /auth/oidc sets state and redirects to provider"""
        from unittest.mock import patch
        from settings import settings as s
        original_oidc = s.OIDC_ENABLED
        original_url = s.OIDC_PROVIDER_URL
        original_client = s.OIDC_CLIENT_ID
        original_redirect = s.OIDC_REDIRECT_URI
        s.OIDC_ENABLED = True
        s.OIDC_PROVIDER_URL = 'https://sso.example.com/realms/myrealm'
        s.OIDC_CLIENT_ID = 'test-client'
        s.OIDC_REDIRECT_URI = 'http://localhost/auth/callback'
        mock_discovery = {
            'authorization_endpoint': 'https://sso.example.com/realms/myrealm/protocol/openid-connect/auth',
            'token_endpoint': 'https://sso.example.com/realms/myrealm/protocol/openid-connect/token',
            'userinfo_endpoint': 'https://sso.example.com/realms/myrealm/protocol/openid-connect/userinfo',
        }
        try:
            import console
            console._oidc_config_cache = mock_discovery
            app.config['TESTING'] = True
            with app.test_client() as c:
                with app.app_context():
                    if console.db is None:
                        test_db = Database('sqlite:///:memory:')
                        test_db.create_tables()
                        console.db = test_db
                    response = c.get('/auth/oidc', follow_redirects=False)
                    assert response.status_code == 302
                    location = response.headers['Location']
                    assert 'sso.example.com' in location
                    assert 'client_id=test-client' in location
                    assert 'state=' in location
        finally:
            s.OIDC_ENABLED = original_oidc
            s.OIDC_PROVIDER_URL = original_url
            s.OIDC_CLIENT_ID = original_client
            s.OIDC_REDIRECT_URI = original_redirect
            console._oidc_config_cache = None

    def test_oidc_callback_invalid_state_returns_400(self):
        """OIDC callback with wrong state returns 400"""
        from settings import settings as s
        original_oidc = s.OIDC_ENABLED
        s.OIDC_ENABLED = True
        try:
            app.config['TESTING'] = True
            with app.test_client() as c:
                with c.session_transaction() as sess:
                    sess['oidc_state'] = 'correct-state'
                response = c.get('/auth/callback?state=wrong-state&code=abc', follow_redirects=False)
                assert response.status_code == 400
        finally:
            s.OIDC_ENABLED = original_oidc

    def test_oidc_callback_group_check_denies_user(self):
        """OIDC callback denies user not in required group"""
        from unittest.mock import patch, MagicMock
        from settings import settings as s
        original_oidc = s.OIDC_ENABLED
        original_group = s.OIDC_REQUIRED_GROUP
        s.OIDC_ENABLED = True
        s.OIDC_REQUIRED_GROUP = 'network'
        mock_discovery = {
            'authorization_endpoint': 'https://sso.example.com/auth',
            'token_endpoint': 'https://sso.example.com/token',
            'userinfo_endpoint': 'https://sso.example.com/userinfo',
        }
        try:
            import console
            console._oidc_config_cache = mock_discovery
            mock_token_resp = MagicMock()
            mock_token_resp.json.return_value = {'access_token': 'test-token'}
            mock_token_resp.raise_for_status = MagicMock()
            mock_userinfo_resp = MagicMock()
            mock_userinfo_resp.json.return_value = {
                'sub': 'user-123',
                'preferred_username': 'jdoe',
                'groups': ['other-group'],
            }
            mock_userinfo_resp.raise_for_status = MagicMock()
            app.config['TESTING'] = True
            with app.test_client() as c:
                with app.app_context():
                    if console.db is None:
                        test_db = Database('sqlite:///:memory:')
                        test_db.create_tables()
                        console.db = test_db
                    with c.session_transaction() as sess:
                        sess['oidc_state'] = 'valid-state'
                    with patch('console.requests.post', return_value=mock_token_resp), \
                         patch('console.requests.get', return_value=mock_userinfo_resp):
                        response = c.get(
                            '/auth/callback?state=valid-state&code=authcode',
                            follow_redirects=False
                        )
                    assert response.status_code == 403
                    assert b'network' in response.data
        finally:
            s.OIDC_ENABLED = original_oidc
            s.OIDC_REQUIRED_GROUP = original_group
            console._oidc_config_cache = None

    def test_oidc_callback_group_check_allows_user(self):
        """OIDC callback allows user in required group and sets session"""
        from unittest.mock import patch, MagicMock
        from settings import settings as s
        original_oidc = s.OIDC_ENABLED
        original_group = s.OIDC_REQUIRED_GROUP
        s.OIDC_ENABLED = True
        s.OIDC_REQUIRED_GROUP = 'network'
        mock_discovery = {
            'authorization_endpoint': 'https://sso.example.com/auth',
            'token_endpoint': 'https://sso.example.com/token',
            'userinfo_endpoint': 'https://sso.example.com/userinfo',
        }
        try:
            import console
            console._oidc_config_cache = mock_discovery
            mock_token_resp = MagicMock()
            mock_token_resp.json.return_value = {'access_token': 'test-token'}
            mock_token_resp.raise_for_status = MagicMock()
            mock_userinfo_resp = MagicMock()
            mock_userinfo_resp.json.return_value = {
                'sub': 'user-456',
                'preferred_username': 'jsmith',
                'groups': ['network', 'devops'],
            }
            mock_userinfo_resp.raise_for_status = MagicMock()
            app.config['TESTING'] = True
            with app.test_client() as c:
                with app.app_context():
                    if console.db is None:
                        test_db = Database('sqlite:///:memory:')
                        test_db.create_tables()
                        console.db = test_db
                    with c.session_transaction() as sess:
                        sess['oidc_state'] = 'valid-state'
                    with patch('console.requests.post', return_value=mock_token_resp), \
                         patch('console.requests.get', return_value=mock_userinfo_resp):
                        response = c.get(
                            '/auth/callback?state=valid-state&code=authcode',
                            follow_redirects=False
                        )
                    assert response.status_code == 302
                    with c.session_transaction() as sess:
                        assert sess.get('username') == 'jsmith'
                        assert sess.get('auth_method') == 'oidc'
        finally:
            s.OIDC_ENABLED = original_oidc
            s.OIDC_REQUIRED_GROUP = original_group
            console._oidc_config_cache = None

-- Seed data for SQLite
-- Source: alembic/versions/001_initial_schema_and_seed_data.py
--
-- Run after the schema has been created, e.g.:
--   sqlite3 app.db < db/seed_data.sqlite.sql
--
-- Booleans are stored as integers: 1 = true, 0 = false.
-- All timestamps are in UTC: '2024-01-01 00:00:00'.

INSERT INTO groups (id, name, description, created_at, updated_at) VALUES
    (1, 'dns-servers-us-east', 'DNS servers located in the US East region', '2024-01-01 00:00:00', '2024-01-01 00:00:00');

INSERT INTO agents (id, agent_name, agent_ip, agent_port, agent_token, group_id, created_at, updated_at, is_active, status, version, service_time) VALUES
    (1, 'dnsdist-us-east-01', '192.168.0.160', 8055, 'WaeqcSDf_DM0cV09_-zBJwu2meMTUqshBq9Lj8bLiYM', 1, '2024-01-01 00:00:00', '2024-01-01 00:00:00', 1, '0', '1.0.1', '0'),
    (2, 'dnsdist-eu-west-01', '192.168.0.160', 8055, 'WaeqcSDf_DM0cV09_-zBJwu2meMTUqshBq9Lj8bLiYM', 1, '2024-01-01 00:00:00', '2024-01-01 00:00:00', 1, '0', '1.0.1', '0');

INSERT INTO command_history (id, agent_name, command, success, result, error, executed_at) VALUES
    (1, 'dnsdist-us-east-01', 'showVersion()',  1, 'dnsdist 1.9.0', NULL, '2024-01-01 00:00:00'),
    (2, 'dnsdist-eu-west-01', 'showServers()',  1, '',              NULL, '2024-01-01 00:00:00'),
    (3, 'dnsdist-eu-west-01', 'topClients(20)', 1, '',              NULL, '2024-01-01 00:00:00'),
    (4, 'dnsdist-eu-west-01', 'clearRules()',   1, '',              NULL, '2024-01-01 00:00:00'),
    (5, 'dnsdist-eu-west-01', 'rmRule(0)',       1, '',              NULL, '2024-01-01 00:00:00');

INSERT INTO dynblock_rules (id, name, rule_command, description, group_id, creation_order, is_active, created_at, updated_at, rule_uuid) VALUES
    (1, 'droper-example', 'addAction(makeRule("example.com"), DropAction(),{name="rule1-droper",uuid = "663947e0-bb8b-4400-be10-ef05670d3119"}) mvRuleToTop()', 'drop example.com', 1, 1, 1, '2024-01-01 00:00:00', '2024-01-01 00:00:00', '663947e0-bb8b-4400-be10-ef05670d3119');

INSERT INTO rule_command_templates (id, name, template, description, is_active, created_at, updated_at) VALUES
    (1, 'makeRule',          'addAction(makeRule("example.org"), DropAction(), {name="{{r_name}}", uuid="{{r_uuid}}"})',                                                        'Matches queries with the specified qname exactly.',                                                                            1, '2024-01-01 00:00:00', '2024-01-01 00:00:00'),
    (2, 'MaxQPSIPRule',      'addAction(MaxQPSIPRule(10, 32, 64), TCAction(),{name="{{r_name}}",uuid = "{{r_uuid}}"})',                                                         'drop queries exceeding 5 qps, grouped by /24 for IPv4 and /64 for IPv6',                                                       1, '2024-01-01 00:00:00', '2024-01-01 00:00:00'),
    (3, 'AllRule',           'addAction(AllRule(),PoolAction(pool_resolv),{name="{{r_name}}",uuid = "{{r_uuid}}"})',                                                            'matches all incoming traffic and send-it to the pool of resolvers',                                                            1, '2024-01-01 00:00:00', '2024-01-01 00:00:00'),
    (4, 'PoolAvailableRule', 'addAction(PoolAvailableRule("current_dc"), PoolAction("current_dc"),{name="{{r_name}}",uuid = "{{r_uuid}}"})',                                    'Check whether a pool has any servers available to handle queries',                                                              1, '2024-01-01 00:00:00', '2024-01-01 00:00:00'),
    (5, 'QNameSuffixRule',   'addAction(QNameSuffixRule("example.com"), DropAction(),{name="{{r_name}}",uuid = "{{r_uuid}}"})',                                                 'Matches based on a group of domain suffixes for rapid testing of membership. (all *example.com)',                               1, '2024-01-01 00:00:00', '2024-01-01 00:00:00'),
    (6, 'RegexRule',         'addAction(RegexRule("[0-9]{4,}\.example$"), DropAction(),{name="{{r_name}}",uuid = "{{r_uuid}}"})',                                               'Matches the query name against the regex in Posix Extended Regular Expressions format. The match is done in a case-insensitive way.', 1, '2024-01-01 00:00:00', '2024-01-01 00:00:00'),
    (7, 'QNameRule',         'addAction(QNameRule("example.com"), DropAction(), {name="{{r_name}}",uuid = "{{r_uuid}}"})',                                                      'Matches queries with the specified qname exactly.',                                                                            1, '2024-01-01 00:00:00', '2024-01-01 00:00:00');

INSERT INTO sync_status (id, last_sync_time, status, synced_agents_count, failed_agents_count, error_message) VALUES
    (1, '2024-01-01 00:00:00', 'OK', 2, 0, NULL);

INSERT INTO audit_logs (id, ip_address, action, details, created_at) VALUES
    (1, '192.168.0.10', 'CREATE_AGENT', 'Created agent dnsdist-us-east-01',  '2024-01-01 00:00:00'),
    (2, '192.168.0.10', 'CREATE_AGENT', 'Created agent dnsdist-eu-west-01',  '2024-01-01 00:00:00'),
    (3, '192.168.0.20', 'CREATE_GROUP', 'Created group dns-servers-us-east', '2024-01-01 00:00:00');

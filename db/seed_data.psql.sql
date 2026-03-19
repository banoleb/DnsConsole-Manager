-- Seed data for PostgreSQL
-- Source: alembic/versions/001_initial_schema_and_seed_data.py
--
-- Run after the schema has been created, e.g.:
--   psql -U <user> -d <dbname> -f db/seed_data.psql.sql
--
-- Booleans use TRUE / FALSE.
-- All timestamps are UTC: '2024-01-01 00:00:00+00'.
-- Sequences are updated at the end so that new rows do not collide
-- with the seeded IDs.

INSERT INTO groups (id, name, description, created_at, updated_at) VALUES
    (1, 'dns-servers-us-east', 'DNS servers located in the US East region', '2024-01-01 00:00:00+00', '2024-01-01 00:00:00+00'),
    (2, 'dns-servers-us-west', 'DNS servers located in the US WEST region', '2024-01-01 00:00:00+00', '2024-01-01 00:00:00+00');

INSERT INTO agents (id, agent_name, agent_ip, agent_port, agent_token, group_id, created_at, updated_at, is_active, status, version, service_time) VALUES
    (1, 'dnsdist-us-east-01', '192.168.0.160', 8085, 'WaeqcSDf_DM0cV09_-zBJwu2meMTUqshBq9Lj8bLiYM', 1, '2024-01-01 00:00:00+00', '2024-01-01 00:00:00+00', TRUE, '0', '1.0.1', '0'),
    (2, 'dnsdist-eu-west-01', '192.168.0.161', 8085, 'WaeqcSDf_DM0cV09_-zBJwu2meMTUqshBq9Lj8bLiYM', 1, '2024-01-01 00:00:00+00', '2024-01-01 00:00:00+00', TRUE, '0', '1.0.1', '0');

INSERT INTO command_history (id, agent_name, command, success, result, error, executed_at) VALUES
    (1, 'dns-prod01', 'showVersion()',  TRUE, 'dnsdist 1.9.0', NULL, '2024-01-01 00:00:00+00'),
    (2, 'dns-prod02', 'showServers()',  TRUE, '',              NULL, '2024-01-01 00:00:00+00'),
    (3, 'dns-prod02', 'topClients(20)', TRUE, '',              NULL, '2024-01-01 00:00:00+00'),
    (4, 'dns-prod02', 'clearRules()',   TRUE, '',              NULL, '2024-01-01 00:00:00+00'),
    (5, 'dns-prod02', 'rmRule(0)',       TRUE, '',              NULL, '2024-01-01 00:00:00+00');

INSERT INTO dynblock_rules (id, name, rule_command, description, group_id, creation_order, is_active, created_at, updated_at, rule_uuid) VALUES
    (1, 'droper-example', 'addAction(makeRule("example.com"), DropAction(),{name="rule1-droper",uuid = "663947e0-bb8b-4400-be10-ef05670d3119"}) mvRuleToTop()', 'drop example.com', 1, 1, TRUE, '2024-01-01 00:00:00+00', '2024-01-01 00:00:00+00', '663947e0-bb8b-4400-be10-ef05670d3119');

INSERT INTO rule_command_templates (id, name, template, description, is_active, created_at, updated_at) VALUES
    (1, 'makeRule',          'addAction(makeRule("example.org"), DropAction(), {name="{{r_name}}", uuid="{{r_uuid}}"})',                                                        'Matches queries with the specified qname exactly.',                                                                            TRUE, '2024-01-01 00:00:00+00', '2024-01-01 00:00:00+00'),
    (2, 'MaxQPSIPRule',      'addAction(MaxQPSIPRule(10, 32, 64), TCAction(),{name="{{r_name}}",uuid = "{{r_uuid}}"})',                                                         'drop queries exceeding 5 qps, grouped by /24 for IPv4 and /64 for IPv6',                                                       TRUE, '2024-01-01 00:00:00+00', '2024-01-01 00:00:00+00'),
    (3, 'AllRule',           'addAction(AllRule(),PoolAction(pool_resolv),{name="{{r_name}}",uuid = "{{r_uuid}}"})',                                                            'matches all incoming traffic and send-it to the pool of resolvers',                                                            TRUE, '2024-01-01 00:00:00+00', '2024-01-01 00:00:00+00'),
    (4, 'PoolAvailableRule', 'addAction(PoolAvailableRule("current_dc"), PoolAction("current_dc"),{name="{{r_name}}",uuid = "{{r_uuid}}"})',                                    'Check whether a pool has any servers available to handle queries',                                                              TRUE, '2024-01-01 00:00:00+00', '2024-01-01 00:00:00+00'),
    (5, 'QNameSuffixRule',   'addAction(QNameSuffixRule("example.com"), DropAction(),{name="{{r_name}}",uuid = "{{r_uuid}}"})',                                                 'Matches based on a group of domain suffixes for rapid testing of membership. (all *example.com)',                               TRUE, '2024-01-01 00:00:00+00', '2024-01-01 00:00:00+00'),
    (6, 'RegexRule',         'addAction(RegexRule("[0-9]{4,}\.example$"), DropAction(),{name="{{r_name}}",uuid = "{{r_uuid}}"})',                                               'Matches the query name against the regex in Posix Extended Regular Expressions format. The match is done in a case-insensitive way.', TRUE, '2024-01-01 00:00:00+00', '2024-01-01 00:00:00+00'),
    (7, 'QNameRule',         'addAction(QNameRule("example.com"), DropAction(), {name="{{r_name}}",uuid = "{{r_uuid}}"})',                                                      'Matches queries with the specified qname exactly.',                                                                            TRUE, '2024-01-01 00:00:00+00', '2024-01-01 00:00:00+00'),
    (8, 'QNameSuffixRule',   'addAction(QNameSuffixRule({{r_access_list}}), DropAction(),{name="{{r_name}}",uuid = "{{r_uuid}}"})',                                             'Matches based on a group of domain suffixes for rapid testing of membership. (all *example.com)',                              TRUE, '2024-01-01 00:00:00+00', '2024-01-01 00:00:00+00'),
    (9, 'NetmaskGroupRule',  'addAction(NetmaskGroupRule({{r_access_list}}), DropAction(),{name="{{r_name}}",uuid = "{{r_uuid}}"})',                                            'Matches based on a group of IP suffixes. Checks if the client IP address (or destination) in the specified network-range.',    TRUE, '2024-01-01 00:00:00+00', '2024-01-01 00:00:00+00');

INSERT INTO access_list (id, name, value, type, category, enabled, reason, source, hit_count, created_at, created_by, updated_at) VALUES
    (1, 'blocklist-1', 'example.org', 'list', 'ip', FALSE, 'test', 'manual', 0  ,'2024-01-01 00:00:00+00', 0, '2024-01-01 00:00:00+00');                                                             

INSERT INTO sync_status (id, last_sync_time, status, synced_agents_count, failed_agents_count, error_message) VALUES
    (1, '2024-01-01 00:00:00+00', 'OK', 2, 0, NULL);

INSERT INTO audit_logs (id, ip_address, action, details, created_at) VALUES
    (1, '192.168.0.10', 'CREATE_AGENT', 'Created agent dist-stg1',  '2024-01-01 00:00:00+00'),
    (2, '192.168.0.10', 'CREATE_AGENT', 'Created agent dns-prod02',  '2024-01-01 00:00:00+00'),
    (3, '192.168.0.20', 'CREATE_GROUP', 'Created group dns-servers', '2024-01-01 00:00:00+00');

-- Reset sequences so that subsequent INSERTs without explicit IDs
-- do not collide with the seeded rows.
SELECT setval(pg_get_serial_sequence('groups',               'id'), MAX(id)) FROM groups;
SELECT setval(pg_get_serial_sequence('agents',               'id'), MAX(id)) FROM agents;
SELECT setval(pg_get_serial_sequence('command_history',      'id'), MAX(id)) FROM command_history;
SELECT setval(pg_get_serial_sequence('dynblock_rules',       'id'), MAX(id)) FROM dynblock_rules;
SELECT setval(pg_get_serial_sequence('rule_command_templates','id'), MAX(id)) FROM rule_command_templates;
SELECT setval(pg_get_serial_sequence('sync_status',          'id'), MAX(id)) FROM sync_status;
SELECT setval(pg_get_serial_sequence('audit_logs',           'id'), MAX(id)) FROM audit_logs;

#!/usr/bin/env python3

import json
import logging
import os
import re
import time
from datetime import datetime, timezone

import parsers
import requests
import sqlalchemy as sa
from flask import Flask, jsonify, render_template, request, send_from_directory
from models import (Agent, AgentDynBlock, AuditLog, CommandHistory, Database,
                    DownstreamServer, DynBlockRule, Group, Rule,
                    RuleCommandTemplate, SyncStatus, TopClient, TopQuery,
                    utc_now)
from settings import settings
from sqlalchemy.orm import joinedload
from victoria_metrics import VictoriaMetricsExporter

settings.configure_logging()
logger = logging.getLogger('web-console-manager')

db = None

# Victoria Metrics exporter instance
victoria_metrics_exporter = None


def create_app():
    """
    Flask application factory

    This function creates and configures the Flask application instance.
    It initializes the database and Victoria Metrics integration.

    In a multi-worker environment (e.g., Gunicorn), each worker process
    will call this function once, creating its own database connection
    and app instance. This is the correct behavior for WSGI applications.

    Returns:
        Flask: Configured Flask application instance

    Raises:
        Exception: If database or Victoria Metrics initialization fails
    """
    global db, victoria_metrics_exporter

    flask_app = Flask(__name__)

    try:
        # Initialize database if not already done (per-worker initialization)
        if db is None:

            db = Database(db_url=settings.DATABASE_URL)
            db.create_tables()
            logger.info(f'Database initialized: {settings.DATABASE_URL}')

        # Initialize Victoria Metrics exporter if not already done
        if victoria_metrics_exporter is None:
            victoria_metrics_exporter = VictoriaMetricsExporter()
            if victoria_metrics_exporter.enabled:
                logger.info(f'Victoria Metrics integration enabled: {victoria_metrics_exporter.base_url}')
            else:
                logger.info('Victoria Metrics integration is disabled')
    except Exception as e:
        logger.error(f'Error initializing application: {e}')
        raise
    return flask_app


app = create_app()


def extract_uuid_from_adddynblocks(command):
    # Match pattern with UUID and creation order
    pattern = r'[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[1-5][0-9a-fA-F]{3}-[89abAB][0-9a-fA-F]{3}-[0-9a-fA-F]{12}'
    match = re.search(pattern, command)
    if match:
        logger.debug(f'Found UUID: {match.group(0)}')
        rules = (match.group(0))
    else:
        rules = "Error"
    return rules


def sync_rules_to_database(agent_name, parsed_rules, session):

    logger.info(f"=== STARTING SYNC for agent {agent_name} ===")

    # Fetch existing rules for this agent
    existing_rules = session.query(Rule).filter_by(agent_name=agent_name).all()
    logger.info(f"Found {len(existing_rules)} existing rules in DB")

    # Create lookup dictionaries
    existing_rules_by_uuid = {}      # поиск по UUID
    existing_rules_by_rule_id = {}   # поиск по rule_id

    for rule in existing_rules:
        if rule.uuid:
            existing_rules_by_uuid[rule.uuid] = rule
        if rule.rule_id is not None:
            existing_rules_by_rule_id[rule.rule_id] = rule

    logger.info(f"UUID lookup map: {len(existing_rules_by_uuid)} entries")
    logger.info(f"Rule ID lookup map: {len(existing_rules_by_rule_id)} entries")

    # Statistics
    added_count = 0
    updated_count = 0
    unchanged_count = 0
    deleted_count = 0

    # Track seen identifiers from parsed_rules
    seen_uuids = set()
    seen_rule_ids = set()

    if not parsed_rules:
        logger.warning(f"No rules to sync for agent {agent_name}")
        # Delete ALL existing rules
        for rule in existing_rules:
            logger.info(f"Deleting rule {rule.uuid or rule.rule_id}")
            session.delete(rule)
            deleted_count += 1
    else:
        logger.info(f"Processing {len(parsed_rules)} rules from input")

        # FIRST PASS: Process all incoming rules
        for rule_data in parsed_rules:
            rule_uuid = rule_data.get('uuid')
            rule_id = rule_data.get('id')

            logger.debug(f"Processing: UUID={rule_uuid}, rule_id={rule_id}")

            # Track seen identifiers
            if rule_uuid:
                seen_uuids.add(rule_uuid)
            if rule_id is not None:
                seen_rule_ids.add(rule_id)

            # Create new rule instance
            new_rule = Rule(
                agent_name=agent_name,
                rule_id=rule_id,
                name=rule_data.get('name'),
                matches=rule_data.get('matches', 0),
                rule=rule_data.get('rule', ''),
                action=rule_data.get('action', ''),
                uuid=rule_uuid,
                creation_order=rule_data.get('creation_order')
            )

            # Find existing rule - first by UUID, then by rule_id
            existing_rule = None
            # found_by = None

            if rule_uuid and rule_uuid in existing_rules_by_uuid:
                existing_rule = existing_rules_by_uuid[rule_uuid]
                # found_by = "UUID"
                logger.debug(f"Found by UUID: {rule_uuid}")
            elif rule_id is not None and rule_id in existing_rules_by_rule_id:
                existing_rule = existing_rules_by_rule_id[rule_id]
                # found_by = "rule_id"
                logger.debug(f"Found by rule_id: {rule_id}")

                # If rule has UUID in DB but not in new data, update it
                if existing_rule.uuid and not rule_uuid:
                    logger.info(f"Rule with rule_id {rule_id} has UUID {existing_rule.uuid} in DB but no UUID in new data")
                # If UUID changed
                elif existing_rule.uuid and rule_uuid and existing_rule.uuid != rule_uuid:
                    logger.info(f"Rule with rule_id {rule_id} changing UUID from {existing_rule.uuid} to {rule_uuid}")
                    existing_rule.uuid = rule_uuid

            if existing_rule:
                # Rule exists - check for changes
                changed_fields = {}

                # Fields to compare (all except id)
                fields_to_compare = ['rule_id', 'name', 'matches', 'rule', 'action', 'uuid', 'creation_order']

                for field in fields_to_compare:
                    old_value = getattr(existing_rule, field)
                    new_value = getattr(new_rule, field)

                    if old_value != new_value:
                        changed_fields[field] = (old_value, new_value)
                        logger.debug(f"  Field '{field}': '{old_value}' -> '{new_value}'")
                        setattr(existing_rule, field, new_value)

                if changed_fields:
                    updated_count += 1
                    logger.debug(f"Rule updated ({len(changed_fields)} fields changed)")
                else:
                    unchanged_count += 1
                    logger.debug("Rule unchanged")
            else:
                # New rule - add to database
                logger.debug("New rule - adding to database")
                session.add(new_rule)
                added_count += 1

        # SECOND PASS: Delete rules that exist in DB but not in parsed_rules
        logger.info("Checking for rules to delete (exist in DB but not in new data)")

        # Check ALL existing rules
        for rule in existing_rules:
            should_delete = False

            # Rule has UUID
            if rule.uuid:
                if rule.uuid not in seen_uuids:
                    # UUID not found in new data
                    should_delete = True
                    logger.debug(f"Rule with UUID {rule.uuid} not found in new data")

            # Rule has no UUID but has rule_id
            elif rule.rule_id is not None:
                if rule.rule_id not in seen_rule_ids:
                    # rule_id not found in new data
                    should_delete = True
                    logger.debug(f"Rule with rule_id {rule.rule_id} (no UUID) not found in new data")

            # Rule has neither UUID nor rule_id (should not happen, but just in case)
            else:
                should_delete = True
                logger.debug("Rule with no identifiers found, deleting")

            if should_delete:
                logger.info(f"Deleting rule {rule.uuid or rule.rule_id} (not in new data)")
                session.delete(rule)
                deleted_count += 1

    # Commit changes
    try:
        session.commit()
        logger.info(f"Commit successful for agent {agent_name}")
    except Exception as e:
        logger.error(f"Error during commit: {e}")
        session.rollback()
        raise

    # Log results
    logger.info(f"=== SYNC RESULTS for agent {agent_name} ===")
    logger.info(f"Added: {added_count}")
    logger.info(f"Updated: {updated_count}")
    logger.info(f"Unchanged: {unchanged_count}")
    logger.info(f"Deleted: {deleted_count}")
    logger.info("=== END SYNC ===\n")

    # return {
    #     'added': added_count,
    #     'updated': updated_count,
    #     'unchanged': unchanged_count,
    #     'deleted': deleted_count
    # }


def sync_agent_status_to_database(agent_name, status, session):

    # Sync agent info to database
    if status is None:
        return
    # session.query(AgentDynBlock).filter_by(agent_name=agent_name).delete()

    # Add new blocks (can be empty list)
    for block_data in status:
        block = AgentDynBlock(
            agent_name=agent_name,
            what=block_data.get('what', ''),
            seconds=block_data.get('seconds'),
            blocks=block_data.get('blocks'),
            warning=block_data.get('warning'),
            action=block_data.get('action'),
            ebpf=block_data.get('ebpf'),
            reason=block_data.get('reason')
        )
        session.add(block)

    session.commit()
    # logger.info(f'Synced {len(parsed_blocks)} dynamic blocks for agent {agent_name}')


def sync_servers_to_database(agent_name, parsed_servers, session):
    """
    Sync downstream servers to database for a given agent using selective updates
    """
    if not parsed_servers or not isinstance(parsed_servers, list):
        return

    # Fetch existing servers for this agent indexed by server_id
    existing_servers = {}
    for server in session.query(DownstreamServer).filter_by(agent_name=agent_name).all():
        existing_servers[server.server_id] = server

    # Track which server_ids we've seen in the new data
    seen_server_ids = set()

    # Counters for logging
    added_count = 0
    updated_count = 0
    unchanged_count = 0

    # Process each server from the new data
    for server_data in parsed_servers:
        server_id = server_data.get('id')
        if server_id is None:
            logger.warning(f'Server data missing id field, skipping: {server_data}')
            continue

        seen_server_ids.add(server_id)

        # Create a new server instance from the parsed data
        new_server = DownstreamServer(
            agent_name=agent_name,
            server_id=server_id,
            name=server_data.get('name'),
            address=server_data.get('address', ''),
            state=server_data.get('state', ''),
            qps=server_data.get('qps'),
            qlim=server_data.get('qlim'),
            ord=server_data.get('ord'),
            wt=server_data.get('wt'),
            queries=server_data.get('queries'),
            drops=server_data.get('drops'),
            drate=server_data.get('drate'),
            lat=server_data.get('lat'),
            tcp=server_data.get('tcp'),
            outstanding=server_data.get('outstanding'),
            pools=server_data.get('pools')
        )

        # Validate the new server data for data quality monitoring
        is_valid, errors = new_server.validate()
        if not is_valid:
            logger.warning(f'Server validation failed for server_id {server_id}: {errors}')

        if server_id in existing_servers:
            # Server exists, check if update is needed
            existing_server = existing_servers[server_id]

            if new_server.needs_update(existing_server):
                # Get changed fields for logging
                changed = new_server.changed_fields(existing_server)
                logger.debug(f'Server {server_id} changed fields: {list(changed.keys())}')

                for field in DownstreamServer.COMPARABLE_FIELDS:
                    setattr(existing_server, field, getattr(new_server, field))
                updated_count += 1
            else:
                unchanged_count += 1
        else:
            # New server, add to database
            session.add(new_server)
            added_count += 1

    # Remove servers that no longer exist in the new data
    removed_count = 0
    for server_id, server in existing_servers.items():
        if server_id not in seen_server_ids:
            session.delete(server)
            removed_count += 1
    session.commit()
    logger.info(f'Synced servers for agent {agent_name}: '
                f'{added_count} added, {updated_count} updated, '
                f'{unchanged_count} unchanged, {removed_count} removed')


def sync_dynblocks_to_database(agent_name, parsed_blocks, session):
    """
    Sync dynamic blocks to database for a given agent
    """
    if parsed_blocks is None:
        return

    # Handle empty list (no blocks)
    if not isinstance(parsed_blocks, list):
        return

    # Delete existing blocks for this agent
    session.query(AgentDynBlock).filter_by(agent_name=agent_name).delete()

    # Add new blocks (can be empty list)
    for block_data in parsed_blocks:
        block = AgentDynBlock(
            agent_name=agent_name,
            what=block_data.get('what', ''),
            seconds=block_data.get('seconds'),
            blocks=block_data.get('blocks'),
            warning=block_data.get('warning'),
            action=block_data.get('action'),
            ebpf=block_data.get('ebpf'),
            reason=block_data.get('reason')
        )
        session.add(block)

    session.commit()
    logger.info(f'Synced {len(parsed_blocks)} dynamic blocks for agent {agent_name}')


def sync_topclients_to_database(agent_name, parsed_clients, session):
    """
    Sync top clients to database for a given agent
    """
    if not parsed_clients or not isinstance(parsed_clients, list):
        return

    # Delete existing top clients for this agent
    session.query(TopClient).filter_by(agent_name=agent_name).delete()

    # Add new top clients
    for client_data in parsed_clients:
        client = TopClient(
            agent_name=agent_name,
            rank=client_data.get('rank'),
            client=client_data.get('client', ''),
            queries=client_data.get('queries', 0),
            percentage=client_data.get('percentage', '0.0%')
        )
        session.add(client)

    session.commit()
    logger.info(f'Synced {len(parsed_clients)} top clients for agent {agent_name}')


def sync_topqueries_to_database(agent_name, parsed_queries, session):
    """
    Sync top queries to database for a given agent
    """
    if not parsed_queries or not isinstance(parsed_queries, list):
        return

    # Delete existing top queries for this agent
    session.query(TopQuery).filter_by(agent_name=agent_name).delete()

    # Add new top queries
    for query_data in parsed_queries:
        query = TopQuery(
            agent_name=agent_name,
            rank=query_data.get('rank'),
            query=query_data.get('query', ''),
            count=query_data.get('count', 0),
            percentage=query_data.get('percentage', '0.0%')
        )
        session.add(query)

    session.commit()
    logger.info(f'Synced {len(parsed_queries)} top queries for agent {agent_name}')


def sync_dynblock_rules_to_agents(session):
    """
    Sync active DynBlock rules from database to all active agents.
    This function is called every 10 seconds by the background syncer.
    """
    try:
        # Get all active DynBlock rules
        all_dyn_rules = session.query(DynBlockRule).all()
        # agents_rules = session.query(DynBlockRule).filter_by(is_active=True).all()
        all_rules = session.query(Rule).all()
        if len(all_dyn_rules) == 0:
            logger.info('No active DynBlock rules to sync')
            return

        agents = session.query(Agent).filter_by(is_active=True).all()
        logger.info(f'Syncing {len(all_dyn_rules)} DynBlock rules to {len(agents)} agents')

        # For each rule, sync to all agents
        for rule in all_dyn_rules:
            for agent in agents:
                if agent.group_id == rule.group_id or rule.group_id is None:
                    logger.debug(f'right agents group for  DynBlock {agent.agent_name}')
                    agent_url = agent.get_url()

                    # Check if this rule already exists before posting the command
                    rule_exists = False
                    list_uuid_all = []
                    uuid = extract_uuid_from_adddynblocks(rule.rule_command)
                    for all_rule in all_rules:
                        if all_rule.agent_name == agent.agent_name:
                            list_uuid_all.append(all_rule.uuid)
                        # else:
                        #    logger.info(f'Rule: {uuid} -found in all rules, but not for agent: {agent.agent_name}, planing to sync')

                    if uuid in list_uuid_all:
                        rule_exists = True
                    else:
                        rule_exists = False
                    if rule_exists:
                        if not rule.is_active:
                            logger.info(f'Rule: {uuid} - disabled and found on agent {agent.agent_name}, need to be deleted')
                            rm_rule_cmd = f'rmRule("{uuid}")'
                            try:
                                response = requests.post(
                                    f'{agent_url}/api/v1/command',
                                    json={'command': rm_rule_cmd},
                                    headers={
                                        'Content-Type': 'application/json',
                                        'X-Agent-Token': agent.agent_token
                                    },
                                    timeout=settings.TIMEOUT_AGENT
                                )
                                # sync_success = False
                                error_msg = None

                                if response.status_code == 200:
                                    response_data = response.json()
                                    if response_data.get('success'):
                                        # sync_success = True
                                        logger.debug(f'Successfully delete DynBlock rule {uuid} to agent {agent.agent_name}')
                                    else:
                                        error_msg = response_data.get('error', 'Unknown error')
                                        logger.warning(f'Failed to delete DynBlock rule {uuid} to agent {agent.agent_name}: {error_msg}')
                                else:
                                    error_msg = f'HTTP {response.status_code}'
                                    logger.warning(f'Failed to delete DynBlock rule {rule.uuid} to agent {agent.agent_name}: {error_msg}')
                            except Exception as e:
                                logger.error(f'Exception deletings DynBlock rule {uuid} to agent {agent.agent_name}: {str(e)}')
                        else:

                            logger.info(f'Rule {uuid} already exists on agent {agent.agent_name}, skipping')
                    else:
                        # Execute the DynBlock rule command
                        if rule.is_active:
                            logger.info(f'NO Rule {uuid} found on agent {agent.agent_name}, try to sync')
                            try:
                                response = requests.post(
                                    f'{agent_url}/api/v1/command',
                                    json={'command': rule.rule_command},
                                    headers={
                                        'Content-Type': 'application/json',
                                        'X-Agent-Token': agent.agent_token
                                    },
                                    timeout=settings.TIMEOUT_AGENT
                                )
                                # sync_success = False
                                error_msg = None
                                if response.status_code == 200:
                                    response_data = response.json()
                                    if response_data.get('success'):
                                        # sync_success = True
                                        logger.debug(f'Successfully synced DynBlock rule {rule.id} to agent {agent.agent_name}')
                                    else:
                                        error_msg = response_data.get('error', 'Unknown error')
                                        logger.warning(f'Failed to sync DynBlock rule {rule.id} to agent {agent.agent_name}: {error_msg}')
                                else:
                                    error_msg = f'HTTP {response.status_code}'
                                    logger.warning(f'Failed to sync DynBlock rule {rule.id} to agent {agent.agent_name}: {error_msg}')
                            except Exception as e:
                                logger.error(f'Exception syncing DynBlock rule {rule.id} to agent {agent.agent_name}: {str(e)}')
                        else:
                            logger.info(f'disable {uuid} does not found on agent {agent.agent_name}, everything is OK')
                else:
                    logger.debug(f'no (difrent groups) DynBlock {agent.agent_name} {rule.name}')
        session.commit()
        logger.debug('DynBlock rules sync completed')

    except Exception as e:
        session.rollback()
        logger.error(f'Error syncing DynBlock rules: {str(e)}')


def update_agent_v2(session, agent_id, new_status, new_version, new_service_time):
    agent = session.query(Agent).filter(Agent.id == agent_id).first()
    logger.info(f'update_agent: {agent.id} {agent.agent_name}')
    try:
        if agent:
            agent.status = new_status
            agent.version = new_version
            agent.service_time = new_service_time
            session.commit()
            return {
                'id': agent.id,
                'status': agent.status,
                'version': agent.version,
                'service_time': agent.service_time
            }
        return None
    except Exception as e:
        session.rollback()
        logger.info(f'Error update_agent: {str(e)}')


@app.route('/api/startsync', methods=['GET'])
async def sync_data():
    logger.info("Start syncer")
    session = db.get_session()
    try:
        agents = session.query(Agent).filter_by(is_active=True).all()
        # Get all active agents with eager loading of group relationship to avoid N+1 queries
        synced_count = 0
        failed_count = 0
        error_messages = []

        agents_status_list = []
        # Sync each active agent
        for agent in agents:
            agent_url = agent.get_url()
            logger.debug(f'start sync: {agent.agent_name}')

            rules_success = False
            servers_success = False
            agent_status = 'unknown'

            agent_info = {
                'id': agent.id,
                'status': agent.status,
                'version': agent.version,
                'service_time': agent.service_time
            }
            #  Try to get agent status
            try:
                response = requests.get(f'{agent_url}/health', timeout=settings.TIMEOUT_AGENT)
                if response.status_code == 200:
                    data = response.json()
                    agent_info['status'] = 'online'
                    agent_info['version'] = data.get('version', 'Unknown')
                    agent_info['service_time'] = data.get('service_time', 'Unknown')
                    update_agent_v2(session, agent.id, agent_info['status'], agent_info['version'], agent_info['service_time'])
                    logger.info(f'Sync agent api: {agent_info}')
                else:
                    agent_info['status'] = 'offline'
                    agent_info['version'] = 'Unknown'
                    update_agent_v2(session, agent.id, agent_info['status'], agent_info['version'], agent_info['service_time'])
                    logger.info('Error sync status:')

            except requests.exceptions.RequestException as e:
                agent_info['status'] = 'offline'
                agent_info['version'] = 'Unknown'
                update_agent_v2(session, agent.id, agent_info['status'], agent_info['version'], agent_info['service_time'])
                logger.info(f'error sync status: {str(e)}')

            time.sleep(0.1)
            # Execute showRules() command
            try:
                response = requests.post(
                    f'{agent_url}/api/v1/command',
                    json={'command': 'showRules({showUUIDs=true})'},
                    headers={
                        'Content-Type': 'application/json',
                        'X-Agent-Token': agent.agent_token
                    },
                    timeout=settings.TIMEOUT_AGENT
                )

                if response.status_code == 200:
                    response_data = response.json()

                    if response_data.get('success'):
                        result_text = response_data.get('result', '')
                        parsed_rules = parsers.parse_showrules_output(result_text)
                        sync_rules_to_database(agent.agent_name, parsed_rules, session)
                        rules_success = True
                        agent_status = 'online'  # Agent responded successfully
                else:
                    agent_status = 'error'  # Non-200 response

            except requests.exceptions.RequestException as e:
                agent_status = 'offline'  # Connection error
                error_msg = f'{agent.agent_name} rules: {str(e)}'
                logger.debug(f'Failed to sync rules for agent {agent.agent_name}: {str(e)}')
                error_messages.append(error_msg)
            except Exception as e:
                # Catch other exceptions (parsing, database, etc.) to prevent sync failure
                agent_status = 'error'  # Other errors
                error_msg = f'{agent.agent_name} rules: {str(e)}'
                logger.debug(f'Failed to sync rules for agent {agent.agent_name}: {str(e)}')
                error_messages.append(error_msg)
            time.sleep(0.1)
            # Execute showServers() command
            try:
                response = requests.post(
                    f'{agent_url}/api/v1/command',
                    json={'command': 'showServers()'},
                    headers={
                        'Content-Type': 'application/json',
                        'X-Agent-Token': agent.agent_token
                    },
                    timeout=settings.TIMEOUT_AGENT
                )
                if response.status_code == 200:
                    response_data = response.json()
                    if response_data.get('success'):
                        result_text = response_data.get('result', '')
                        parsed_servers = parsers.parse_showservers_output(result_text)
                        if parsed_servers is not None:
                            sync_servers_to_database(agent.agent_name, parsed_servers, session)
                            servers_success = True
                    else:
                        error_msg = (
                            f'{agent.agent_name} servers: '
                            f'{response_data.get("error", "Unknown error")}'
                        )
                        error_messages.append(error_msg)
                else:
                    error_messages.append(f'{agent.agent_name} servers: HTTP {response.status_code}')
            except Exception as e:
                logger.debug(f'Failed to sync servers for agent {agent.agent_name}: {str(e)}')
                error_messages.append(f'{agent.agent_name} servers: {str(e)}')
            time.sleep(0.1)
            # Execute showDynBlocks() command
            try:
                response = requests.post(
                    f'{agent_url}/api/v1/command',
                    json={'command': 'showDynBlocks()'},
                    headers={
                        'Content-Type': 'application/json',
                        'X-Agent-Token': agent.agent_token
                    },
                    timeout=settings.TIMEOUT_AGENT
                )

                if response.status_code == 200:
                    response_data = response.json()
                    if response_data.get('success'):
                        result_text = response_data.get('result', '')
                        parsed_blocks = parsers.parse_showdynblocks_detailed(result_text)
                        if parsed_blocks is not None:
                            sync_dynblocks_to_database(agent.agent_name, parsed_blocks, session)
                    else:
                        # Log warning but don't fail the overall sync
                        logger.warning(f'{response_data.get("error", "Unknown error")}')
                        logger.warning(f'Failed to sync dynamic blocks for agent {agent.agent_name}')
                else:
                    logger.warning(f'Failed to sync dynamic blocks for agent {agent.agent_name}: {response.status_code}')
            except Exception as e:
                logger.warning(f'Failed to sync dynamic blocks for agent {agent.agent_name}: {str(e)}')
                # Don't add to error_messages as dynblocks are optional/informational
            time.sleep(0.1)
            # Execute topClients() command
            try:
                response = requests.post(
                    f'{agent_url}/api/v1/command',
                    json={'command': 'topClients()'},
                    headers={
                        'Content-Type': 'application/json',
                        'X-Agent-Token': agent.agent_token
                    },
                    timeout=settings.TIMEOUT_AGENT
                )
                if response.status_code == 200:
                    response_data = response.json()
                    if response_data.get('success'):
                        result_text = response_data.get('result', '')
                        parsed_clients = parsers.parse_topclients_output(result_text)
                        if parsed_clients is not None:
                            sync_topclients_to_database(agent.agent_name, parsed_clients, session)
                    else:
                        # Log warning but don't fail the overall sync
                        logger.warning(
                            f'Failed to sync top clients for agent {agent.agent_name}: '
                            f'{response_data.get("error", "Unknown error")}'
                        )
                else:
                    logger.warning(
                        f'Failed to sync top clients for agent {agent.agent_name}: '
                        f'HTTP {response.status_code}'
                    )
            except Exception as e:
                logger.warning(f'Failed to sync top clients for agent {agent.agent_name}: {str(e)}')
            time.sleep(0.1)
            # Execute topResponses(10, 3) command NXDOMAIN
            try:
                response = requests.post(
                    f'{agent_url}/api/v1/command',
                    json={'command': 'topResponses(10)'},
                    headers={
                        'Content-Type': 'application/json',
                        'X-Agent-Token': agent.agent_token
                    },
                    timeout=settings.TIMEOUT_AGENT
                )

                if response.status_code == 200:
                    response_data = response.json()
                    if response_data.get('success'):
                        result_text = response_data.get('result', '')
                        parsed_queries = parsers.parse_topqueries_output(result_text)
                        if parsed_queries is not None:
                            sync_topqueries_to_database(agent.agent_name, parsed_queries, session)
                    else:
                        # Log warning but don't fail the overall sync
                        logger.warning(
                            f'Failed to sync top responses for agent {agent.agent_name}: '
                            f'{response_data.get("error", "Unknown error")}'
                        )
                else:
                    logger.warning(
                        f'Failed to sync top responses for agent {agent.agent_name}: '
                        f'HTTP {response.status_code}'
                    )
            except Exception as e:
                logger.warning(f'Failed to sync top responses for agent {agent.agent_name}: {str(e)}')
                # Don't add to error_messages as top responses are optional/informational
            # Count agent as synced if both commands succeeded
            if rules_success and servers_success:
                synced_count += 1
            elif rules_success or servers_success:
                # At least one command succeeded, but not both - count as partial failure
                failed_count += 1
            else:
                # Both commands failed
                failed_count += 1

            # Add agent status to the list for metrics export
            agents_status_list.append({
                'agent_name': agent.agent_name,
                'status': agent_status,
                'is_active': agent.is_active,
                'group_name': agent.group.name if agent.group else None
            })
        logger.info(failed_count)

        # Add inactive agents to the status list (marked as DISABLED)
        # Note: This query gets agents with is_active=False, which are not processed
        # in the main loop above (which only processes is_active=True agents)
        inactive_agents = session.query(Agent).options(joinedload(Agent.group)).filter_by(is_active=False).all()
        for agent in inactive_agents:
            agents_status_list.append({
                'agent_name': agent.agent_name,
                'status': 'disabled',
                'is_active': agent.is_active,
                'group_name': agent.group.name if agent.group else None
            })

        # Update sync status in database
        sync_status = session.query(SyncStatus).first()
        if not sync_status:
            sync_status = SyncStatus()
            session.add(sync_status)
        failed_count

        sync_status.last_sync_time = datetime.now(timezone.utc)
        sync_status.synced_agents_count = synced_count
        sync_status.failed_agents_count = failed_count

        # Set status based on results
        if synced_count > 0 and failed_count == 0:
            sync_status.status = 'Success'
            sync_status.error_message = None
        elif synced_count > 0 and failed_count > 0:
            sync_status.status = 'Partial'
            sync_status.error_message = '; '.join(error_messages[:3])  # Keep first 3 errors
        elif failed_count > 0:
            sync_status.status = 'Failed'
            sync_status.error_message = '; '.join(error_messages[:3])
        else:
            sync_status.status = 'No active agents'
            sync_status.error_message = None

        session.commit()
        logger.debug(f'Background sync completed: {synced_count} synced, {failed_count} failed')
        # Export metrics to Victoria Metrics if enabled
        if victoria_metrics_exporter and victoria_metrics_exporter.enabled:
            try:
                # Get all topclients and topqueries from database
                all_topclients = session.query(TopClient).all()
                all_topqueries = session.query(TopQuery).all()

                # Export to Victoria Metrics
                victoria_metrics_exporter.export_metrics(
                    topclients=all_topclients,
                    topqueries=all_topqueries,
                    agents_status=agents_status_list
                )
            except Exception as vm_error:
                logger.error(f'Error exporting metrics to Victoria Metrics: {str(vm_error)}')
        sync_dynblock_rules_to_agents(session)
        return jsonify({"status": "success", "message": "Sync completed"})

    except Exception as e:
        logger.error(f"Sync failed: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500
    finally:
        session.close()


def log_audit(action, details=None, ip_address=None):
    """
    Log an audit event to the audit_logs table
    """
    try:
        # Get IP address from request if not provided
        if ip_address is None:
            if request:
                # Try to get real IP from proxy headers
                ip_address = request.headers.get('X-Forwarded-For', request.remote_addr)
                if ip_address and ',' in ip_address:
                    # Take first IP in case of multiple proxies
                    ip_address = ip_address.split(',')[0].strip()
            else:
                ip_address = 'unknown'
        session = db.get_session()
        try:
            audit_log = AuditLog(
                ip_address=ip_address,
                action=action,
                details=details
            )
            session.add(audit_log)
            session.commit()
            logger.debug(f'Audit log created: {action}')
        except Exception as e:
            session.rollback()
            logger.error(f'Error creating audit log: {str(e)}')
        finally:
            session.close()
    except Exception as e:
        logger.error(f'Error in log_audit: {str(e)}')


@app.route('/')
def dashboard():
    """Render the main console page"""
    return render_template('dashboard.html')

# @app.route('/dashboard')
# def dashboard2():
#     """Render the main console page"""
#     return render_template('dashboard.html')


@app.route('/agents')
def agents():
    """Render the agents management page"""
    return render_template('index.html')


@app.route('/agents/<int:rule_uuid>')
def agents_id(rule_uuid: int):
    """Render the agents management page"""
    return render_template('index.html')


@app.route('/rules')
def rules():
    """Render the rules page"""
    return render_template('rules.html')


@app.route('/rules/<string:rule_uuid>')
def rules_by_uuid(rule_uuid: str):
    """Render the rules page filtered to a specific rule by UUID"""
    return render_template('rules.html')


@app.route('/summary')
def summary():
    """Render the summary page"""
    return render_template('summary.html')


@app.route('/dynblock-rules')
def dynblock_rules_page():
    """Render the DynBlock rules management page"""
    return render_template('dynblock_rules.html')


@app.route('/dynblock-rules/<string:rule_uuid>')
def dynblock_by_uuid(rule_uuid: str):
    """Render the DynBlock rules management page"""
    return render_template('dynblock_rules.html')


@app.route('/audit')
def audit_page():
    """Render the audit logs page"""
    return render_template('audit.html')


@app.route('/dashboard')
def dashboard_page():
    """Render the dashboard page"""
    return render_template('dashboard.html')


@app.route('/static/<path:filename>')
def static_files(filename):
    return send_from_directory('static', filename)


@app.errorhandler(404)
def page_not_found(e):
    return render_template('errors/404.html'), 404


@app.errorhandler(500)
def server_not_work(e):
    return render_template('errors/500.html'), 500


@app.route('/api/rules', methods=['GET'])
def get_all_rules():
    """
    Get all rules from database
    """
    session = db.get_session()
    try:
        rules = session.query(Rule).all()
        dynblock_uuids = set(dbr.rule_uuid for dbr in session.query(DynBlockRule.rule_uuid).distinct())
        online_agent_names = set(
            agent.agent_name for agent in session.query(Agent)
            .filter(Agent.status == 'online')
            .all()
        )
        result = []
        for rule in rules:
            rule_dict = {
                'id': rule.id,
                'agent_name': rule.agent_name,
                'agent_online': 1 if rule.agent_name in online_agent_names else 0,
                'rule_id': rule.rule_id,
                'name': rule.name,
                'matches': rule.matches,
                'rule': rule.rule,
                'action': rule.action,
                'uuid': rule.uuid,
                'has_synced': 1 if rule.uuid in dynblock_uuids else 0,
                'creation_order': rule.creation_order,
                'updated_at': rule._serialize_datetime(rule.updated_at) if hasattr(rule, '_serialize_datetime') else rule.updated_at
            }
            result.append(rule_dict)

        print(result)
        return jsonify({
            'success': True,
            'rules': result
        })
    finally:
        session.close()


@app.route('/api/rules/<int:rule_id>', methods=['DELETE'])
def delete_rule(rule_id):
    """Delete a rule by its database ID"""
    session = db.get_session()
    try:
        rule = session.query(Rule).filter_by(id=rule_id).first()
        if not rule:
            return jsonify({
                'success': False,
                'error': 'Rule not found'
            }), 404

        rule_name = rule.name or f"Rule {rule_id}"
        session.delete(rule)
        session.commit()

        logger.info(f'Deleted rule: {rule_id}')

        log_audit(
            action='Delete Rule',
            details=f"Deleted rule '{rule_name}'"
        )

        return jsonify({
            'success': True,
            'message': 'Rule deleted successfully'
        })

    except Exception as e:
        session.rollback()
        logger.error(f'Error deleting rule: {str(e)}')
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500
    finally:
        session.close()


@app.route('/api/rules/<path:rule_uuid>', methods=['GET'])
def get_all_rules_id(rule_uuid: str):
    """
    Get all rules from database
    """
    session = db.get_session()
    try:
        # Преобразование
        result = []

        # Получаем все DynBlockRule и создаем множество uuid для быстрого поиска
        dynblock_uuids = set(dbr.rule_uuid for dbr in session.query(DynBlockRule.rule_uuid).distinct())

        # Получаем конкретное правило по uuid
        rules = session.query(Rule).filter(Rule.uuid == rule_uuid).all()
        online_agent_names = set(
            agent.agent_name for agent in session.query(Agent)
            .filter(Agent.status == 'online')
            .all()
        )
        if not rules:
            session.close()
            return jsonify({
                'success': False,
                'rules': result
            })
        if len(rules) >= 1:
            for rule in rules:
                rule_dict = {
                    'id': rule.id,
                    'agent_name': rule.agent_name,
                    'agent_online': 1 if rule.agent_name in online_agent_names else 0,
                    'rule_id': rule.rule_id,
                    'name': rule.name,
                    'matches': rule.matches,
                    'rule': rule.rule,
                    'action': rule.action,
                    'uuid': rule.uuid,
                    'has_synced': 1 if rule.uuid in dynblock_uuids else 0,
                    'creation_order': rule.creation_order,
                    'updated_at': rule._serialize_datetime(rule.updated_at) if hasattr(rule, '_serialize_datetime') else rule.updated_at
                }
                result.append(rule_dict)
        else:
            rule_dict = {
                'id': rules.id,
                'agent_name': rules.agent_name,
                'rule_id': rules.rule_id,
                'name': rules.name,
                'matches': rules.matches,
                'rule': rules.rule,
                'action': rules.action,
                'uuid': rules.uuid,
                'has_synced': 1 if rules.uuid in dynblock_uuids else 0,
                'creation_order': rules.creation_order,
                'updated_at': rules._serialize_datetime(rules.updated_at) if hasattr(rules, '_serialize_datetime') else rules.updated_at
            }
            result.append(rule_dict)
        print(result)
        return jsonify({
            'success': True,
            'rules': result
        })
    finally:
        session.close()


@app.route('/api/agents/rules', methods=['GET'])
def get_agents_rules():
    """Get rules count for all agents"""
    session = db.get_session()
    try:
        # Eager load group relationship for consistency
        agents = session.query(Agent).options(joinedload(Agent.group)).filter_by(is_active=True).all()

        if not agents:
            return jsonify({
                'success': True,
                'agents_rules': []
            })

        # Get all agent names
        agent_names = [agent.agent_name for agent in agents]

        # Fetch all rules for active agents in a single query
        all_rules = session.query(Rule).filter(Rule.agent_name.in_(agent_names)).all()
        dynblock_uuids = set(dbr.rule_uuid for dbr in session.query(DynBlockRule.rule_uuid).distinct())

        # Group rules by agent_name
        rules_by_agent = {}
        for rule in all_rules:
            logger.debug(f'Get agents rules {rule}')
            rule_info = {
                'id': rule.id,
                'agent_name': rule.agent_name,
                'rule_id': rule.rule_id,
                'name': rule.name,
                'matches': rule.matches,
                'rule': rule.rule,
                'action': rule.action,
                'uuid': rule.uuid,
                'has_synced': 1 if rule.uuid in dynblock_uuids else 0,
                'creation_order': rule.creation_order,
                'updated_at': rule.updated_at
            }
            if rule.agent_name not in rules_by_agent:
                rules_by_agent[rule.agent_name] = []

            rules_by_agent[rule.agent_name].append(rule_info)

        # Build response
        agents_rules = []
        for agent in agents:
            rules = rules_by_agent.get(agent.agent_name, [])
            agents_rules.append({
                'agent_id': agent.id,
                'agent_name': agent.agent_name,
                'rules_count': len(rules),
                'rules': rules
            })
        return jsonify({
            'success': True,
            'agents_rules': agents_rules
        })
    finally:
        session.close()


@app.route('/api/agents/servers', methods=['GET'])
def get_agents_servers():
    """Get downstream servers for all agents"""
    session = db.get_session()
    try:
        # Eager load group relationship for consistency
        agents = session.query(Agent).options(joinedload(Agent.group)).filter_by(is_active=True).all()

        # Early return if no agents to avoid unnecessary query with empty IN clause
        if not agents:
            return jsonify({
                'success': True,
                'agents_servers': []
            })

        # Get all agent names
        agent_names = [agent.agent_name for agent in agents]

        # Fetch all servers for active agents in a single query
        all_servers = session.query(DownstreamServer).filter(DownstreamServer.agent_name.in_(agent_names)).all()

        # Group servers by agent_name
        servers_by_agent = {}
        for server in all_servers:
            if server.agent_name not in servers_by_agent:
                servers_by_agent[server.agent_name] = []
            servers_by_agent[server.agent_name].append(server)

        # Build response
        agents_servers = []
        for agent in agents:
            servers = servers_by_agent.get(agent.agent_name, [])
            agents_servers.append({
                'agent_id': agent.id,
                'agent_name': agent.agent_name,
                'servers_count': len(servers),
                'servers': [server.to_dict() for server in servers]
            })

        return jsonify({
            'success': True,
            'agents_servers': agents_servers
        })
    finally:
        session.close()


@app.route('/api/agents/topclients', methods=['GET'])
def get_agents_topclients():
    """Get top clients for all agents"""
    session = db.get_session()
    try:
        # Eager load group relationship for consistency
        agents = session.query(Agent).options(joinedload(Agent.group)).filter_by(is_active=True).all()

        # Early return if no agents to avoid unnecessary query with empty IN clause
        if not agents:
            return jsonify({
                'success': True,
                'agents_topclients': []
            })

        agent_names = [agent.agent_name for agent in agents]

        # Fetch all topclients for active agents in a single query
        all_topclients = session.query(TopClient).filter(TopClient.agent_name.in_(agent_names)).all()

        # Group topclients by agent_name
        topclients_by_agent = {}
        for client in all_topclients:
            if client.agent_name not in topclients_by_agent:
                topclients_by_agent[client.agent_name] = []
            topclients_by_agent[client.agent_name].append(client)

        # Build response
        agents_topclients = []
        for agent in agents:
            topclients = topclients_by_agent.get(agent.agent_name, [])
            agents_topclients.append({
                'agent_id': agent.id,
                'agent_name': agent.agent_name,
                'topclients_count': len(topclients),
                'topclients': [client.to_dict() for client in topclients]
            })

        return jsonify({
            'success': True,
            'agents_topclients': agents_topclients
        })
    finally:
        session.close()


@app.route('/api/agents/topqueries', methods=['GET'])
def get_agents_topqueries():
    """Get top queries for all agents"""
    session = db.get_session()
    try:
        # Eager load group relationship for consistency
        agents = session.query(Agent).options(joinedload(Agent.group)).filter_by(is_active=True).all()

        # Early return if no agents to avoid unnecessary query with empty IN clause
        if not agents:
            return jsonify({
                'success': True,
                'agents_topqueries': []
            })

        # Get all agent names
        agent_names = [agent.agent_name for agent in agents]

        # Fetch all topqueries for active agents in a single query
        all_topqueries = session.query(TopQuery).filter(TopQuery.agent_name.in_(agent_names)).all()

        # Group topqueries by agent_name
        topqueries_by_agent = {}
        for query in all_topqueries:
            if query.agent_name not in topqueries_by_agent:
                topqueries_by_agent[query.agent_name] = []
            topqueries_by_agent[query.agent_name].append(query)

        # Build response
        agents_topqueries = []
        for agent in agents:
            topqueries = topqueries_by_agent.get(agent.agent_name, [])
            agents_topqueries.append({
                'agent_id': agent.id,
                'agent_name': agent.agent_name,
                'topqueries_count': len(topqueries),
                'topqueries': [query.to_dict() for query in topqueries]
            })

        return jsonify({
            'success': True,
            'agents_topqueries': agents_topqueries
        })
    finally:
        session.close()


@app.route('/api/sync-status', methods=['GET'])
def get_sync_status():
    """Get background sync status"""
    session = db.get_session()
    try:
        sync_status = session.query(SyncStatus).first()

        if not sync_status:
            # Return default status if no sync has occurred yet
            return jsonify({
                'success': True,
                'sync_status': {
                    'last_sync_time': None,
                    'status': 'Never',
                    'synced_agents_count': 0,
                    'failed_agents_count': 0,
                    'error_message': None
                }
            })

        return jsonify({
            'success': True,
            'sync_status': sync_status.to_dict()
        })
    except Exception as e:
        logger.error(f'Error fetching sync status: {str(e)}')
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500
    finally:
        session.close()


@app.route('/metrics', methods=['GET'])
def get_metrics():
    """Get Prometheus-formatted metrics for all agents"""
    session = db.get_session()
    try:
        # Get all topclients, topqueries, and agent status
        all_topclients = session.query(TopClient).all()
        all_topqueries = session.query(TopQuery).all()

        agents = session.query(Agent).options(joinedload(Agent.group)).all()
        agents_status_list = []
        for agent in agents:
            agents_status_list.append({
                'agent_name': agent.agent_name,
                'status': 'unknown' if agent.is_active else 'disabled',
                'is_active': agent.is_active,
                'group_name': agent.group.name if agent.group else None
            })

        if victoria_metrics_exporter:
            metrics_text = victoria_metrics_exporter.get_prometheus_metrics(
                topclients=all_topclients,
                topqueries=all_topqueries,
                agents_status=agents_status_list
            )
            return metrics_text, 200, {'Content-Type': 'text/plain; version=0.0.4'}
        else:
            return '# Victoria Metrics exporter not initialized\n', 200, {'Content-Type': 'text/plain; version=0.0.4'}
    except Exception as e:
        logger.error(f'Error generating metrics: {str(e)}')
        return f'# Error generating metrics: {str(e)}\n', 500, {'Content-Type': 'text/plain; version=0.0.4'}
    finally:
        session.close()


@app.route('/api/backend-health', methods=['GET'])
def get_backend_health():
    """Health check endpoint for the console.py backend"""
    try:
        # Simple health check - verify database connection
        session = db.get_session()
        session.execute(sa.text('SELECT 1'))
        session.close()

        return jsonify({
            'success': True,
            'status': 'healthy',
            'service': 'dnsdist-console',
            'timestamp': utc_now().isoformat()
        }), 200
    except Exception as e:
        logger.error(f'Backend health check failed: {str(e)}')
        return jsonify({
            'success': False,
            'status': 'unhealthy',
            'service': 'dnsdist-console',
            'error': str(e),
            'timestamp': utc_now().isoformat()
        }), 500


@app.route('/api/agents', methods=['GET'])
def get_agents():
    """Get list of agents with their status from database"""
    session = db.get_session()
    try:
        agents = session.query(Agent).options(joinedload(Agent.group)).all()

        # agents = session.query(Agent)\
        #     .options(joinedload(Agent.group))\
        #     .order_by(desc(Agent.is_active))\
        #     .all()
        agents_status = []

        for agent in agents:
            agent_url = agent.get_url()
            agent_info = {
                'id': agent.id,
                'url': agent_url,
                'name': agent.agent_name,
                'agent_ip': agent.agent_ip,
                'agent_port': agent.agent_port,
                'agent_token': agent.agent_token,
                'is_active': agent.is_active,
                'group_id': agent.group_id,
                'group_name': agent.group.name if agent.group else None,
                'status': agent.status,
                'version': agent.version,
                'service_time': agent.service_time
            }
            agents_status.append(agent_info)

        return jsonify(agents_status)
    finally:
        session.close()


@app.route('/api/agents/<int:agent_id>', methods=['GET'])
def get_agent_id(agent_id):

    session = db.get_session()
    try:
        agent = session.query(Agent).filter_by(id=agent_id).first()

        # if not agent:
        #     return jsonify({
        #         'success': False,
        #         'error': 'agent not found'
        #     }), 404

        agents_status = []

        agent_info = {
            'id': agent.id,
            'url': agent.get_url(),
            'name': agent.agent_name,
            'agent_ip': agent.agent_ip,
            'agent_port': agent.agent_port,
            'agent_token': agent.agent_token,
            'is_active': agent.is_active,
            'group_id': agent.group_id,
            'group_name': agent.group.name if agent.group else None,
            'status': agent.status,
            'version': agent.version,
            'service_time': agent.service_time
        }
        agents_status.append(agent_info)

        return jsonify(agents_status)
    finally:
        session.close()


@app.route('/api/agents', methods=['POST'])
def create_agent():
    """Create a new agent"""
    data = request.get_json()

    if not data:
        return jsonify({'success': False, 'error': 'No data provided'}), 400

    required_fields = ['agent_name', 'agent_ip', 'agent_port', 'agent_token']
    for field in required_fields:
        if field not in data:
            return jsonify({'success': False, 'error': f'Missing required field: {field}'}), 400

    session = db.get_session()
    try:
        # Check if agent with same name already exists
        existing = session.query(Agent).filter_by(agent_name=data['agent_name']).first()
        if existing:
            return jsonify({'success': False, 'error': 'Agent with this name already exists'}), 400

        agent = Agent(
            agent_name=data['agent_name'],
            agent_ip=data['agent_ip'],
            agent_port=int(data['agent_port']),
            agent_token=data['agent_token'],
            group_id=data.get('group_id')
        )

        session.add(agent)
        session.commit()

        # Re-query agent with group relationship eagerly loaded to avoid lazy loading
        agent = session.query(Agent).options(joinedload(Agent.group)).filter_by(id=agent.id).first()

        # Log audit event
        log_audit(
            action='Create Agent',
            details=f"Created agent '{agent.agent_name}' with IP {agent.agent_ip}:{agent.agent_port}"
        )

        return jsonify({'success': True, 'agent': agent.to_dict()}), 201
    except Exception as e:
        session.rollback()
        logger.error(f'Error creating agent: {str(e)}')
        return jsonify({'success': False, 'error': str(e)}), 500
    finally:
        session.close()


@app.route('/api/agents/<int:agent_id>', methods=['PUT'])
def update_agent(agent_id):
    """Update an existing agent"""
    data = request.get_json()

    if not data:
        return jsonify({'success': False, 'error': 'No data provided'}), 400

    session = db.get_session()
    try:
        agent = session.query(Agent).filter_by(id=agent_id).first()
        if not agent:
            return jsonify({'success': False, 'error': 'Agent not found'}), 404

        # Track status change for logging
        old_is_active = agent.is_active

        if 'agent_name' in data:
            agent.agent_name = data['agent_name']
        if 'agent_ip' in data:
            agent.agent_ip = data['agent_ip']
        if 'agent_port' in data:
            agent.agent_port = int(data['agent_port'])
        if 'agent_token' in data:
            agent.agent_token = data['agent_token']
        if 'group_id' in data:
            agent.group_id = data['group_id']
        if 'is_active' in data:
            agent.is_active = bool(data['is_active'])
            

        # Log status change to history if is_active was changed
        status_changed = False
        if 'is_active' in data and old_is_active != agent.is_active:
            
            status_changed = True
            status_text = "available" if agent.is_active else "disabled"
            if not agent.is_active:
                agent.status = "offline"
            history = CommandHistory(
                agent_name=agent.agent_name,
                command=f"agent set new status {status_text}",
                success=True,
                result=f"Agent status changed to {status_text}"
            )
            session.add(history)

            # Log audit event for enable/disable
            log_audit(
                action='Enable Agent' if agent.is_active else 'Disable Agent',
                details=f"Agent '{agent.agent_name}' was {'enabled' if agent.is_active else 'disabled'}"
            )

        session.commit()

        # Re-query agent with group relationship eagerly loaded to avoid lazy loading
        agent = session.query(Agent).options(joinedload(Agent.group)).filter_by(id=agent.id).first()

        if not status_changed or len(data) > 1:
            log_audit(
                action='Update Agent',
                details=f"Updated agent '{agent.agent_name}'"
            )

        return jsonify({'success': True, 'agent': agent.to_dict()})
    except Exception as e:
        session.rollback()
        logger.error(f'Error updating agent: {str(e)}')
        return jsonify({'success': False, 'error': str(e)}), 500
    finally:
        session.close()


@app.route('/api/agents/<int:agent_id>', methods=['DELETE'])
def delete_agent(agent_id):
    """Delete an agent (hard delete from database)"""
    session = db.get_session()
    try:
        agent = session.query(Agent).filter_by(id=agent_id).first()
        if not agent:
            return jsonify({'success': False, 'error': 'Agent not found'}), 404

        agent_name = agent.agent_name
        session.delete(agent)
        session.commit()

        # Log audit event
        log_audit(
            action='Delete Agent',
            details=f"Deleted agent '{agent_name}'"
        )

        return jsonify({'success': True, 'message': 'Agent deleted successfully'})
    except Exception as e:
        session.rollback()
        logger.error(f'Error deleting agent: {str(e)}')
        return jsonify({'success': False, 'error': str(e)}), 500
    finally:
        session.close()


@app.route('/api/command', methods=['POST'])
def execute_command():
    """Execute a command on a specific agent"""
    data = request.get_json()

    if not data or 'agent_id' not in data or 'command' not in data:
        return jsonify({
            'success': False,
            'error': 'Missing agent_id or command in request'
        }), 400

    agent_id = data['agent_id']
    command = data['command']

    session = db.get_session()
    try:
        # Get agent from database
        agent = session.query(Agent).filter_by(id=agent_id, is_active=True).first()
        if not agent:
            return jsonify({
                'success': False,
                'error': 'Invalid or inactive agent'
            }), 400

        agent_url = agent.get_url()

        # Send command to agent
        try:
            response = requests.post(
                f'{agent_url}/api/v1/command',
                json={'command': command},
                headers={
                    'Content-Type': 'application/json',
                    'X-Agent-Token': agent.agent_token
                },
                timeout=settings.TIMEOUT_AGENT
            )
            response_data = response.json()

            # Check if this is a showRules() command and parse the output
            if response_data.get('success') and command.strip().startswith('showRules'):
                result_text = response_data.get('result', '')
                parsed_rules = parsers.parse_showrules_output(result_text)
                if parsed_rules is not None:
                    # Add parsed rules to response
                    response_data['parsed_rules'] = parsed_rules
                    # Sync rules to database
                    # sync_rules_to_database(agent.agent_name, parsed_rules, session)

            # Check if this is a showServers() command and parse the output
            if response_data.get('success') and command.strip().startswith('showServers'):
                result_text = response_data.get('result', '')
                parsed_servers = parsers.parse_showservers_output(result_text)
                if parsed_servers is not None:
                    # Add parsed servers to response
                    response_data['parsed_servers'] = parsed_servers
                    # Sync servers to database

                    # sync_servers_to_database(agent.agent_name, parsed_servers, session)

            # Save to history - encode result as JSON if it's not a simple string
            result = response_data.get('result', '')
            if result and not isinstance(result, str):
                result = json.dumps(result)
            elif isinstance(result, str):
                result = result
            else:
                result = ''

            # Save to history
            history = CommandHistory(
                agent_name=agent.agent_name,
                command=command,
                success=response_data.get('success', False),
                result=result,
                error=response_data.get('error')
            )
            session.add(history)
            session.commit()

            return jsonify(response_data), response.status_code

        except requests.exceptions.RequestException as e:
            logger.error(f'Error sending command to agent {agent_url}: {str(e)}')

            # Save failed attempt to history
            history = CommandHistory(
                agent_name=agent.agent_name,
                command=command,
                success=False,
                error=f'Failed to connect to agent: {str(e)}'
            )
            session.add(history)
            session.commit()

            return jsonify({
                'success': False,
                'error': f'Failed to connect to agent: {str(e)}'
            }), 500
    finally:
        session.close()


@app.route('/api/command/broadcast', methods=['POST'])
def execute_broadcast_command():
    """Execute a command on all agents or agents in a specific group"""
    data = request.get_json()

    if not data or 'command' not in data:
        return jsonify({
            'success': False,
            'error': 'Missing command in request'
        }), 400

    command = data['command']
    group_id = data.get('group_id')  # Optional: filter by group
    results = []

    session = db.get_session()
    try:
        # Get agents based on group filter
        query = session.query(Agent).filter_by(is_active=True)

        if group_id is not None and group_id != 'all':
            # Filter by specific group
            if group_id == 'none':
                # Agents with no group
                query = query.filter(Agent.group_id.is_(None))
            else:
                # Agents in specific group
                query = query.filter_by(group_id=int(group_id))

        agents = query.all()

        # Send command to all agents
        for agent in agents:
            agent_url = agent.get_url()
            result = {
                'agent_id': agent.id,
                'agent_url': agent_url,
                'agent_name': agent.agent_name,
                'success': False,
                'result': None,
                'error': None
            }
            try:
                response = requests.post(
                    f'{agent_url}/api/v1/command',
                    json={'command': command},
                    headers={
                        'Content-Type': 'application/json',
                        'X-Agent-Token': agent.agent_token
                    },
                    timeout=settings.TIMEOUT_AGENT
                )
                response_data = response.json()
                result['success'] = response_data.get('success', False)
                result['result'] = response_data.get('result')
                result['error'] = response_data.get('error')

                # Check if this is a showRules() command and parse the output
                if result['success'] and command.strip().startswith('showRules'):
                    result_text = result['result']
                    parsed_rules = parsers.parse_showrules_output(result_text)
                    if parsed_rules is not None:
                        # Add parsed rules to result
                        result['parsed_rules'] = parsed_rules
                        # Sync rules to database
                        # sync_rules_to_database(agent.agent_name, parsed_rules, session)

                # Check if this is a showServers() command and parse the output
                if result['success'] and command.strip().startswith('showServers'):
                    result_text = result['result']
                    parsed_servers = parsers.parse_showservers_output(result_text)
                    if parsed_servers is not None:
                        # Add parsed servers to result
                        result['parsed_servers'] = parsed_servers
                        # Sync servers to database
                        # sync_servers_to_database(agent.agent_name, parsed_servers, session)

                # Save to history - encode result as JSON if it's not a simple string
                result_data = result['result']
                if result_data and not isinstance(result_data, str):
                    result_data = json.dumps(result_data)
                elif isinstance(result_data, str):
                    result_data = result_data
                else:
                    result_data = None

                # Save to history
                history = CommandHistory(
                    agent_name=agent.agent_name,
                    command=command,
                    success=result['success'],
                    result=result_data,
                    error=result['error']
                )
                session.add(history)

            except requests.exceptions.RequestException as e:
                logger.error(f'Error sending command to agent {agent_url}: {str(e)}')
                result['error'] = f'Failed to connect to agent: {str(e)}'

                # Save failed attempt to history
                history = CommandHistory(
                    agent_name=agent.agent_name,
                    command=command,
                    success=False,
                    error=result['error']
                )
                session.add(history)
            results.append(result)
        session.commit()

        # Calculate success/failure counts for better feedback
        success_count = sum(1 for r in results if r['success'])
        failure_count = len(results) - success_count

        # Overall success if at least one agent succeeded
        overall_success = success_count > 0

        # Log audit event for broadcast command
        group_text = 'all agents'
        if group_id is not None and group_id != 'all':
            if group_id == 'none':
                group_text = 'agents without group'
            else:
                group_text = f'agents in group {group_id}'
        log_audit(
            action='Broadcast Command',
            details=f"Executed command '{command}' on {group_text} - {success_count}/{len(results)} succeeded"
        )

        return jsonify({
            'success': overall_success,
            'command': command,
            'success_count': success_count,
            'failure_count': failure_count,
            'total_count': len(results),
            'results': results
        })
    except Exception as e:
        session.rollback()
        logger.error(f'Error in broadcast command: {str(e)}')
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500
    finally:
        session.close()


@app.route('/api/history', methods=['GET'])
def get_history():
    """Get command execution history"""
    session = db.get_session()
    try:
        # Get pagination parameters
        limit = request.args.get('limit', 100, type=int)
        offset = request.args.get('offset', 0, type=int)

        # Get total count
        total_count = session.query(CommandHistory).count()

        # Query history with pagination
        history_records = session.query(CommandHistory).order_by(
            CommandHistory.executed_at.desc()
        ).limit(limit).offset(offset).all()

        history_list = [record.to_dict() for record in history_records]

        return jsonify({
            'success': True,
            'history': history_list,
            'count': len(history_list),
            'total': total_count
        })
    except Exception as e:
        logger.error(f'Error fetching history: {str(e)}')
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500
    finally:
        session.close()


@app.route('/api/history', methods=['DELETE'])
def clear_history():
    """Clear all command execution history"""
    session = db.get_session()
    try:
        # Delete all history records
        deleted_count = session.query(CommandHistory).delete()
        session.commit()

        logger.info(f'Cleared {deleted_count} history records')

        return jsonify({
            'success': True,
            'message': f'Cleared {deleted_count} history records'
        })
    except Exception as e:
        session.rollback()
        logger.error(f'Error clearing history: {str(e)}')
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500
    finally:
        session.close()


@app.route('/api/history/autocomplete', methods=['GET'])
def get_autocomplete_suggestions():
    """Get autocomplete suggestions from command history"""
    session = db.get_session()
    try:
        # Get the search prefix from query parameter
        prefix = request.args.get('q', '').strip()
        limit = request.args.get('limit', 10, type=int)

        # Build subquery to get the most recent execution time for each command
        from sqlalchemy import func
        subquery = session.query(
            CommandHistory.command,
            func.max(CommandHistory.executed_at).label('latest_execution')
        )

        if prefix:
            # Case-insensitive search for commands starting with prefix
            subquery = subquery.filter(CommandHistory.command.ilike(f'{prefix}%'))

        # Group by command and order by most recent usage
        subquery = subquery.group_by(CommandHistory.command).order_by(
            func.max(CommandHistory.executed_at).desc()
        ).limit(limit)

        suggestions = subquery.all()

        # Extract command strings from tuples
        command_list = [cmd[0] for cmd in suggestions]

        return jsonify({
            'success': True,
            'suggestions': command_list,
            'count': len(command_list)
        })
    except Exception as e:
        logger.error(f'Error fetching autocomplete suggestions: {str(e)}')
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500
    finally:
        session.close()


@app.route('/api/commands')
def get_commands():
    """Get list of available dnsdist commands from distcommands.txt"""
    try:
        commands_file = os.path.join(os.path.dirname(__file__), 'distcommands.txt')

        if not os.path.exists(commands_file):
            return jsonify({
                'success': False,
                'error': 'Commands file not found'
            }), 404

        with open(commands_file, 'r') as f:
            commands = [line.strip() for line in f.readlines() if line.strip()]

        return jsonify({
            'success': True,
            'commands': commands
        })

    except Exception as e:
        logger.error(f'Error reading commands file: {str(e)}')
        return jsonify({
            'success': False,
            'error': f'Failed to read commands: {str(e)}'
        }), 500


@app.route('/api/groups', methods=['GET'])
def get_groups():
    """Get all groups"""
    session = db.get_session()
    try:
        # Eager load agents relationship to avoid N+1 queries
        groups = session.query(Group).options(joinedload(Group.agents)).all()
        return jsonify({
            'success': True,
            'groups': [group.to_dict() for group in groups]
        })
    except Exception as e:
        logger.error(f'Error fetching groups: {str(e)}')
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500
    finally:
        session.close()


@app.route('/api/groups', methods=['POST'])
def create_group():
    """Create a new group"""
    data = request.get_json()

    if not data:
        return jsonify({'success': False, 'error': 'No data provided'}), 400

    if 'name' not in data:
        return jsonify({'success': False, 'error': 'Missing required field: name'}), 400

    session = db.get_session()
    try:
        # Check if group with same name already exists
        existing = session.query(Group).filter_by(name=data['name']).first()
        if existing:
            return jsonify({'success': False, 'error': 'Group with this name already exists'}), 400

        # Create new group
        group = Group(
            name=data['name'],
            description=data.get('description', '')
        )

        session.add(group)
        session.commit()
        return jsonify({'success': True, 'group': group.to_dict()}), 201
    except Exception as e:
        session.rollback()
        logger.error(f'Error creating group: {str(e)}')
        return jsonify({'success': False, 'error': str(e)}), 500
    finally:
        session.close()


@app.route('/api/groups/<int:group_id>', methods=['PUT'])
def update_group(group_id):
    """Update an existing group"""
    data = request.get_json()

    if not data:
        return jsonify({'success': False, 'error': 'No data provided'}), 400

    session = db.get_session()
    try:
        group = session.query(Group).filter_by(id=group_id).first()
        if not group:
            return jsonify({'success': False, 'error': 'Group not found'}), 404

        # Update fields if provided
        if 'name' in data:
            # Check if another group with the same name exists
            existing = session.query(Group).filter(
                Group.name == data['name'],
                Group.id != group_id
            ).first()
            if existing:
                return jsonify({'success': False, 'error': 'Group with this name already exists'}), 400
            group.name = data['name']

        if 'description' in data:
            group.description = data['description']
        session.commit()
        return jsonify({'success': True, 'group': group.to_dict()})
    except Exception as e:
        session.rollback()
        logger.error(f'Error updating group: {str(e)}')
        return jsonify({'success': False, 'error': str(e)}), 500
    finally:
        session.close()


@app.route('/api/groups/<int:group_id>', methods=['DELETE'])
def delete_group(group_id):
    """Delete a group"""
    session = db.get_session()
    try:
        group = session.query(Group).filter_by(id=group_id).first()
        if not group:
            return jsonify({'success': False, 'error': 'Group not found'}), 404

        # Check if any agents are still in this group
        agents_count = session.query(Agent).filter_by(group_id=group_id).count()
        if agents_count > 0:
            return jsonify({
                'success': False,
                'error': f'Cannot delete group: {agents_count} agent(s) still assigned to this group'
            }), 400

        session.delete(group)
        session.commit()

        return jsonify({'success': True})
    except Exception as e:
        session.rollback()
        logger.error(f'Error deleting group: {str(e)}')
        return jsonify({'success': False, 'error': str(e)}), 500
    finally:
        session.close()


@app.route('/api/dynblock-rules/<path:rule_uuid>', methods=['GET'])
def get_all_dynblock_id(rule_uuid: str):
    """
    Get all rules from database
    """
    session = db.get_session()
    try:
        # Получаем конкретное правило по uuid
        rules = session.query(DynBlockRule).options(joinedload(DynBlockRule.group)).filter(DynBlockRule.rule_uuid == rule_uuid).all()
        # print(rule.rule_uuid)
        if not rules:
            session.close()
            return jsonify({
                'success': False,
                'rules': []
            })
        return jsonify({
            'success': True,
            'rules':  [rule.to_dict() for rule in rules]
        })
    finally:
        session.close()


@app.route('/api/dynblock-rules', methods=['GET'])
def get_dynblock_rules():
    """Get all DynBlock rules"""
    session = db.get_session()
    try:
        # Eager load group relationship to avoid N+1 queries
        # Sort by creation_order (ascending) as the default and only sort order
        rules = session.query(DynBlockRule).options(joinedload(DynBlockRule.group)).order_by(DynBlockRule.creation_order.asc()).all()
        return jsonify({
            'success': True,
            'rules': [rule.to_dict() for rule in rules]
        })
    except Exception as e:
        logger.error(f'Error fetching DynBlock rules: {str(e)}')
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500
    finally:
        session.close()


@app.route('/api/dynblock-rules', methods=['POST'])
def create_dynblock_rule():
    """Create a new DynBlock rule"""
    session = db.get_session()
    try:
        data = request.get_json()
        if not data:
            return jsonify({
                'success': False,
                'error': 'Missing rule_command field'
            }), 400

        get_uuid = extract_uuid_from_adddynblocks(data.get('rule_command'))

        logger.info(f'get uuid in  DynBlock rule: {get_uuid} start creating')
        if get_uuid == "Error":
            logger.info(f'No uuid found in command: {get_uuid} error')
            return jsonify({
                'success': False,
                'error': "No uuid found in command (every rule should have unique uuid)"
            }), 500

        # Handle group_id - convert empty string or 'all' to None
        group_id = data.get('group_id')
        if group_id in ('', 'all', None):
            group_id = None
        else:
            group_id = int(group_id)

        # Auto-generate creation_order by finding the max value and incrementing
        max_order = session.query(sa.func.max(DynBlockRule.creation_order)).scalar()
        creation_order = (max_order or 0) + 1

        rule = DynBlockRule(
            name=data.get('name') or None,
            rule_command=data['rule_command'],
            description=data.get('description') or None,
            group_id=group_id,
            creation_order=creation_order,
            rule_uuid=get_uuid
        )

        session.add(rule)
        session.commit()

        # Re-query rule with group relationship eagerly loaded to avoid lazy loading
        rule = session.query(DynBlockRule).options(joinedload(DynBlockRule.group)).filter_by(id=rule.id).first()

        logger.info(f'Created DynBlock rule: {rule.rule_command}')

        # Log audit event
        log_audit(
            action='Add DynBlock Rule',
            details=f"Added rule '{rule.name or rule.rule_command[:50]}'"
        )
        return jsonify({
            'success': True,
            'rule': rule.to_dict()
        })

    except Exception as e:
        session.rollback()
        logger.error(f'Error creating DynBlock rule: {str(e)}')
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500
    finally:
        session.close()


@app.route('/api/dynblock-rules/<int:rule_id>', methods=['DELETE'])
def delete_dynblock_rule(rule_id):
    """Delete a DynBlock rule"""
    session = db.get_session()
    try:
        rule = session.query(DynBlockRule).filter_by(id=rule_id).first()
        if not rule:
            return jsonify({
                'success': False,
                'error': 'Rule not found'
            }), 404

        rule_name = rule.name or f"Rule {rule_id}"
        session.delete(rule)
        session.commit()

        logger.info(f'Deleted DynBlock rule: {rule_id}')

        log_audit(
            action='Delete DynBlock Rule',
            details=f"Deleted rule '{rule_name}'"
        )

        return jsonify({
            'success': True,
            'message': 'Rule deleted successfully'
        })

    except Exception as e:
        session.rollback()
        logger.error(f'Error deleting DynBlock rule: {str(e)}')
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500
    finally:
        session.close()


@app.route('/api/dynblock-rules/<int:rule_id>', methods=['PATCH'])
def update_dynblock_rule(rule_id):
    """Update a DynBlock rule (e.g., toggle is_active, edit name, description, rule_command, group_id)"""
    session = db.get_session()
    try:
        # Query with eager loading to avoid N+1 queries
        rule = session.query(DynBlockRule).options(joinedload(DynBlockRule.group)).filter_by(id=rule_id).first()
        if not rule:
            return jsonify({
                'success': False,
                'error': 'Rule not found'
            }), 404

        data = request.get_json()

        changes = []
        old_is_active = rule.is_active

        # Update is_active if provided
        if 'is_active' in data:
            rule.is_active = bool(data['is_active'])
            if old_is_active != rule.is_active:
                changes.append('enabled' if rule.is_active else 'disabled')

        # Update name if provided
        if 'name' in data:
            rule.name = data['name'] or None
            changes.append('name')

        # Update rule_command if provided
        if 'rule_command' in data:
            if not data['rule_command']:
                return jsonify({
                    'success': False,
                    'error': 'rule_command cannot be empty'
                }), 400
            rule.rule_command = data['rule_command']
            changes.append('rule_command')

        # Update description if provided
        if 'description' in data:
            rule.description = data['description'] or None
            changes.append('description')

        # Update group_id if provided
        if 'group_id' in data:
            group_id = data['group_id']
            if group_id in ('', 'all', None):
                rule.group_id = None
            else:
                rule.group_id = int(group_id)
            changes.append('group')

        session.commit()
        session.refresh(rule)

        logger.info(f'Updated DynBlock rule {rule_id}')

        # Log audit events consistently with agent updates
        rule_name = rule.name or f"Rule {rule_id}"
        status_changed = 'is_active' in data and old_is_active != rule.is_active

        # Log status change if it occurred
        if status_changed:
            log_audit(
                action='Enable DynBlock Rule' if rule.is_active else 'Disable DynBlock Rule',
                details=f"Rule '{rule_name}' was {'enabled' if rule.is_active else 'disabled'}"
            )

        if not status_changed or len(data) > 1:
            if changes:  # Only log if something actually changed
                log_audit(
                    action='Edit DynBlock Rule',
                    details=f"Updated rule '{rule_name}' - changed: {', '.join(changes)}"
                )

        return jsonify({
            'success': True,
            'rule': rule.to_dict()
        })

    except Exception as e:
        session.rollback()
        logger.error(f'Error updating DynBlock rule: {str(e)}')
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500
    finally:
        session.close()


@app.route('/api/rule-command-templates', methods=['GET'])
def get_rule_command_templates():
    """Get all active rule command templates"""
    session = db.get_session()
    try:
        templates = session.query(RuleCommandTemplate).all()
        logger.debug(f'Get agents rules {[template.to_dict() for template in templates]}')
        return jsonify({
            'success': True,
            'templates': [template.to_dict() for template in templates]
        })
    except Exception as e:
        logger.error(f'Error fetching rule command templates: {str(e)}')
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500
    finally:
        session.close()


@app.route('/api/rule-command-templates', methods=['POST'])
def create_rule_command_template():
    """Create a new rule command template"""
    session = db.get_session()
    try:
        data = request.get_json()

        # Validate required fields
        if not data.get('name'):
            return jsonify({
                'success': False,
                'error': 'Template name is required'
            }), 400

        if not data.get('template'):
            return jsonify({
                'success': False,
                'error': 'Template content is required'
            }), 400

        # Create new template
        template = RuleCommandTemplate(
            name=data.get('name'),
            template=data.get('template'),
            description=data.get('description', ''),
            is_active=data.get('is_active', True)
        )

        session.add(template)
        session.commit()
        session.refresh(template)

        logger.info(f'Created template: {template.name}')
        return jsonify({
            'success': True,
            'template': template.to_dict()
        })
    except Exception as e:
        session.rollback()
        logger.error(f'Error creating template: {str(e)}')
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500
    finally:
        session.close()


@app.route('/api/rule-command-templates/<int:template_id>', methods=['PATCH'])
def update_rule_command_template(template_id):
    """Update an existing rule command template"""
    session = db.get_session()
    try:
        template = session.query(RuleCommandTemplate).filter_by(id=template_id).first()

        if not template:
            return jsonify({
                'success': False,
                'error': 'Template not found'
            }), 404

        data = request.get_json()

        # Update fields if provided and validate non-empty values
        if 'name' in data:
            if not data['name'] or not data['name'].strip():
                return jsonify({
                    'success': False,
                    'error': 'Template name cannot be empty'
                }), 400
            template.name = data['name']
        if 'template' in data:
            if not data['template'] or not data['template'].strip():
                return jsonify({
                    'success': False,
                    'error': 'Template content cannot be empty'
                }), 400
            template.template = data['template']
        if 'description' in data:
            template.description = data['description']
        if 'is_active' in data:
            template.is_active = data['is_active']

        session.commit()
        session.refresh(template)

        logger.info(f'Updated template: {template.name}')
        return jsonify({
            'success': True,
            'template': template.to_dict()
        })
    except Exception as e:
        session.rollback()
        logger.error(f'Error updating template: {str(e)}')
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500
    finally:
        session.close()


@app.route('/api/rule-command-templates/<int:template_id>', methods=['DELETE'])
def delete_rule_command_template(template_id):
    """Delete a rule command template"""
    session = db.get_session()
    try:
        template = session.query(RuleCommandTemplate).filter_by(id=template_id).first()

        if not template:
            return jsonify({
                'success': False,
                'error': 'Template not found'
            }), 404

        template_name = template.name
        session.delete(template)
        session.commit()

        logger.info(f'Deleted template: {template_name}')
        return jsonify({
            'success': True,
            'message': f'Template "{template_name}" deleted successfully'
        })
    except Exception as e:
        session.rollback()
        logger.error(f'Error deleting template: {str(e)}')
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500
    finally:
        session.close()


@app.route('/api/audit', methods=['GET'])
def get_audit_logs():
    """Get audit logs with pagination"""
    session = db.get_session()
    try:
        # Get pagination parameters
        page = request.args.get('page', 1, type=int)
        per_page = request.args.get('per_page', 50, type=int)

        # Ensure valid pagination parameters
        if page < 1:
            page = 1
        if per_page < 1 or per_page > 100:
            per_page = 50

        # Query audit logs ordered by most recent first
        query = session.query(AuditLog).order_by(AuditLog.created_at.desc())

        # Get total count
        total_count = query.count()

        # Calculate pagination
        offset = (page - 1) * per_page
        total_pages = (total_count + per_page - 1) // per_page if total_count > 0 else 0

        # Get paginated results
        audit_logs = query.limit(per_page).offset(offset).all()

        return jsonify({
            'success': True,
            'audit_logs': [log.to_dict() for log in audit_logs],
            'pagination': {
                'page': page,
                'per_page': per_page,
                'total_count': total_count,
                'total_pages': total_pages,
                'has_next': page < total_pages,
                'has_prev': page > 1
            }
        })
    except Exception as e:
        logger.error(f'Error fetching audit logs: {str(e)}')
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500
    finally:
        session.close()


@app.route('/api/audit/cleanup', methods=['DELETE'])
def cleanup_old_audit_logs():
    """Delete audit logs older than 3 days"""
    session = db.get_session()
    try:
        from datetime import timedelta

        # Calculate the cutoff date (3 days ago)
        cutoff_date = utc_now() - timedelta(days=3)

        # Delete old audit logs
        deleted_count = session.query(AuditLog).filter(
            AuditLog.created_at < cutoff_date
        ).delete()

        session.commit()

        # Log this action using the existing log_audit function
        log_audit('CLEANUP_AUDIT_LOGS', f'Deleted {deleted_count} audit logs older than 3 days')

        return jsonify({
            'success': True,
            'deleted_count': deleted_count,
            'message': f'Successfully deleted {deleted_count} audit logs older than 3 days'
        })
    except Exception as e:
        session.rollback()
        logger.error(f'Error cleaning up audit logs: {str(e)}')
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500
    finally:
        session.close()


def main():
    # Database and Victoria Metrics are already initialized in create_app()
    logger.info(f'Starting Dnsdist Web Console on {settings.CONSOLE_HOST}:{settings.CONSOLE_PORT}')
    logger.info(f'Using database: {settings.DATABASE_URL}')

    app.run(host=settings.CONSOLE_HOST, port=settings.CONSOLE_PORT, debug=settings.DEBUG)


if __name__ == '__main__':
    main()

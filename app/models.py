#!/usr/bin/env python3
"""
Database models for dnsdist Web API
"""

from datetime import datetime, timezone

from model_utils import (ComparableMixin, DateTimeSerializableMixin,
                         ValidationMixin)
from settings import settings
from sqlalchemy import (Boolean, Column, DateTime, ForeignKey, Integer, String,
                        Text, create_engine)
from sqlalchemy.orm import declarative_base, relationship, sessionmaker
from werkzeug.security import check_password_hash, generate_password_hash

Base = declarative_base()


def utc_now():
    """Helper function to get current UTC time"""
    return datetime.now(timezone.utc)


class Group(Base, DateTimeSerializableMixin):
    """Model for agent groups"""
    __tablename__ = 'groups'

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(255), nullable=False, unique=True)
    description = Column(Text, nullable=True)
    created_at = Column(DateTime, default=utc_now, nullable=False)
    updated_at = Column(DateTime, default=utc_now, onupdate=utc_now, nullable=False)

    # Relationship to agents
    agents = relationship('Agent', back_populates='group')

    def to_dict(self):
        """Convert group to dictionary"""
        return {
            'id': self.id,
            'name': self.name,
            'description': self.description,
            'created_at': self._serialize_datetime(self.created_at),
            'updated_at': self._serialize_datetime(self.updated_at),
            'agent_count': len(self.agents) if self.agents else 0
        }


class Agent(Base, DateTimeSerializableMixin):
    """Model for dnsdist agents"""
    __tablename__ = 'agents'

    id = Column(Integer, primary_key=True, autoincrement=True)
    agent_name = Column(String(255), nullable=False, unique=True)
    agent_ip = Column(String(255), nullable=False)
    agent_port = Column(Integer, nullable=False)
    agent_token = Column(String(255), nullable=False)
    group_id = Column(Integer, ForeignKey('groups.id'), nullable=True)
    created_at = Column(DateTime, default=utc_now, nullable=False)
    updated_at = Column(DateTime, default=utc_now, onupdate=utc_now, nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)
    status = Column(String(255), default="0", nullable=False)
    version = Column(String(255), default="0", nullable=False)
    service_time = Column(String(255), default="0", nullable=False)

    # Relationship to group
    group = relationship('Group', back_populates='agents')

    def to_dict(self):
        """Convert agent to dictionary"""
        return {
            'id': self.id,
            'agent_name': self.agent_name,
            'agent_ip': self.agent_ip,
            'agent_port': self.agent_port,
            'agent_token': self.agent_token,
            'group_id': self.group_id,
            'group_name': self.group.name if self.group else None,
            'created_at': self._serialize_datetime(self.created_at),
            'updated_at': self._serialize_datetime(self.updated_at),
            'is_active': self.is_active,
            'status': self.status,
            'version': self.version,
            'service_time':  self.service_time
        }

    def get_url(self):
        """Get the full URL for the agent"""
        protocol = 'https' if self.agent_port == 443 else 'http'
        return f'{protocol}://{self.agent_ip}:{self.agent_port}'


class CommandHistory(Base, DateTimeSerializableMixin):
    """Model for command execution history"""
    __tablename__ = 'command_history'

    id = Column(Integer, primary_key=True, autoincrement=True)
    agent_name = Column(String(255), nullable=False)
    command = Column(Text, nullable=False)
    success = Column(Boolean, nullable=False)
    result = Column(Text, nullable=True)
    error = Column(Text, nullable=True)
    executed_at = Column(DateTime, default=utc_now, nullable=False)

    def to_dict(self):
        """Convert history to dictionary"""
        return {
            'id': self.id,
            'agent_name': self.agent_name,
            'command': self.command,
            'success': self.success,
            'result': self.result,
            'error': self.error,
            'executed_at': self._serialize_datetime(self.executed_at)
        }


class Rule(Base, ValidationMixin, DateTimeSerializableMixin, ComparableMixin):
    """Model for dnsdist rules"""
    __tablename__ = 'rules'

    # Fields that can change and should be compared/updated.
    # Natural key fields (agent_name, rule_id) are excluded as they identify the rule and should not change.
    # Auto-managed fields (id, updated_at) are also excluded.
    COMPARABLE_FIELDS = ['name', 'matches', 'rule', 'action', 'uuid', 'creation_order']

    id = Column(Integer, primary_key=True, autoincrement=True)
    agent_name = Column(String(255), nullable=False)
    rule_id = Column(Integer, nullable=False)
    name = Column(String(255), nullable=True)
    matches = Column(Integer, nullable=False)
    rule = Column(Text, nullable=False)
    action = Column(Text, nullable=False)
    uuid = Column(String(255), nullable=True)
    creation_order = Column(Integer, nullable=True)
    updated_at = Column(DateTime, default=utc_now, onupdate=utc_now, nullable=False)

    def to_dict(self):
        """Convert rule to dictionary"""
        return {
            'id': self.id,
            'agent_name': self.agent_name,
            'rule_id': self.rule_id,
            'name': self.name,
            'matches': self.matches,
            'rule': self.rule,
            'action': self.action,
            'uuid': self.uuid,
            'creation_order': self.creation_order,
            'updated_at': self._serialize_datetime(self.updated_at)
        }

    def validate_rule_id(self):
        """
        Validate rule_id field

        Returns:
            tuple: (is_valid, error_message)
        """
        return self._validate_positive_integer(self.rule_id, 'rule_id')

    def validate_uuid(self):
        """
        Validate rule_id field

        Returns:
            tuple: (is_valid, error_message)
        """
        return self._validate_uuid(self.uuid, 'uuid')

    def validate_matches(self):
        """
        Validate matches field

        Returns:
            tuple: (is_valid, error_message)
        """
        return self._validate_positive_integer(self.matches, 'matches')

    def validate_agent_name(self):
        """
        Validate agent_name field

        Returns:
            tuple: (is_valid, error_message)
        """
        return self._validate_string_field_required(self.agent_name, 'agent_name')

    def validate_rule_text(self):
        """
        Validate rule field

        Returns:
            tuple: (is_valid, error_message)
        """
        if self.rule is None:
            return False, "rule cannot be None"
        if not isinstance(self.rule, str):
            return False, "rule must be a string"
        return True, None

    def validate_action(self):
        """
        Validate action field

        Returns:
            tuple: (is_valid, error_message)
        """
        if self.action is None:
            return False, "action cannot be None"
        if not isinstance(self.action, str):
            return False, "action must be a string"
        return True, None

    def validate_name(self):
        """
        Validate name field (optional field)

        Returns:
            tuple: (is_valid, error_message)
        """
        return self._validate_string_field_optional(self.name, 'name')

    def validate(self):
        """
        Validate all fields of the Rule instance

        Returns:
            tuple: (is_valid, list_of_error_messages)
        """
        errors = []

        validators = [
            self.validate_agent_name,
            self.validate_rule_id,
            self.validate_matches,
            self.validate_rule_text,
            self.validate_action,
            self.validate_name,
            self.validate_uuid
        ]

        for validator in validators:
            is_valid, error_msg = validator()
            if not is_valid:
                errors.append(error_msg)

        return len(errors) == 0, errors

    def __repr__(self):
        return f"<Rule(id={self.id}, agent='{self.agent_name}', uuid='{self.uuid}', type='{self.rule_id}',name='{self.name}')>"


class DynBlockRule(Base, DateTimeSerializableMixin):
    """Model for custom DynBlock rules created by users"""
    __tablename__ = 'dynblock_rules'

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(255), nullable=True)
    rule_command = Column(Text, nullable=False)
    description = Column(String(255), nullable=True)
    group_id = Column(Integer, ForeignKey('groups.id'), nullable=True)
    creation_order = Column(Integer, nullable=True)
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime, default=utc_now, nullable=False)
    updated_at = Column(DateTime, default=utc_now, onupdate=utc_now, nullable=False)
    rule_uuid = Column(Text, nullable=False)

    # Relationship to group
    group = relationship('Group', foreign_keys=[group_id])

    def to_dict(self):
        """Convert dynblock rule to dictionary"""
        return {
            'id': self.id,
            'name': self.name,
            'rule_command': self.rule_command,
            'description': self.description,
            'group_id': self.group_id,
            'group_name': self.group.name if self.group else None,
            'creation_order': self.creation_order,
            'is_active': self.is_active,
            'created_at': self._serialize_datetime(self.created_at),
            'updated_at': self._serialize_datetime(self.updated_at),
            'rule_uuid': self.rule_uuid
        }


class DynBlockRuleSyncStatus(Base, DateTimeSerializableMixin):
    """Model for tracking which DynBlock rules are synced to which agents"""
    __tablename__ = 'dynblock_rule_sync_status'

    id = Column(Integer, primary_key=True, autoincrement=True)
    dynblock_rule_id = Column(Integer, nullable=False)
    agent_name = Column(String(255), nullable=False)
    last_synced_at = Column(DateTime, nullable=False)
    sync_success = Column(Boolean, nullable=False)
    error_message = Column(Text, nullable=True)

    def to_dict(self):
        """Convert sync status to dictionary"""
        return {
            'id': self.id,
            'dynblock_rule_id': self.dynblock_rule_id,
            'agent_name': self.agent_name,
            'last_synced_at': self._serialize_datetime(self.last_synced_at),
            'sync_success': self.sync_success,
            'error_message': self.error_message
        }


class RuleCommandTemplate(Base, DateTimeSerializableMixin):
    """Model for rule command templates with Jinja2 placeholders"""
    __tablename__ = 'rule_command_templates'

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(255), nullable=False)
    template = Column(Text, nullable=False)
    description = Column(String(255), nullable=True)
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime, default=utc_now, nullable=False)
    updated_at = Column(DateTime, default=utc_now, onupdate=utc_now, nullable=False)

    def to_dict(self):
        """Convert template to dictionary"""
        return {
            'id': self.id,
            'name': self.name,
            'template': self.template,
            'description': self.description,
            'is_active': self.is_active,
            'created_at': self._serialize_datetime(self.created_at),
            'updated_at': self._serialize_datetime(self.updated_at)
        }


class DownstreamServer(Base, ValidationMixin, DateTimeSerializableMixin, ComparableMixin):
    """Model for dnsdist downstream servers (also known as Servers)"""
    __tablename__ = 'downstream_servers'

    # Fields that can change and should be compared/updated.
    # Natural key fields (agent_name, server_id) are excluded as they identify the server and should not change.
    # Auto-managed fields (id, updated_at) are also excluded.
    COMPARABLE_FIELDS = [
        'name', 'address', 'state', 'qps', 'qlim', 'ord', 'wt',
        'queries', 'drops', 'drate', 'lat', 'tcp', 'outstanding', 'pools'
    ]

    id = Column(Integer, primary_key=True, autoincrement=True)
    agent_name = Column(String(255), nullable=False)
    server_id = Column(Integer, nullable=False)
    name = Column(String(255), nullable=True)
    address = Column(String(255), nullable=False)
    state = Column(String(50), nullable=False)
    qps = Column(String(50), nullable=True)
    qlim = Column(String(50), nullable=True)
    ord = Column(String(50), nullable=True)
    wt = Column(String(50), nullable=True)
    queries = Column(String(50), nullable=True)
    drops = Column(String(50), nullable=True)
    drate = Column(String(50), nullable=True)
    lat = Column(String(50), nullable=True)
    tcp = Column(String(50), nullable=True)
    outstanding = Column(String(50), nullable=True)
    pools = Column(Text, nullable=True)
    updated_at = Column(DateTime, default=utc_now, onupdate=utc_now, nullable=False)

    def to_dict(self):
        """Convert downstream server to dictionary"""
        return {
            'id': self.id,
            'agent_name': self.agent_name,
            'server_id': self.server_id,
            'name': self.name,
            'address': self.address,
            'state': self.state,
            'qps': self.qps,
            'qlim': self.qlim,
            'ord': self.ord,
            'wt': self.wt,
            'queries': self.queries,
            'drops': self.drops,
            'drate': self.drate,
            'lat': self.lat,
            'tcp': self.tcp,
            'outstanding': self.outstanding,
            'pools': self.pools,
            'updated_at': self._serialize_datetime(self.updated_at)
        }

    def validate_server_id(self):
        """
        Validate server_id field

        Returns:
            tuple: (is_valid, error_message)
        """
        return self._validate_positive_integer(self.server_id, 'server_id')

    def validate_agent_name(self):
        """
        Validate agent_name field

        Returns:
            tuple: (is_valid, error_message)
        """
        return self._validate_string_field_required(self.agent_name, 'agent_name')

    def validate_name(self):
        """
        Validate name field (optional field)

        Returns:
            tuple: (is_valid, error_message)
        """
        return self._validate_string_field_optional(self.name, 'name')

    def validate_address(self):
        """
        Validate address field

        Returns:
            tuple: (is_valid, error_message)
        """
        if self.address is None:
            return False, "address cannot be None"
        if not isinstance(self.address, str):
            return False, "address must be a string"
        if not self.address:
            return False, "address cannot be empty"
        if len(self.address) > 255:
            return False, "address cannot exceed 255 characters"
        return True, None

    def validate_state(self):
        """
        Validate state field

        Returns:
            tuple: (is_valid, error_message)
        """
        if self.state is None:
            return False, "state cannot be None"
        if not isinstance(self.state, str):
            return False, "state must be a string"
        if not self.state:
            return False, "state cannot be empty"
        if len(self.state) > 50:
            return False, "state cannot exceed 50 characters"
        return True, None

    def validate_string_field(self, field_name, max_length=50):
        """
        Generic validation for optional string fields

        Args:
            field_name: Name of the field to validate
            max_length: Maximum allowed length

        Returns:
            tuple: (is_valid, error_message)
        """
        return self._validate_string_field_optional(getattr(self, field_name, None), field_name, max_length)

    def validate(self):
        """
        Validate all fields of the DownstreamServer instance

        Returns:
            tuple: (is_valid, list_of_error_messages)
        """
        errors = []

        # Validate required fields
        validators = [
            self.validate_agent_name,
            self.validate_server_id,
            self.validate_name,
            self.validate_address,
            self.validate_state
        ]

        for validator in validators:
            is_valid, error_msg = validator()
            if not is_valid:
                errors.append(error_msg)

        # Validate optional string fields
        optional_fields = ['qps', 'qlim', 'ord', 'wt', 'queries', 'drops', 'drate', 'lat', 'tcp', 'outstanding']
        for field in optional_fields:
            is_valid, error_msg = self.validate_string_field(field)
            if not is_valid:
                errors.append(error_msg)

        # Validate pools field (can be longer Text field)
        is_valid, error_msg = self.validate_string_field('pools', max_length=65535)
        if not is_valid:
            errors.append(error_msg)

        return len(errors) == 0, errors

    def __repr__(self):
        return f"<DownstreamServer(id={self.id}, agent='{self.agent_name}', server_id={self.server_id}, name='{self.name}', address='{self.address}')>"


class AgentDynBlock(Base, DateTimeSerializableMixin):
    """Model for dnsdist dynamic blocks"""
    __tablename__ = 'agents_dyn_blocks'

    id = Column(Integer, primary_key=True, autoincrement=True)
    agent_name = Column(String(255), nullable=False)
    what = Column(String(255), nullable=False)
    seconds = Column(Integer, nullable=True)
    blocks = Column(Integer, nullable=True)
    warning = Column(String(50), nullable=True)
    action = Column(String(255), nullable=True)
    ebpf = Column(String(50), nullable=True)
    reason = Column(Text, nullable=True)
    updated_at = Column(DateTime, default=utc_now, onupdate=utc_now, nullable=False)

    def to_dict(self):
        """Convert dynamic block to dictionary"""
        return {
            'id': self.id,
            'agent_name': self.agent_name,
            'what': self.what,
            'seconds': self.seconds,
            'blocks': self.blocks,
            'warning': self.warning,
            'action': self.action,
            'ebpf': self.ebpf,
            'reason': self.reason,
            'updated_at': self._serialize_datetime(self.updated_at)
        }


class TopClient(Base, DateTimeSerializableMixin):
    """Model for dnsdist top clients"""
    __tablename__ = 'topclients'

    id = Column(Integer, primary_key=True, autoincrement=True)
    agent_name = Column(String(255), nullable=False)
    rank = Column(Integer, nullable=False)
    client = Column(String(255), nullable=False)
    queries = Column(Integer, nullable=False)
    percentage = Column(String(50), nullable=False)
    updated_at = Column(DateTime, default=utc_now, onupdate=utc_now, nullable=False)

    def to_dict(self):
        """Convert top client to dictionary"""
        return {
            'id': self.id,
            'agent_name': self.agent_name,
            'rank': self.rank,
            'client': self.client,
            'queries': self.queries,
            'percentage': self.percentage,
            'updated_at': self._serialize_datetime(self.updated_at)
        }


class TopQuery(Base, DateTimeSerializableMixin):
    """Model for dnsdist top queries"""
    __tablename__ = 'topqueries'

    id = Column(Integer, primary_key=True, autoincrement=True)
    agent_name = Column(String(255), nullable=False)
    rank = Column(Integer, nullable=False)
    query = Column(String(255), nullable=False)
    count = Column(Integer, nullable=False)
    percentage = Column(String(50), nullable=False)
    updated_at = Column(DateTime, default=utc_now, onupdate=utc_now, nullable=False)

    def to_dict(self):
        """Convert top query to dictionary"""
        return {
            'id': self.id,
            'agent_name': self.agent_name,
            'rank': self.rank,
            'query': self.query,
            'count': self.count,
            'percentage': self.percentage,
            'updated_at': self._serialize_datetime(self.updated_at)
        }


class SyncStatus(Base, DateTimeSerializableMixin):
    """Model for tracking background sync status"""
    __tablename__ = 'sync_status'

    id = Column(Integer, primary_key=True, autoincrement=True)
    last_sync_time = Column(DateTime, nullable=True)
    status = Column(String(50), nullable=False, default='Never')
    synced_agents_count = Column(Integer, nullable=False, default=0)
    failed_agents_count = Column(Integer, nullable=False, default=0)
    error_message = Column(Text, nullable=True)

    def to_dict(self):
        """Convert sync status to dictionary"""
        return {
            'id': self.id,
            'last_sync_time': self._serialize_datetime(self.last_sync_time),
            'status': self.status,
            'synced_agents_count': self.synced_agents_count,
            'failed_agents_count': self.failed_agents_count,
            'error_message': self.error_message
        }


class User(Base, DateTimeSerializableMixin):
    """Model for web console users"""
    __tablename__ = 'users'

    id = Column(Integer, primary_key=True, autoincrement=True)
    username = Column(String(255), nullable=False, unique=True)
    password_hash = Column(String(255), nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime, default=utc_now, nullable=False)
    updated_at = Column(DateTime, default=utc_now, onupdate=utc_now, nullable=False)

    def set_password(self, password):
        """Hash and store the user password"""
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        """Verify a password against the stored hash"""
        return check_password_hash(self.password_hash, password)

    def to_dict(self):
        """Convert user to dictionary (without password hash)"""
        return {
            'id': self.id,
            'username': self.username,
            'is_active': self.is_active,
            'created_at': self._serialize_datetime(self.created_at),
            'updated_at': self._serialize_datetime(self.updated_at),
        }


class AuditLog(Base, DateTimeSerializableMixin):
    """Model for audit logging"""
    __tablename__ = 'audit_logs'

    id = Column(Integer, primary_key=True, autoincrement=True)
    ip_address = Column(String(255), nullable=False)
    action = Column(String(255), nullable=False)
    details = Column(Text, nullable=True)
    created_at = Column(DateTime, default=utc_now, nullable=False)

    def to_dict(self):
        """Convert audit log to dictionary"""
        return {
            'id': self.id,
            'ip_address': self.ip_address,
            'action': self.action,
            'details': self.details,
            'created_at': self._serialize_datetime(self.created_at)
        }


# Database configuration
class Database:
    """Database manager"""

    def __init__(self, db_url=None):
        """Initialize database with URL"""
        if db_url is None:
            db_url = settings.DATABASE_URL
        self.engine = create_engine(db_url, echo=False)
        self.SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=self.engine)

    def create_tables(self):
        """Create all tables and seed default data"""
        Base.metadata.create_all(bind=self.engine)
        self._seed_default_admin()

    def _seed_default_admin(self):
        """Create the default admin user if no users exist"""
        session = self.SessionLocal()
        try:
            if session.query(User).count() == 0:
                admin = User(username='admin', is_active=True)
                admin.set_password('admin')
                session.add(admin)
                session.commit()
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

    def get_session(self):
        """Get a new database session"""
        return self.SessionLocal()


# Alias for DownstreamServer to match problem statement naming
Servers = DownstreamServer

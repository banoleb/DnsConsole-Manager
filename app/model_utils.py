#!/usr/bin/env python3
import uuid

"""
Shared utilities for database models

This module provides common validation and serialization utilities
to reduce code duplication across model classes.
"""


class ValidationMixin:
    """Mixin class providing common validation methods for model fields"""

    @staticmethod
    def _validate_uuid(value, field_name):

        if not value:
            return False

        try:
            _ = uuid.UUID(value)
            return True
        except (ValueError, AttributeError, TypeError):
            return False, f"{field_name} must be an uuid"

    @staticmethod
    def _validate_positive_integer(value, field_name):
        """
        Validate that a field is a positive integer (>= 0)

        Args:
            value: The value to validate
            field_name: Name of the field (for error messages)

        Returns:
            tuple: (is_valid, error_message)
        """
        if value is None:
            return False, f"{field_name} cannot be None"
        if not isinstance(value, int):
            return False, f"{field_name} must be an integer"
        if value < 0:
            return False, f"{field_name} must be non-negative"
        return True, None

    @staticmethod
    def _validate_string_field_required(value, field_name, max_length=255):
        """
        Validate that a required string field meets all requirements

        Args:
            value: The value to validate
            field_name: Name of the field (for error messages)
            max_length: Maximum allowed length (default: 255)

        Returns:
            tuple: (is_valid, error_message)
        """
        if not isinstance(value, str):
            return False, f"{field_name} must be a string"
        if not value:
            return False, f"{field_name} cannot be empty"
        if len(value) > max_length:
            return False, f"{field_name} cannot exceed {max_length} characters"
        return True, None

    @staticmethod
    def _validate_string_field_optional(value, field_name, max_length=255):
        """
        Validate an optional string field

        Args:
            value: The value to validate (can be None)
            field_name: Name of the field (for error messages)
            max_length: Maximum allowed length (default: 255)

        Returns:
            tuple: (is_valid, error_message)
        """
        if value is not None:
            if not isinstance(value, str):
                return False, f"{field_name} must be a string or None"
            if len(value) > max_length:
                return False, f"{field_name} cannot exceed {max_length} characters"
        return True, None


class DateTimeSerializableMixin:
    """Mixin class providing DateTime serialization for to_dict methods"""

    @staticmethod
    def _serialize_datetime(dt):
        """
        Convert a datetime object to ISO format string

        Args:
            dt: datetime object or None

        Returns:
            str: ISO format datetime string, or None if dt is None
        """
        return dt.isoformat() if dt else None


class ComparableMixin:
    """
    Mixin class providing field comparison methods for models

    Classes using this mixin must define a COMPARABLE_FIELDS class attribute
    that lists the field names to compare. These should be fields that can change
    and need to be tracked for updates. Natural key fields (like agent_name, rule_id)
    and auto-managed fields (like id, updated_at) should be excluded.

    Example:
        class MyModel(Base, ComparableMixin):
            COMPARABLE_FIELDS = ['name', 'value', 'status']

            id = Column(Integer, primary_key=True)
            entity_id = Column(Integer, nullable=False)  # Natural key - excluded
            name = Column(String, nullable=True)
            value = Column(Integer, nullable=False)
            status = Column(String, nullable=False)
            updated_at = Column(DateTime)  # Auto-managed - excluded
    """

    # Must be overridden in subclass
    COMPARABLE_FIELDS = []

    def equals(self, other):
        """
        Compare this instance with another to check for equality
        Compares all fields listed in COMPARABLE_FIELDS

        Args:
            other: Another instance of the same class to compare with

        Returns:
            bool: True if instances are equal, False otherwise
        """
        if not isinstance(other, self.__class__):
            return False

        for field in self.COMPARABLE_FIELDS:
            if getattr(self, field) != getattr(other, field):
                return False
        return True

    def changed_fields(self, other):
        """
        Detect which fields have changed between this instance and another

        Args:
            other: Another instance of the same class to compare with

        Returns:
            dict: Dictionary with field names as keys and tuples of (self_value, other_value).
                  Empty dict if no changes detected.
        """
        if not isinstance(other, self.__class__):
            return {}

        changes = {}
        for field in self.COMPARABLE_FIELDS:
            self_value = getattr(self, field)
            other_value = getattr(other, field)
            if self_value != other_value:
                changes[field] = (self_value, other_value)

        return changes

    def needs_update(self, other):
        """
        Determine if this instance needs to be updated based on comparison with another

        Args:
            other: Another instance of the same class to compare with

        Returns:
            bool: True if update is needed, False otherwise
        """
        return bool(self.changed_fields(other))

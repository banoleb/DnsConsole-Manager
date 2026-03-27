#!/usr/bin/env python3
"""
 Metrics integration module

This module provides functionality to export topClients and topQueries metrics
to Metrics in Prometheus format.
"""

import logging

from settings import settings

logger = logging.getLogger('dns-metrics')


def escape_prometheus_label_value(value):
    """
    Escape a string value for use in Prometheus label values.

    Prometheus requires escaping of backslashes, newlines, and double quotes.

    Args:
        value: String value to escape

    Returns:
        Escaped string safe for use in Prometheus label values
    """
    if value is None:
        return ""

    # Convert to string if not already
    value = str(value)

    # Escape in the correct order: backslash first, then newline, then double quote
    value = value.replace('\\', '\\\\')  # Escape backslashes
    value = value.replace('\n', '\\n')   # Escape newlines
    value = value.replace('"', '\\"')    # Escape double quotes

    return value


class MetricsExporter:
    """Exporter for sending metrics to Metrics"""

    def __init__(self, enabled=None):
        self.enabled = enabled if enabled is not None else settings.METRICS_ENABLED

    def get_prometheus_metrics(self, topclients=None, topqueries=None, agents_status=None):
        """
        Generate Prometheus-formatted metrics as a string
        """
        metrics = []

        # Add topclients metrics
        if topclients:
            for item in topclients:
                safe_agent = escape_prometheus_label_value(item.agent_name)
                safe_client = escape_prometheus_label_value(item.client)

                count_value = item.queries
                metric_line = (
                    f'dnsdist_top_client_queries{{agent="{safe_agent}",'
                    f'client="{safe_client}"}} {count_value}'
                )
                metrics.append(metric_line)

                # Parse percentage (remove % sign and convert to float)
                try:
                    percentage_value = float(item.percentage.rstrip('%'))
                    percentage_metric = (
                        f'dnsdist_top_client_percentage{{agent="{safe_agent}",'
                        f'client="{safe_client}"}} {percentage_value}'
                    )
                    metrics.append(percentage_metric)
                except (ValueError, AttributeError) as e:
                    logger.debug(f'Failed to parse percentage for client {safe_client}: {item.percentage} - {e}')

        # Add topqueries metrics
        if topqueries:
            for item in topqueries:
                safe_agent = escape_prometheus_label_value(item.agent_name)
                safe_query = escape_prometheus_label_value(item.query)

                count_value = item.count
                metric_line = (
                    f'dnsdist_top_query_count{{agent="{safe_agent}",'
                    f'query="{safe_query}"}} {count_value}'
                )
                metrics.append(metric_line)

                # Parse percentage (remove % sign and convert to float)
                try:
                    percentage_value = float(item.percentage.rstrip('%'))
                    percentage_metric = (
                        f'dnsdist_top_query_percentage{{agent="{safe_agent}",'
                        f'query="{safe_query}"}} {percentage_value}'
                    )
                    metrics.append(percentage_metric)
                except (ValueError, AttributeError) as e:
                    logger.debug(f'Failed to parse percentage for query {safe_query}: {item.percentage} - {e}')

        # Add agent status metrics
        if agents_status:
            for agent_status in agents_status:
                agent_name = escape_prometheus_label_value(agent_status.get('agent_name', 'unknown'))
                status = agent_status.get('status', None)
                is_active = agent_status.get('is_active', True)
                group_name = agent_status.get('group_name', None)
                version = agent_status.get('version', None)
                # Escape group name for Prometheus label
                safe_group = escape_prometheus_label_value(group_name) if group_name else 'none'
                if is_active:
                    is_active = 1
                else:
                    is_active = 0
                metric_line = (
                    f'dnsdist_agent_status{{agent="{agent_name}",status="{status}",group="{safe_group},version="{version}"}} '
                    f'{is_active}'
                )
                metrics.append(metric_line)

        return '\n'.join(metrics)

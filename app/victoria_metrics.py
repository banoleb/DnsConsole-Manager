#!/usr/bin/env python3
"""
Victoria Metrics integration module

This module provides functionality to export topClients and topQueries metrics
to Victoria Metrics in Prometheus format.
"""

import logging

import requests
from settings import settings

logger = logging.getLogger('victoria-metrics')


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


class VictoriaMetricsExporter:
    """Exporter for sending metrics to Victoria Metrics"""

    def __init__(self, host=None, port=None, url_path=None, enabled=None):
        """
        Initialize Victoria Metrics exporter

        Args:
            host: Victoria Metrics host (default: from settings)
            port: Victoria Metrics port (default: from settings)
            url_path: Victoria Metrics URL path (default: from settings)
            enabled: Whether Victoria Metrics is enabled (default: from settings)
        """
        self.host = host or settings.VICTORIA_METRICS_HOST
        self.port = port or settings.VICTORIA_METRICS_PORT
        self.url_path = url_path or settings.VICTORIA_METRICS_URL
        self.enabled = enabled if enabled is not None else settings.VICTORIA_METRICS_ENABLED

        # Build the full URL
        self.base_url = f'http://{self.host}:{self.port}{self.url_path}'

        if self.enabled:
            logger.info(f'Victoria Metrics exporter initialized: {self.base_url}')
        else:
            logger.debug('Victoria Metrics exporter is disabled')

    def _send_metrics(self, metrics_text, metric_type='metrics'):
        """
        Send metrics to Victoria Metrics

        Args:
            metrics_text: Prometheus-formatted metrics text
            metric_type: Type of metrics for logging (default: 'metrics')

        Returns:
            bool: True if export was successful, False otherwise
        """
        try:
            response = requests.post(
                self.base_url,
                data=metrics_text,
                headers={'Content-Type': 'text/plain'},
                timeout=10
            )

            if response.status_code in [200, 204]:
                return True
            else:
                logger.error(
                    f'Failed to export {metric_type} to Victoria Metrics: '
                    f'HTTP {response.status_code} - {response.text}'
                )
                return False
        except Exception as e:
            logger.error(f'Error sending {metric_type} to Victoria Metrics: {str(e)}')
            return False

    def _export_ranked_metrics(self, items, metric_name_prefix, item_field_name, count_field_name):
        """
        Generic method to export ranked metrics (topClients or topQueries) to Victoria Metrics

        Args:
            items: List of model instances to export
            metric_name_prefix: Prefix for the metric name (e.g., 'dnsdist_top_client')
            item_field_name: Name of the field containing the item identifier (e.g., 'client' or 'query')
            count_field_name: Name of the field containing the count value (e.g., 'queries' or 'count')

        Returns:
            bool: True if export was successful, False otherwise
        """
        if not self.enabled:
            logger.debug(f'Victoria Metrics is disabled, skipping {metric_name_prefix} export')
            return False

        if not items:
            logger.debug(f'No {metric_name_prefix} to export')
            return True

        try:
            # Convert items to Prometheus format
            metrics = []
            for item in items:
                # Escape all label values for safety
                safe_agent = escape_prometheus_label_value(item.agent_name)
                safe_item = escape_prometheus_label_value(getattr(item, item_field_name))
                safe_rank = escape_prometheus_label_value(item.rank)

                # Create metric for count
                count_value = getattr(item, count_field_name)
                metric_line = (
                    f'{metric_name_prefix}_{count_field_name}{{agent="{safe_agent}",'
                    f'{item_field_name}="{safe_item}",rank="{safe_rank}"}} {count_value}'
                )
                metrics.append(metric_line)

                # Parse percentage (remove % sign and convert to float)
                try:
                    percentage_value = float(item.percentage.rstrip('%'))
                    percentage_metric = (
                        f'{metric_name_prefix}_percentage{{agent="{safe_agent}",'
                        f'{item_field_name}="{safe_item}",rank="{safe_rank}"}} {percentage_value}'
                    )
                    metrics.append(percentage_metric)
                except (ValueError, AttributeError):
                    logger.warning(f'Failed to parse percentage for {item_field_name} {safe_item}: {item.percentage}')

            # Join metrics with newlines
            metrics_text = '\n'.join(metrics)

            # Send to Victoria Metrics using helper method
            success = self._send_metrics(metrics_text, metric_name_prefix)
            if success:
                logger.info(f'Successfully exported {len(items)} {metric_name_prefix} metrics to Victoria Metrics')
            return success

        except Exception as e:
            logger.error(f'Error exporting {metric_name_prefix} metrics to Victoria Metrics: {str(e)}')
            return False

    def export_topclients(self, topclients):
        """
        Export topClients metrics to Victoria Metrics

        Args:
            topclients: List of TopClient model instances

        Returns:
            bool: True if export was successful, False otherwise
        """
        return self._export_ranked_metrics(
            topclients,
            metric_name_prefix='dnsdist_top_client',
            item_field_name='client',
            count_field_name='queries'
        )

    def export_topqueries(self, topqueries):
        """
        Export topQueries metrics to Victoria Metrics

        Args:
            topqueries: List of TopQuery model instances

        Returns:
            bool: True if export was successful, False otherwise
        """
        return self._export_ranked_metrics(
            topqueries,
            metric_name_prefix='dnsdist_top_query',
            item_field_name='query',
            count_field_name='count'
        )

    def export_agent_status(self, agents_status):
        """
        Export agent status metrics to Victoria Metrics

        Args:
            agents_status: List of dictionaries containing agent status information
                Each dict should have: agent_name, status, is_active, group_name (optional)

        Returns:
            bool: True if export was successful, False otherwise
        """
        if not self.enabled:
            logger.debug('Victoria Metrics is disabled, skipping agent status export')
            return False

        if not agents_status:
            logger.debug('No agent status to export')
            return True

        try:
            # Convert agent status to Prometheus format
            metrics = []
            for agent_status in agents_status:
                agent_name = escape_prometheus_label_value(agent_status.get('agent_name', 'unknown'))
                status = agent_status.get('status', 'unknown')
                is_active = agent_status.get('is_active', True)
                group_name = agent_status.get('group_name', None)

                # Escape group name for Prometheus label
                # Use "none" for agents without a group to distinguish from empty group names
                safe_group = escape_prometheus_label_value(group_name) if group_name else 'none'

                # Determine status value
                # DISABLED: is_active=False -> -1
                # DOWN: is_active=True but status is offline/error -> 0
                # UP: is_active=True and status is online -> 1
                if not is_active:
                    status_value = -1
                    status_label = 'DISABLED'
                elif status == 'online':
                    status_value = 1
                    status_label = 'UP'
                else:
                    # offline, error, or unknown
                    status_value = 0
                    status_label = 'DOWN'

                # Create metric line with both numeric value and status label
                # Note: We include both the numeric value and status label because:
                # - Numeric value enables mathematical operations (e.g., count(dnsdist_agent_status >= 0))
                # - Status label enables readable queries (e.g., {status="UP"} vs remembering value==1)
                # - This follows Prometheus best practices for status metrics
                # Group label is included to enable filtering by agent group
                metric_line = (
                    f'dnsdist_agent_status{{agent="{agent_name}",status="{status_label}",group="{safe_group}"}} '
                    f'{status_value}'
                )
                metrics.append(metric_line)

            # Join metrics with newlines
            metrics_text = '\n'.join(metrics)

            # Send to Victoria Metrics
            success = self._send_metrics(metrics_text, 'agent_status')
            if success:
                logger.info(f'Successfully exported {len(agents_status)} agent status metrics to Victoria Metrics')
            return success

        except Exception as e:
            logger.error(f'Error exporting agent status metrics to Victoria Metrics: {str(e)}')
            return False

    def export_metrics(self, topclients=None, topqueries=None, agents_status=None):
        """
        Export topClients, topQueries, and agent status metrics to Victoria Metrics

        Args:
            topclients: List of TopClient model instances (optional)
            topqueries: List of TopQuery model instances (optional)
            agents_status: List of agent status dictionaries (optional)

        Returns:
            tuple: (topclients_success, topqueries_success, agent_status_success)
        """
        topclients_success = True
        topqueries_success = True
        agent_status_success = True

        if topclients:
            topclients_success = self.export_topclients(topclients)

        if topqueries:
            topqueries_success = self.export_topqueries(topqueries)

        if agents_status:
            agent_status_success = self.export_agent_status(agents_status)

        return topclients_success, topqueries_success, agent_status_success

    def get_prometheus_metrics(self, topclients=None, topqueries=None, agents_status=None):
        """
        Generate Prometheus-formatted metrics as a string

        Args:
            topclients: List of TopClient model instances (optional)
            topqueries: List of TopQuery model instances (optional)
            agents_status: List of agent status dictionaries (optional)

        Returns:
            str: Prometheus-formatted metrics text
        """
        metrics = []

        # Add topclients metrics
        if topclients:
            for item in topclients:
                safe_agent = escape_prometheus_label_value(item.agent_name)
                safe_client = escape_prometheus_label_value(item.client)
                safe_rank = escape_prometheus_label_value(item.rank)

                # Create metric for count
                count_value = item.queries
                metric_line = (
                    f'dnsdist_top_client_queries{{agent="{safe_agent}",'
                    f'client="{safe_client}",rank="{safe_rank}"}} {count_value}'
                )
                metrics.append(metric_line)

                # Parse percentage (remove % sign and convert to float)
                try:
                    percentage_value = float(item.percentage.rstrip('%'))
                    percentage_metric = (
                        f'dnsdist_top_client_percentage{{agent="{safe_agent}",'
                        f'client="{safe_client}",rank="{safe_rank}"}} {percentage_value}'
                    )
                    metrics.append(percentage_metric)
                except (ValueError, AttributeError) as e:
                    logger.debug(f'Failed to parse percentage for client {safe_client}: {item.percentage} - {e}')

        # Add topqueries metrics
        if topqueries:
            for item in topqueries:
                safe_agent = escape_prometheus_label_value(item.agent_name)
                safe_query = escape_prometheus_label_value(item.query)
                safe_rank = escape_prometheus_label_value(item.rank)

                # Create metric for count
                count_value = item.count
                metric_line = (
                    f'dnsdist_top_query_count{{agent="{safe_agent}",'
                    f'query="{safe_query}",rank="{safe_rank}"}} {count_value}'
                )
                metrics.append(metric_line)

                # Parse percentage (remove % sign and convert to float)
                try:
                    percentage_value = float(item.percentage.rstrip('%'))
                    percentage_metric = (
                        f'dnsdist_top_query_percentage{{agent="{safe_agent}",'
                        f'query="{safe_query}",rank="{safe_rank}"}} {percentage_value}'
                    )
                    metrics.append(percentage_metric)
                except (ValueError, AttributeError) as e:
                    logger.debug(f'Failed to parse percentage for query {safe_query}: {item.percentage} - {e}')

        # Add agent status metrics
        if agents_status:
            for agent_status in agents_status:
                agent_name = escape_prometheus_label_value(agent_status.get('agent_name', 'unknown'))
                status = agent_status.get('status', 'unknown')
                is_active = agent_status.get('is_active', True)
                group_name = agent_status.get('group_name', None)

                # Escape group name for Prometheus label
                safe_group = escape_prometheus_label_value(group_name) if group_name else 'none'

                # Determine status value
                if not is_active:
                    status_value = -1
                    status_label = 'DISABLED'
                elif status == 'online':
                    status_value = 1
                    status_label = 'UP'
                else:
                    status_value = 0
                    status_label = 'DOWN'

                metric_line = (
                    f'dnsdist_agent_status{{agent="{agent_name}",status="{status_label}",group="{safe_group}"}} '
                    f'{status_value}'
                )
                metrics.append(metric_line)

        return '\n'.join(metrics)

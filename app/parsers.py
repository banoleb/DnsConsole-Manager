import re


def parse_showrules_output(output):
    """
    Parse showRules() command output into structured JSON format

    Args:
        output: String output from showRules() command

    Returns:
        List of dictionaries containing parsed rule information, or None if parsing fails
    """
    # Check for new format with UUID and Cr. Order
    is_valid_new, lines_new = validate_output(output, required_headers=['Name', 'UUID', 'Cr. Order', 'Matches', 'Rule', 'Action'])

    # If new format is valid, parse with UUID and Cr. Order
    if is_valid_new:
        rules = []
        # Process each data line (skip header)
        for line in lines_new[1:]:
            # Skip empty lines
            if not line.strip():
                continue

            # Try to parse the line with new format
            # Format: #   id name UUID   Cr. Order   Matches   Rule   Action
            # Example: 1   test  89875d6e-d517-4834-9ac8-0b4447fbc886           6         0 pool 'current_dc_1' is available    to pool current_dc_1
            # Pattern: number uuid creation_order optional_name matches rule_description action

            # Match pattern with UUID and creation order
            match = re.match(r'^(\d+)\s+(.*?)\s+([0-9a-fA-F\-]{36})\s+(\S+)\s+(\d+)\s+(.+?)\s{2,}(.+)$', line)

            if match:
                rule_id, name, uuid, creation_order, matches, rule, action = match.groups()
                rule = {
                    'id': int(rule_id),
                    'uuid': uuid.strip() if uuid.strip() else None,
                    'creation_order': int(creation_order),
                    'name': name.strip() if name.strip() else None,
                    'matches': int(matches),
                    'rule': rule.strip(),
                    'action': action.strip()
                }
                rules.append(rule)
            else:
                # Try a simpler pattern for lines without names
                # Pattern: number uuid creation_order matches rule_description action
                simple_match = re.match(r'^(\d+)\s+([0-9a-fA-F\-]+)\s+(\d+)\s+(\d+)\s+(.+?)\s{2,}(.+)$', line)
                if simple_match:
                    rule_id, uuid, creation_order, matches, rule, action = simple_match.groups()
                    rule = {
                        'id': int(rule_id),
                        'uuid': uuid.strip() if uuid.strip() else None,
                        'creation_order': int(creation_order),
                        'name': None,
                        'matches': int(matches),
                        'rule': rule.strip(),
                        'action': action.strip()
                    }
                    rules.append(rule)

        return rules if rules else None

    # Fall back to old format without UUID and Cr. Order for backward compatibility
    is_valid_old, lines_old = validate_output(output, required_headers=['Name', 'Matches', 'Rule', 'Action'])
    if not is_valid_old:
        return None

    rules = []
    # Process each data line (skip header)
    for line in lines_old[1:]:
        # Skip empty lines
        if not line.strip():
            continue

        # Try to parse the line
        # Format: #   Name   Matches Rule   Action
        # Example: 0   0 pool 'current_dc_1' is available   to pool current_dc_1
        # Pattern: number (name) matches rule_description action

        # Use regex to extract fields - the format has fixed-width columns
        # Match pattern: leading number, optional name, matches count, rule description, action
        match = re.match(r'^(\d+)\s+(.*?)\s+([0-9a-fA-F\-]{36})\s+(\S+)\s+(\d+)\s+(.+?)\s{2,}(.+)$', line)

        if match:
            rule_id, name, matches, rule, action = match.groups()
            rule = {
                'id': int(rule_id),
                'uuid': None,
                'creation_order': None,
                'name': name.strip() if name.strip() else None,
                'matches': int(matches),
                'rule': rule.strip(),
                'action': action.strip()
            }
            rules.append(rule)
        else:
            # Try a simpler pattern for lines without names
            # Pattern: number matches rule_description action
            simple_match = re.match(r'^(\d+)\s+(\d+)\s+(.+?)\s{2,}(.+)$', line)
            if simple_match:
                rule_id, matches, rule, action = simple_match.groups()
                rule = {
                    'id': int(rule_id),
                    'uuid': None,
                    'creation_order': None,
                    'name': None,
                    'matches': int(matches),
                    'rule': rule.strip(),
                    'action': action.strip()
                }
                rules.append(rule)

    return rules if rules else None


def parse_showservers_output(output):
    """
    Parse showServers() command output into structured JSON format

    Args:
        output: String output from showServers() command

    Returns:
        List of dictionaries containing parsed server information, or None if parsing fails
    """
    is_valid, lines = validate_output(output, required_headers=['Name', 'Address', 'State'])
    if not is_valid:
        return None

    servers = []
    # Process each data line (skip header)
    for line in lines[1:]:
        # Skip empty lines or summary lines (like "All")
        if not line.strip() or line.strip().startswith('All'):
            continue

        # Try to parse the line
        # Format: # Name Address State Qps Qlim Ord Wt Queries Drops Drate Lat TCP
        # Outstanding Pools
        # Example: 0 powerdns1 192.168.0.160:5233 down 0.0 0 1 1 0 0 0.0 - - 0
        # current_dc_1

        # Use regex to extract fields - the format has variable-width columns
        # Pattern: number, name, address, state, and then the rest of the fields
        pattern = (
            r'^(\d+)\s+(\S+)\s+(\S+)\s+(\S+)\s+(\S+)\s+(\S+)\s+(\S+)\s+(\S+)'
            r'\s+(\S+)\s+(\S+)\s+(\S+)\s+(\S+)\s+(\S+)\s+(\S+)\s+(.+)$'
        )
        match = re.match(pattern, line)

        if match:
            (server_id, name, address, state, qps, qlim, ord_val, wt, queries,
             drops, drate, lat, tcp, outstanding, pools) = match.groups()
            server = {
                'id': int(server_id),
                'name': name.strip(),
                'address': address.strip(),
                'state': state.strip(),
                'qps': qps.strip(),
                'qlim': qlim.strip(),
                'ord': ord_val.strip(),
                'wt': wt.strip(),
                'queries': queries.strip(),
                'drops': drops.strip(),
                'drate': drate.strip(),
                'lat': lat.strip(),
                'tcp': tcp.strip(),
                'outstanding': outstanding.strip(),
                'pools': pools.strip()
            }
            servers.append(server)

    return servers if servers else None


def parse_showdynblocks_output(output):
    """
    Parse showDynBlocks() command output to extract blocked addresses

    Args:
        output: String output from showDynBlocks() command

    Returns:
        Set of blocked addresses/subnets, or empty set if parsing fails
    """
    if not output or not isinstance(output, str):
        return set()

    blocked_addresses = set()
    lines = output.strip().split('\n')

    # showDynBlocks() output format typically shows blocked IPs/subnets
    # Example output might be:
    # What    Seconds Until    Reason
    # 192.168.1.100/32    3599    Suspicious activity
    for line in lines:
        # Skip header lines and empty lines
        if not line.strip() or 'What' in line or 'Seconds' in line:
            continue

        # Extract the first field which should be the IP/subnet
        parts = line.split()
        if parts:
            # The first part is typically the blocked address
            blocked_addresses.add(parts[0].strip())

    return blocked_addresses


def parse_showdynblocks_detailed(output):
    """
    Parse showDynBlocks() command output into structured JSON format

    Args:
        output: String output from showDynBlocks() command

    Returns:
        List of dictionaries containing parsed dynamic block information, or None if parsing fails
        Returns empty list if output is empty or has no blocks
    """
    if not output or not isinstance(output, str):
        return []

    lines = output.strip().split('\n')
    if len(lines) < 1:
        return []

    blocks = []

    # Check if this looks like showDynBlocks() output
    # First line should be the header with columns
    # Format: What   Seconds   Blocks Warning   Action   eBPF   Reason
    # The header might vary slightly, but should contain "What" and "Seconds"

    # has_header = False
    for line in lines:
        if 'What' in line and 'Seconds' in line:
            # has_header = True
            break

    # If there's no header, this might not be showDynBlocks() output
    # However, if output is empty (no blocks), there may be no header either
    # So we'll process lines anyway and see if we can parse them

    # Process each data line (skip header)
    for line in lines:
        # Skip empty lines and header lines
        if not line.strip() or 'What' in line or 'Seconds' in line:
            continue

        # Try to parse the line
        # Format: What   Seconds   Blocks Warning   Action   eBPF   Reason
        # Example: 192.168.100.1/32   53   17 false   Drop   *   Exceeded resp BW rate

        # Split by whitespace but be careful with the reason field which may contain spaces
        parts = line.split(None, 6)  # Split into at most 7 parts

        if len(parts) >= 6:  # We need at least 6 fields (reason is optional)
            # Parse numeric fields with proper error handling
            try:
                seconds = int(parts[1]) if parts[1].lstrip('-').isdigit() else None
            except (ValueError, AttributeError):
                seconds = None

            try:
                block_count = int(parts[2]) if parts[2].lstrip('-').isdigit() else None
            except (ValueError, AttributeError):
                block_count = None

            block = {
                'what': parts[0].strip(),
                'seconds': seconds,
                'blocks': block_count,
                'warning': parts[3].strip(),
                'action': parts[4].strip(),
                'ebpf': parts[5].strip(),
                'reason': parts[6].strip() if len(parts) > 6 else None
            }
            blocks.append(block)

    return blocks


def parse_topclients_output(output):
    """
    Parse topClients() command output into structured JSON format

    Args:
        output: String output from topClients() command

    Returns:
        List of dictionaries containing parsed top clients information, or None if parsing fails
    """
    return parse_ranked_metric_output(output, item_field_name='client', count_field_name='queries')


def parse_topqueries_output(output):
    """
    Parse topQueries() command output into structured JSON format

    Args:
        output: String output from topQueries() command

    Returns:
        List of dictionaries containing parsed top queries information, or None if parsing fails
    """
    return parse_ranked_metric_output(output, item_field_name='query', count_field_name='count')


def validate_output(output, required_headers=None):
    """
    Validate command output before parsing

    Args:
        output: String output from a dnsdist command
        required_headers: Optional list of header strings that must be present in the first line

    Returns:
        tuple: (is_valid, lines) where lines is the split output if valid
    """
    if not output or not isinstance(output, str):
        return False, None

    lines = output.strip().split('\n')
    if len(lines) < 1:
        return False, None

    # If required headers are specified, check the first line
    if required_headers:
        if len(lines) < 2:  # Need at least header and one data line
            return False, None

        header = lines[0]
        for required_header in required_headers:
            if required_header not in header:
                return False, None

    return True, lines


def parse_ranked_metric_output(output, item_field_name, count_field_name):
    """
    Generic parser for ranked metric output (topClients, topQueries, etc.)

    Args:
        output: String output from a dnsdist command
        item_field_name: Name of the field for the item (e.g., 'client', 'query')
        count_field_name: Name of the field for the count (e.g., 'queries', 'count')

    Returns:
        List of dictionaries containing parsed information, or None if parsing fails

    Expected format:
        rank  item  count percentage
        1  example.com  100 50.0%
    """
    is_valid, lines = validate_output(output)
    if not is_valid:
        return None

    items = []

    # Process each data line
    for line in lines:
        # Skip empty lines
        if not line.strip():
            continue

        # Try to parse the line
        # Format: rank  item  count percentage
        # Example: 1  172.24.5.153  1064 50.0%
        # Example: 3  Rest  0  0.0%

        # Use regex to extract fields
        match = re.match(r'^\s*(\d+)\s+(\S+)\s+(\d+)\s+([\d.]+%)\s*$', line)

        if match:
            rank, item, count, percentage = match.groups()
            item_data = {
                'rank': int(rank),
                item_field_name: item.strip(),
                count_field_name: int(count),
                'percentage': percentage.strip()
            }
            items.append(item_data)

    return items if items else None

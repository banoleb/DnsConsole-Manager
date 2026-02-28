
const { createApp } = Vue;

createApp({
    data() {

        return {

            agents: [],
            agentsRules: [],
            agentsServers: [],
            agentsTopClients: [],
            agentsTopQueries: [],
            expandedAgents: {},
            expandedRules: {},
            expandedServers: {},
            expandedTopClients: {},
            expandedTopQueries: {},
            agentCommands: {},
            agentOutputs: {},
            broadcastCommand: '',
            broadcastOutput: '',
            broadcastTarget: 'all',
            isRefreshing: false,
            modals: {
                help: false,
                history: false,
                agents: false,
                createGroup: false,
                editAgent: false
            },
            allCommands: [],
            commandSearch: '',
            history: [],
            historySearch: '',
            historyPagination: {
                currentPage: 1,
                perPage: 10,
                total: 0
            },
            newAgent: {
                name: '',
                ip: '',
                port: 8081,
                token: '',
                group_id: null
            },
            editAgent: {
                id: null,
                name: '',
                ip: '',
                port: 8081,
                token: '',
                group_id: null
            },
            agentsList: [],
            loadingAgentsList: false,
            agentMessage: null,
            editAgentMessage: null,
            groups: [],
            newGroup: {
                name: '',
                description: ''
            },
            autoRefreshInterval: null,
            groupMessage: null,
            selectedGroupFilter: 'all',
            showActiveOnly: true,
            // Autocomplete state
            autocomplete: {
                showBroadcast: false,
                showAgent: {},
                suggestions: [],
                selectedIndex: -1,
                activeInput: null
            }
        };
    },
    computed: {
        filteredAgents() {
            // console.log('filteredAgents called:', {
            //     selectedGroupFilter: this.selectedGroupFilter,
            //     agentsCount: this.agents?.length,
            //     agents: this.agents
            // });
            let agents = this.agents || [];
            if (this.showActiveOnly) {
                agents = agents.filter(agent => agent.is_active);
            }

            if (this.selectedGroupFilter === 'all') {
                return agents;
            } else if (this.selectedGroupFilter === 'none') {
                return agents.filter(agent => !agent.group_id);
            } else {
                return agents.filter(
                    agent => agent.group_id === Number(this.selectedGroupFilter)
                );
            }

        },

        filteredAgentsWithIndex() {
            const filtered = this.filteredAgents;

            const indexMap = new Map(
                this.agents
                    .map((agent, idx) => [agent.id, idx])
                    .filter(([id]) => id !== undefined && id !== null)
            );
            // console.log('Filtered agents from computed:', filtered);
            // console.log('Index map created:', Array.from(indexMap.entries()));
            return filtered.map((agent, fallbackIndex) => ({
                ...agent,
                originalIndex:
                    agent.id != null
                        ? (indexMap.get(agent.id) ?? fallbackIndex)
                        : fallbackIndex
            }));


        },
        filteredCommands() {
            if (!this.commandSearch) {
                return this.allCommands;
            }
            const search = this.commandSearch.toLowerCase();
            return this.allCommands.filter(cmd =>
                cmd.toLowerCase().includes(search)
            );
        },
        filteredHistory() {
            if (!this.historySearch) {
                return this.history;
            }
            const search = this.historySearch.toLowerCase();
            return this.history.filter(item =>
                item.command.toLowerCase().includes(search) ||
                item.agent_name.toLowerCase().includes(search) ||
                (item.error && item.error.toLowerCase().includes(search))
            );
        },
        totalPages() {
            return Math.ceil(this.historyPagination.total / this.historyPagination.perPage);
        },
        hasPreviousPage() {
            return this.historyPagination.currentPage > 1;
        },
        hasNextPage() {
            return this.historyPagination.currentPage < this.totalPages;
        }
    },
    mounted() {
        this.refreshAgents();
        this.loadCommands();
        this.loadGroups();
        // Auto-refresh every 2 seconds
        this.autoRefreshInterval = setInterval(() => {
            this.refreshAgents();
        }, 10000);
    },
    beforeUnmount() {
        if (this.autoRefreshInterval) {
            clearInterval(this.autoRefreshInterval);
        }
    },
    methods: {
        // # NEED REVIEW

        async refreshAgents() {
            this.isRefreshing = true;
            try {

                // const pathParts = window.location.pathname.split('/').filter(Boolean);
                // // Проверяем, что второй сегмент - это число (ID агента)
                // const idPattern = /^\d+$/;  // Только цифры
                // const url = (pathParts[0] === 'agents' && pathParts.length === 2 && idPattern.test(pathParts[1]))
                //     ? `/api/agents/${pathParts[1]}`
                //     : '/api/agents';


                const pathParts = window.location.pathname.split('/').filter(Boolean);
                const isAgentDetail = pathParts[0] === 'agents' &&
                                    pathParts.length === 2 &&
                                    /^\d+$/.test(pathParts[1]); // Только цифры

                const url = isAgentDetail ? `/api/agents/${pathParts[1]}` : '/api/agents';

                const response = await fetch(url);
                const data = await response.json();
                this.agents = data;
                // Initialize expanded state for new agents
                // this.agents.forEach((agent, index) => {
                //     if (!(index in this.expandedAgents)) {
                //         this.expandedAgents[index] = false;
                //     }
                // });

                // Fetch rules for all agents
                await this.fetchAgentsRules();

                // Fetch servers for all agents
                await this.fetchAgentsServers();

                // Fetch top clients for all agents
                await this.fetchAgentsTopClients();

                // Fetch top queries for all agents
                await this.fetchAgentsTopQueries();
            } catch (error) {
                console.error('Error loading agents:', error);
            } finally {
                setTimeout(() => {
                    this.isRefreshing = false;
                });
            }
        },
        async fetchAgentsRules() {
            try {
                const response = await fetch('/api/agents/rules');
                const data = await response.json();
                if (data.success) {
                    this.agentsRules = data.agents_rules;
                }
            } catch (error) {
                console.error('Error loading agents rules:', error);
            }
        },
        async fetchAgentsServers() {
            try {
                const response = await fetch('/api/agents/servers');
                const data = await response.json();
                if (data.success) {
                    this.agentsServers = data.agents_servers;
                }
            } catch (error) {
                console.error('Error loading agents servers:', error);
            }
        },
        async fetchAgentsTopClients() {
            try {
                const response = await fetch('/api/agents/topclients');
                const data = await response.json();
                if (data.success) {
                    this.agentsTopClients = data.agents_topclients;
                }
            } catch (error) {
                console.error('Error loading agents top clients:', error);
            }
        },
        async fetchAgentsTopQueries() {
            try {
                const response = await fetch('/api/agents/topqueries');
                const data = await response.json();
                if (data.success) {
                    this.agentsTopQueries = data.agents_topqueries;
                }
            } catch (error) {
                console.error('Error loading agents top queries:', error);
            }
        },
        getRulesCount(agentId) {
            const agentRules = this.agentsRules.find(ar => ar.agent_id === agentId);
            return agentRules ? agentRules.rules_count : 0;
        },
        getRules(agentId) {
            const agentRules = this.agentsRules.find(ar => ar.agent_id === agentId);
            return agentRules ? agentRules.rules : [];
        },
        getServersCount(agentId) {
            const agentServers = this.agentsServers.find(as => as.agent_id === agentId);
            return agentServers ? agentServers.servers_count : 0;
        },
        getServers(agentId) {
            const agentServers = this.agentsServers.find(as => as.agent_id === agentId);
            return agentServers ? agentServers.servers : [];
        },
        getTopClientsCount(agentId) {
            const agentTopClients = this.agentsTopClients.find(atc => atc.agent_id === agentId);
            return agentTopClients ? agentTopClients.topclients_count : 0;
        },
        getTopClients(agentId) {
            const agentTopClients = this.agentsTopClients.find(atc => atc.agent_id === agentId);
            return agentTopClients ? agentTopClients.topclients : [];
        },
        getTopQueriesCount(agentId) {
            const agentTopQueries = this.agentsTopQueries.find(atq => atq.agent_id === agentId);
            return agentTopQueries ? agentTopQueries.topqueries_count : 0;
        },
        getTopQueries(agentId) {
            const agentTopQueries = this.agentsTopQueries.find(atq => atq.agent_id === agentId);
            return agentTopQueries ? agentTopQueries.topqueries : [];
        },
        toggleRules(index) {
            this.expandedRules[index] = !this.expandedRules[index];
        },
        toggleServers(index) {
            this.expandedServers[index] = !this.expandedServers[index];
        },
        toggleTopClients(index) {
            this.expandedTopClients[index] = !this.expandedTopClients[index];
        },
        toggleTopQueries(index) {
            this.expandedTopQueries[index] = !this.expandedTopQueries[index];
        },
        toggleAgent(index) {
            this.expandedAgents[index] = !this.expandedAgents[index];
        },
        getStatusClass(status) {
            return status === 'online' ? 'status-online' :
                   status === 'offline' ? 'status-offline' : 'status-unknown';
        },
        getStatusIcon(status) {
            return status === 'online' ? '✅' :
                   status === 'offline' ? '❌' : '⚠️';
        },
        async sendBroadcastCommand(command) {
            // const command = this.broadcastCommand.trim();
            if (!command) {
                alert('Please enter a command');
                return;
            }

            const targetLabel = this.broadcastTarget === 'all' ? 'all agents' :
                               this.broadcastTarget === 'none' ? 'agents without group' :
                               this.groups.find(g => g.id === parseInt(this.broadcastTarget))?.name || 'selected group';

            this.broadcastOutput = `Executing command on ${targetLabel}...`;

            try {
                const response = await fetch('/api/command/broadcast', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json'
                    },
                    body: JSON.stringify({
                        command,
                        group_id: this.broadcastTarget
                    })
                });
                const data = await response.json();

                let html = '';

                    data.results.forEach((result, index) => {
                        const statusIcon = result.success ? '✓' : '✗';
                        const statusColor = result.success ? '#28a745' : '#dc3545';
                        const isLastItem = index === data.results.length - 1;

                        html += `<div style="margin-bottom: 15px; padding-bottom: 15px; ${isLastItem ? '' : 'border-bottom: 1px solid #444;'}">`;
                        html += `<div style="color: ${statusColor}; font-weight: bold;">${statusIcon} ${this.escapeHtml(result.agent_name)}</div>`;

                        if (result.success) {
                            // Check if this is showRules() with parsed data
                            if (result.parsed_rules && Array.isArray(result.parsed_rules)) {
                                html += '<div style="margin-top: 10px;">';
                                html += '<strong>Rules Information:</strong><br>';
                                html += '<table style="width: 100%; border-collapse: collapse; margin-top: 10px; font-size: 0.85em;">';
                                html += '<thead><tr style="border-bottom: 2px solid #4a4a4a;">';
                                html += '<th style="padding: 6px; text-align: left; border: 1px solid #4a4a4a;">ID</th>';
                                html += '<th style="padding: 6px; text-align: left; border: 1px solid #4a4a4a;">Name</th>';
                                html += '<th style="padding: 6px; text-align: left; border: 1px solid #4a4a4a;">UUID</th>';
                                html += '<th style="padding: 6px; text-align: left; border: 1px solid #4a4a4a;">Sort</th>';
                                html += '<th style="padding: 6px; text-align: left; border: 1px solid #4a4a4a;">Matches</th>';
                                html += '<th style="padding: 6px; text-align: left; border: 1px solid #4a4a4a;">Rule</th>';
                                html += '<th style="padding: 6px; text-align: left; border: 1px solid #4a4a4a;">Action</th>';
                                html += '</tr></thead><tbody>';

                                result.parsed_rules.forEach(rule => {
                                    html += '<tr style="border-bottom: 1px solid #3a3a3a;">';
                                    html += `<td style="padding: 6px; border: 1px solid #4a4a4a;">${rule.id}</td>`;
                                    html += `<td style="padding: 6px; border: 1px solid #4a4a4a;">${rule.name || '-'}</td>`;
                                    html += `<td style="padding: 6px; border: 1px solid #4a4a4a;"><a href="/rules/${rule.uuid}" style="color: #fb02fb; text-decoration: none;">${rule.uuid}</a></td>`;
                                    html += `<td style="padding: 6px; border: 1px solid #4a4a4a;">${rule.creation_order || '-'}</td>`;
                                    html += `<td style="padding: 6px; border: 1px solid #4a4a4a;">${rule.matches}</td>`;
                                    html += `<td style="padding: 6px; border: 1px solid #4a4a4a;">${this.escapeHtml(rule.rule)}</td>`;
                                    html += `<td style="padding: 6px; border: 1px solid #4a4a4a;">${this.escapeHtml(rule.action)}</td>`;
                                    html += '</tr>';
                                });

                                html += '</tbody></table></div>';
                            // Check if this is showServers() with parsed data
                            } else if (result.parsed_servers && Array.isArray(result.parsed_servers)) {
                                html += '<div style="margin-top: 10px;">';
                                html += '<strong>Servers Information:</strong><br>';
                                html += '<table style="width: 100%; border-collapse: collapse; margin-top: 10px; font-size: 0.85em;">';
                                html += '<thead><tr style="border-bottom: 2px solid #4a4a4a;">';
                                html += '<th style="padding: 6px; text-align: left; border: 1px solid #4a4a4a;">ID</th>';
                                html += '<th style="padding: 6px; text-align: left; border: 1px solid #4a4a4a;">Name</th>';
                                html += '<th style="padding: 6px; text-align: left; border: 1px solid #4a4a4a;">Address</th>';
                                html += '<th style="padding: 6px; text-align: left; border: 1px solid #4a4a4a;">State</th>';
                                html += '<th style="padding: 6px; text-align: left; border: 1px solid #4a4a4a;">QPS</th>';
                                html += '<th style="padding: 6px; text-align: left; border: 1px solid #4a4a4a;">Queries</th>';
                                html += '<th style="padding: 6px; text-align: left; border: 1px solid #4a4a4a;">Drops</th>';
                                html += '<th style="padding: 6px; text-align: left; border: 1px solid #4a4a4a;">Drate</th>';
                                html += '<th style="padding: 6px; text-align: left; border: 1px solid #4a4a4a;">Lat</th>';
                                html += '<th style="padding: 6px; text-align: left; border: 1px solid #4a4a4a;">TCP</th>';
                                html += '<th style="padding: 6px; text-align: left; border: 1px solid #4a4a4a;">Out</th>';
                                html += '<th style="padding: 6px; text-align: left; border: 1px solid #4a4a4a;">Pools</th>';
                                html += '</tr></thead><tbody>';

                                result.parsed_servers.forEach(server => {
                                    const stateColor = server.state === 'up' ? '#28a745' : '#dc3545';
                                    html += '<tr style="border-bottom: 1px solid #3a3a3a;">';
                                    html += `<td style="padding: 6px; border: 1px solid #4a4a4a;">${server.id}</td>`;
                                    html += `<td style="padding: 6px; border: 1px solid #4a4a4a;">${this.escapeHtml(server.name || '-')}</td>`;
                                    html += `<td style="padding: 6px; border: 1px solid #4a4a4a;">${this.escapeHtml(server.address)}</td>`;
                                    html += `<td style="padding: 6px; border: 1px solid #4a4a4a; color: ${stateColor}; font-weight: bold;">${this.escapeHtml(server.state)}</td>`;
                                    html += `<td style="padding: 6px; border: 1px solid #4a4a4a;">${this.escapeHtml(server.qps)}</td>`;
                                    html += `<td style="padding: 6px; border: 1px solid #4a4a4a;">${this.escapeHtml(server.queries)}</td>`;
                                    html += `<td style="padding: 6px; border: 1px solid #4a4a4a;">${this.escapeHtml(server.drops)}</td>`;
                                    html += `<td style="padding: 6px; border: 1px solid #4a4a4a;">${this.escapeHtml(server.drate)}</td>`;
                                    html += `<td style="padding: 6px; border: 1px solid #4a4a4a;">${this.escapeHtml(server.lat)}</td>`;
                                    html += `<td style="padding: 6px; border: 1px solid #4a4a4a;">${this.escapeHtml(server.tcp)}</td>`;
                                    html += `<td style="padding: 6px; border: 1px solid #4a4a4a;">${this.escapeHtml(server.outstanding)}</td>`;
                                    html += `<td style="padding: 6px; border: 1px solid #4a4a4a;">${this.escapeHtml(server.pools)}</td>`;
                                    html += '</tr>';
                                });

                                html += '</tbody></table></div>';
                            } else {
                                html += `<div style="margin-top: 5px;">${this.escapeHtml(result.result || 'Command executed successfully')}</div>`;
                            }
                        } else {
                            html += `<div style="color: #dc3545; margin-top: 5px;">Error: ${this.escapeHtml(result.error || 'Unknown error')}</div>`;
                        }

                        html += `</div>`;
                    });


                this.broadcastOutput = html;

                // Refresh rules count in the UI if this was a showRules command
                if (command.trim().startsWith('showRules')) {
                    await this.fetchAgentsRules();
                }
            } catch (error) {
                this.broadcastOutput = `<span style="color: #dc3545;">✗ Connection Error</span>\n\n${this.escapeHtml(error.message)}`;
            }
        },
        async sendCommand(agent, index, command) {
            // const command = this.agentCommands[index]?.trim();
            if (!command) {
                alert('Please enter a command');
                return;
            }

            this.agentOutputs[index] = 'Executing command...';

            try {
                const response = await fetch('/api/command', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json'
                    },
                    body: JSON.stringify({
                        agent_id: agent.id,
                        command: command
                    })
                });
                const data = await response.json();

                if (data.success) {
                    // Check if this is showRules() with parsed data
                    if (data.parsed_rules && Array.isArray(data.parsed_rules)) {
                        // Format parsed rules as a nice table
                        let output = '<span style="color: #28a745;">✓ Success</span>\n\n';
                        output += '<div style="margin-top: 10px;">';
                        output += '<strong>Rules Information:</strong><br>';
                        output += '<table style="width: 100%; border-collapse: collapse; margin-top: 10px; font-size: 0.9em;">';
                        output += '<thead><tr style="border-bottom: 2px solid #4a4a4a;">';
                        output += '<th style="padding: 8px; text-align: left; border: 1px solid #4a4a4a;">ID</th>';
                        output += '<th style="padding: 8px; text-align: left; border: 1px solid #4a4a4a;">Name</th>';
                        output += '<th style="padding: 8px; text-align: left; border: 1px solid #4a4a4a;">UUID</th>';
                        output += '<th style="padding: 8px; text-align: left; border: 1px solid #4a4a4a;">Sort</th>';
                        output += '<th style="padding: 8px; text-align: left; border: 1px solid #4a4a4a;">Matches</th>';
                        output += '<th style="padding: 8px; text-align: left; border: 1px solid #4a4a4a;">Rule</th>';
                        output += '<th style="padding: 8px; text-align: left; border: 1px solid #4a4a4a;">Action</th>';
                        output += '</tr></thead><tbody>';

                        data.parsed_rules.forEach(rule => {
                            output += '<tr style="border-bottom: 1px solid #3a3a3a;">';
                            output += `<td style="padding: 8px; border: 1px solid #4a4a4a;">${rule.id}</td>`;
                            output += `<td style="padding: 8px; border: 1px solid #4a4a4a;">${rule.name || '-'}</td>`;
                            output += `<td style="padding: 8px; border: 1px solid #4a4a4a;"><a href="/rules/${rule.uuid}" style="color: #fb02fb; text-decoration: none;">${rule.uuid}</a></td>`;
                            output += `<td style="padding: 8px; border: 1px solid #4a4a4a;">${rule.ncreation_orderame || '-'}</td>`;
                            output += `<td style="padding: 8px; border: 1px solid #4a4a4a;">${rule.matches}</td>`;
                            output += `<td style="padding: 8px; border: 1px solid #4a4a4a;">${this.escapeHtml(rule.rule)}</td>`;
                            output += `<td style="padding: 8px; border: 1px solid #4a4a4a;">${this.escapeHtml(rule.action)}</td>`;
                            output += '</tr>';
                        });

                        output += '</tbody></table></div>';
                        output += '<br><details style="margin-top: 10px;"><summary style="cursor: pointer; color: #6c757d;">Show raw output</summary>';
                        output += `<pre style="margin-top: 10px; white-space: pre-wrap;">${this.escapeHtml(data.result)}</pre>`;
                        output += '</details>';

                        this.agentOutputs[index] = output;

                        // Refresh rules count in the UI
                        await this.fetchAgentsRules();
                    // Check if this is showServers() with parsed data
                    } else if (data.parsed_servers && Array.isArray(data.parsed_servers)) {
                        // Format parsed servers as a nice table
                        let output = '<span style="color: #28a745;">✓ Success</span>\n\n';
                        output += '<div style="margin-top: 10px;">';
                        output += '<strong>Servers Information:</strong><br>';
                        output += '<table style="width: 100%; border-collapse: collapse; margin-top: 10px; font-size: 0.9em;">';
                        output += '<thead><tr style="border-bottom: 2px solid #4a4a4a;">';
                        output += '<th style="padding: 8px; text-align: left; border: 1px solid #4a4a4a;">ID</th>';
                        output += '<th style="padding: 8px; text-align: left; border: 1px solid #4a4a4a;">Name</th>';
                        output += '<th style="padding: 8px; text-align: left; border: 1px solid #4a4a4a;">Address</th>';
                        output += '<th style="padding: 8px; text-align: left; border: 1px solid #4a4a4a;">State</th>';
                        output += '<th style="padding: 8px; text-align: left; border: 1px solid #4a4a4a;">QPS</th>';
                        output += '<th style="padding: 8px; text-align: left; border: 1px solid #4a4a4a;">Queries</th>';
                        output += '<th style="padding: 8px; text-align: left; border: 1px solid #4a4a4a;">Drops</th>';
                        output += '<th style="padding: 8px; text-align: left; border: 1px solid #4a4a4a;">Drate</th>';
                        output += '<th style="padding: 8px; text-align: left; border: 1px solid #4a4a4a;">Lat</th>';
                        output += '<th style="padding: 8px; text-align: left; border: 1px solid #4a4a4a;">TCP</th>';
                        output += '<th style="padding: 8px; text-align: left; border: 1px solid #4a4a4a;">Out</th>';
                        output += '<th style="padding: 8px; text-align: left; border: 1px solid #4a4a4a;">Pools</th>';
                        output += '</tr></thead><tbody>';

                        data.parsed_servers.forEach(server => {
                            const stateColor = server.state === 'up' ? '#28a745' : '#dc3545';
                            output += '<tr style="border-bottom: 1px solid #3a3a3a;">';
                            output += `<td style="padding: 8px; border: 1px solid #4a4a4a;">${server.id}</td>`;
                            output += `<td style="padding: 8px; border: 1px solid #4a4a4a;">${this.escapeHtml(server.name || '-')}</td>`;
                            output += `<td style="padding: 8px; border: 1px solid #4a4a4a;">${this.escapeHtml(server.address)}</td>`;
                            output += `<td style="padding: 8px; border: 1px solid #4a4a4a; color: ${stateColor}; font-weight: bold;">${this.escapeHtml(server.state)}</td>`;
                            output += `<td style="padding: 8px; border: 1px solid #4a4a4a;">${this.escapeHtml(server.qps)}</td>`;
                            output += `<td style="padding: 8px; border: 1px solid #4a4a4a;">${this.escapeHtml(server.queries)}</td>`;
                            output += `<td style="padding: 8px; border: 1px solid #4a4a4a;">${this.escapeHtml(server.drops)}</td>`;
                            output += `<td style="padding: 8px; border: 1px solid #4a4a4a;">${this.escapeHtml(server.drate)}</td>`;
                            output += `<td style="padding: 8px; border: 1px solid #4a4a4a;">${this.escapeHtml(server.lat)}</td>`;
                            output += `<td style="padding: 8px; border: 1px solid #4a4a4a;">${this.escapeHtml(server.tcp)}</td>`;
                            output += `<td style="padding: 8px; border: 1px solid #4a4a4a;">${this.escapeHtml(server.outstanding)}</td>`;
                            output += `<td style="padding: 8px; border: 1px solid #4a4a4a;">${this.escapeHtml(server.pools)}</td>`;
                            output += '</tr>';
                        });

                        output += '</tbody></table></div>';
                        output += '<br><details style="margin-top: 10px;"><summary style="cursor: pointer; color: #6c757d;">Show raw output</summary>';
                        output += `<pre style="margin-top: 10px; white-space: pre-wrap;">${this.escapeHtml(data.result)}</pre>`;
                        output += '</details>';

                        this.agentOutputs[index] = output;
                    } else {
                        this.agentOutputs[index] = `<span style="color: #28a745;">✓ Success</span>\n\n${this.escapeHtml(data.result || 'Command executed successfully')}`;
                    }
                } else {
                    this.agentOutputs[index] = `<span style="color: #dc3545;">✗ Error</span>\n\n${this.escapeHtml(data.error || 'Unknown error')}`;
                }
            } catch (error) {
                this.agentOutputs[index] = `<span style="color: #dc3545;">✗ Connection Error</span>\n\n${this.escapeHtml(error.message)}`;
            }
        },
        handleBroadcastEnter() {
            // Only execute command if autocomplete is not showing
            if (!this.autocomplete.showBroadcast || this.autocomplete.suggestions.length === 0) {
                this.sendBroadcastCommand(this.broadcastCommand);
            }
        },
        handleAgentEnter(agent, index) {
            // Only execute command if autocomplete is not showing for this agent
            if (!this.autocomplete.showAgent[index] || this.autocomplete.suggestions.length === 0) {
                this.sendCommand(agent, index, this.agentCommands[agent.originalIndex]);
            }
        },
        async loadCommands() {
            try {
                const response = await fetch('/api/commands');
                const data = await response.json();
                if (data.success) {
                    this.allCommands = data.commands;
                }
            } catch (error) {
                console.error('Error loading commands:', error);
            }
        },
        async loadHistory() {
            try {
                const offset = (this.historyPagination.currentPage - 1) * this.historyPagination.perPage;
                const limit = this.historyPagination.perPage;

                const response = await fetch(`/api/history?limit=${limit}&offset=${offset}`);
                const data = await response.json();
                if (data.success && data.history) {
                    this.history = data.history;
                    this.historyPagination.total = data.total || 0;
                }
            } catch (error) {
                console.error('Error loading history:', error);
            }
        },
        copyCommand(command, event) {
            // Copy command to clipboard
            navigator.clipboard.writeText(command).then(() => {
                // Visual feedback - change button text temporarily
                const button = event.currentTarget;
                const originalText = button.textContent;
                button.textContent = '✓ Copied!';
                button.classList.add('copied');

                setTimeout(() => {
                    button.textContent = originalText;
                    button.classList.remove('copied');
                }, 2000);
            }).catch(err => {
                console.error('Failed to copy command:', err);
                // Fallback: provide visual feedback even on error
                const button = event.currentTarget;
                const originalText = button.textContent;
                button.textContent = '✗ Failed';
                button.style.backgroundColor = '#dc3545';
                button.style.borderColor = '#dc3545';

                setTimeout(() => {
                    button.textContent = originalText;
                    button.style.backgroundColor = '';
                    button.style.borderColor = '';
                }, 2000);
            });
        },
        async clearHistory() {
            if (!confirm('Are you sure you want to clear all command history? This action cannot be undone.')) {
                return;
            }

            try {
                const response = await fetch('/api/history', {
                    method: 'DELETE'
                });
                const data = await response.json();
                if (data.success) {
                    this.history = [];
                    this.historyPagination.total = 0;
                    this.historyPagination.currentPage = 1;
                    // Success - history is now empty, user can see it
                } else {
                    console.error('Error clearing history:', data.error);
                }
            } catch (error) {
                console.error('Error clearing history:', error);
            }
        },
        previousPage() {
            if (this.hasPreviousPage) {
                this.historyPagination.currentPage--;
                this.loadHistory();
            }
        },
        nextPage() {
            if (this.hasNextPage) {
                this.historyPagination.currentPage++;
                this.loadHistory();
            }
        },
        async loadAgentsList() {
            this.loadingAgentsList = true;
            try {
                const response = await fetch('/api/agents');
                const data = await response.json();
                this.agentsList = data;
            } catch (error) {
                console.error('Error loading agents list:', error);
            } finally {
                this.loadingAgentsList = false;
            }
        },
        async addAgent() {
            try {
                const response = await fetch('/api/agents', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json'
                    },
                    body: JSON.stringify({
                        agent_name: this.newAgent.name,
                        agent_ip: this.newAgent.ip,
                        agent_port: this.newAgent.port,
                        agent_token: this.newAgent.token,
                        group_id: this.newAgent.group_id
                    })
                });
                const data = await response.json();

                if (data.success) {
                    this.newAgent = { name: '', ip: '', port: 8081, token: '', group_id: null };
                    this.loadAgentsList();
                    this.refreshAgents();
                    this.showMessage('Agent added successfully!', 'success');
                } else {
                    this.showMessage('Error: ' + data.error, 'danger');
                }
            } catch (error) {
                this.showMessage('Error: ' + error.message, 'danger');
            }
        },
        async deleteAgent(agent) {
            if (!confirm(`Are you sure you want to delete agent "${agent.agent_name}"?`)) {
                return;
            }

            try {
                const response = await fetch(`/api/agents/${agent.id}`, {
                    method: 'DELETE'
                });
                const data = await response.json();

                if (data.success) {
                    this.loadAgentsList();
                    this.refreshAgents();
                    this.showMessage('Agent deleted successfully', 'success');
                } else {
                    this.showMessage('Error: ' + data.error, 'danger');
                }
            } catch (error) {
                this.showMessage('Error: ' + error.message, 'danger');
            }
        },
        async toggleAgentStatus(agent, event) {
            await this.updateAgentStatus(agent, event, false);
        },
        async toggleAgentStatusInSettings(agent, event) {
            await this.updateAgentStatus(agent, event, true);
        },
        async updateAgentStatus(agent, event, reloadAgentsList) {
            const newStatus = event.target.checked;
            try {
                const response = await fetch(`/api/agents/${agent.id}`, {
                    method: 'PUT',
                    headers: {
                        'Content-Type': 'application/json'
                    },
                    body: JSON.stringify({
                        is_active: newStatus
                    })
                });
                const data = await response.json();

                if (data.success) {
                    // Update the agent in the local state
                    agent.is_active = newStatus;
                    this.refreshAgents();
                    if (reloadAgentsList) {
                        this.loadAgentsList();
                    }
                } else {
                    // Revert checkbox if update failed
                    event.target.checked = !newStatus;
                    if (reloadAgentsList) {
                        this.showMessage('Error: ' + data.error, 'danger');
                    } else {
                        console.error('Error updating agent status:', data.error);
                    }
                }
            } catch (error) {
                // Revert checkbox if update failed
                event.target.checked = !newStatus;
                if (reloadAgentsList) {
                    this.showMessage('Error: ' + error.message, 'danger');
                } else {
                    console.error('Error updating agent status:', error);
                }
            }
        },
        showMessage(text, type) {
            this.agentMessage = { text, type };
            setTimeout(() => {
                this.agentMessage = null;
            }, 5000);
        },
        showHelpModal() {
            this.modals.help = true;
            this.commandSearch = '';
        },
        closeHelpModal() {
            this.modals.help = false;
        },
        showHistoryModal() {
            this.historyPagination.currentPage = 1;
            this.historySearch = '';
            this.modals.history = true;
            this.loadHistory();
        },
        closeHistoryModal() {
            this.modals.history = false;
        },
        showAgentsModal() {
            this.modals.agents = true;
            this.loadAgentsList();
            this.loadGroups();
        },
        closeAgentsModal() {
            this.modals.agents = false;
        },
        showCreateGroupModal() {
            this.modals.createGroup = true;
            this.newGroup = { name: '', description: '' };
            this.groupMessage = null;
        },
        closeCreateGroupModal() {
            this.modals.createGroup = false;
        },
        openEditAgentModal(agent) {
            this.editAgent = {
                id: agent.id,
                name: agent.name,
                ip: agent.agent_ip,
                port: agent.agent_port,
                token: agent.agent_token,
                group_id: agent.group_id
            };
            // console.log('openEditAgentModal:', this.editAgent);
            // console.log('openEditAgentModal:', agent);


            this.editAgentMessage = null;
            this.modals.editAgent = true;
        },
        closeEditAgentModal() {
            this.modals.editAgent = false;
            this.editAgent = {
                id: null,
                name: '',
                ip: '',
                port: '8081',
                token: '',
                group_id: null
            };
            this.editAgentMessage = null;
        },
        async updateAgent() {
            try {
                const response = await fetch(`/api/agents/${this.editAgent.id}`, {
                    method: 'PUT',
                    headers: {
                        'Content-Type': 'application/json'
                    },
                    body: JSON.stringify({
                        agent_ip: this.editAgent.ip,
                        agent_port: this.editAgent.port,
                        agent_token: this.editAgent.token,
                        group_id: this.editAgent.group_id
                    })
                });
                const data = await response.json();

                if (data.success) {
                    this.editAgentMessage = { text: 'Agent updated successfully!', type: 'success' };
                    this.loadAgentsList();
                    this.refreshAgents();
                    setTimeout(() => {
                        this.closeEditAgentModal();
                    }, 1500);
                } else {
                    this.editAgentMessage = { text: 'Error: ' + data.error, type: 'danger' };
                }
            } catch (error) {
                this.editAgentMessage = { text: 'Error: ' + error.message, type: 'danger' };
            }
        },
        async loadGroups() {
            try {
                const response = await fetch('/api/groups');
                const data = await response.json();

                if (data.success) {
                    this.groups = data.groups || [];
                } else {
                    console.error('Error loading groups:', data.error);
                }
            } catch (error) {
                console.error('Error loading groups:', error);
            }
        },
        async createGroup() {
            try {
                const response = await fetch('/api/groups', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json'
                    },
                    body: JSON.stringify({
                        name: this.newGroup.name,
                        description: this.newGroup.description
                    })
                });
                const data = await response.json();

                if (data.success) {
                    this.loadGroups();
                    this.groupMessage = { text: 'Group created successfully!', type: 'success' };
                    setTimeout(() => {
                        this.closeCreateGroupModal();
                    }, 1500);
                } else {
                    this.groupMessage = { text: 'Error: ' + data.error, type: 'danger' };
                }
            } catch (error) {
                this.groupMessage = { text: 'Error: ' + error.message, type: 'danger' };
            }
        },
        formatTimestamp(timestamp) {
            const date = new Date(timestamp);
            return date.toLocaleString('en-US', {
                year: 'numeric',
                month: 'short',
                day: 'numeric',
                hour: '2-digit',
                minute: '2-digit',
                second: '2-digit'
            });
        },
        escapeHtml(text) {
            const div = document.createElement('div');
            div.textContent = text;
            return div.innerHTML;
        },
        // Autocomplete methods
        async fetchAutocompleteSuggestions(query) {
            if (!query || query.trim().length === 0) {
                this.autocomplete.suggestions = [];
                return;
            }

            try {
                const response = await fetch(`/api/history/autocomplete?q=${encodeURIComponent(query)}&limit=10`);
                const data = await response.json();

                if (data.success) {
                    this.autocomplete.suggestions = data.suggestions || [];
                } else {
                    this.autocomplete.suggestions = [];
                }
            } catch (error) {
                console.error('Error fetching autocomplete suggestions:', error);
                this.autocomplete.suggestions = [];
            }
        },
        async onBroadcastCommandInput() {
            await this.fetchAutocompleteSuggestions(this.broadcastCommand);
            this.autocomplete.showBroadcast = this.autocomplete.suggestions.length > 0;
            this.autocomplete.selectedIndex = -1;
            this.autocomplete.activeInput = 'broadcast';
        },
        async onAgentCommandInput(index) {
            const command = this.agentCommands[index] || '';
            await this.fetchAutocompleteSuggestions(command);
            this.autocomplete.showAgent[index] = this.autocomplete.suggestions.length > 0;
            this.autocomplete.selectedIndex = -1;
            this.autocomplete.activeInput = `agent-${index}`;
        },
        selectSuggestion(suggestion, inputType, index = null) {
            if (inputType === 'broadcast') {
                this.broadcastCommand = suggestion;
                this.autocomplete.showBroadcast = false;
            } else if (inputType === 'agent') {
                this.agentCommands[index] = suggestion;
                this.autocomplete.showAgent[index] = false;
            }
            this.autocomplete.suggestions = [];
            this.autocomplete.selectedIndex = -1;
        },
        handleAutocompleteKeydown(event, inputType, index = null) {
            const showDropdown = inputType === 'broadcast' ? this.autocomplete.showBroadcast : this.autocomplete.showAgent[index];

            if (!showDropdown || this.autocomplete.suggestions.length === 0) {
                return;
            }

            switch(event.key) {
                case 'ArrowDown':
                    event.preventDefault();
                    this.autocomplete.selectedIndex = Math.min(
                        this.autocomplete.selectedIndex + 1,
                        this.autocomplete.suggestions.length - 1
                    );
                    break;
                case 'ArrowUp':
                    event.preventDefault();
                    this.autocomplete.selectedIndex = Math.max(this.autocomplete.selectedIndex - 1, -1);
                    break;
                case 'ArrowRight':
                    if (this.autocomplete.selectedIndex >= 0) {
                        event.preventDefault();
                        const suggestion = this.autocomplete.suggestions[this.autocomplete.selectedIndex];
                        this.selectSuggestion(suggestion, inputType, index);
                    }
                    break;
                case 'Escape':
                    event.preventDefault();
                    if (inputType === 'broadcast') {
                        this.autocomplete.showBroadcast = false;
                    } else {
                        this.autocomplete.showAgent[index] = false;
                    }
                    this.autocomplete.suggestions = [];
                    this.autocomplete.selectedIndex = -1;
                    break;
            }
        },
        hideAutocomplete(inputType, index = null) {
            // Delay hiding to allow click events on suggestions to fire
            setTimeout(() => {
                if (inputType === 'broadcast') {
                    this.autocomplete.showBroadcast = false;
                } else if (inputType === 'agent') {
                    this.autocomplete.showAgent[index] = false;
                }
                this.autocomplete.suggestions = [];
                this.autocomplete.selectedIndex = -1;
            }, 200);
        }
    }
}).mount('#app');

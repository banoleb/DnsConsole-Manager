Vue.createApp({
    data() {
        return {
            // Data arrays
            topClients: [],
            topQueries: [],
            agents: [],
            // Agent filter
            selectedAgent: '',

            // Clients search and sort
            clientsSearchQuery: '',
            clientsSortKey: 'rank',
            clientsSortOrder: 'asc',
            clientsCurrentPage: 1,
            clientsItemsPerPage: 50,

            // Queries search and sort
            queriesSearchQuery: '',
            queriesSortKey: 'rank',
            queriesSortOrder: 'asc',
            queriesCurrentPage: 1,
            queriesItemsPerPage: 50,

            // UI state
            loading: false,
            isRefreshing: false
        };
    },
    computed: {
        filteredClients() {
            let filtered = this.topClients;

            // Apply agent filter
            if (this.selectedAgent) {
                filtered = filtered.filter(client => client.agent_name === this.selectedAgent);
            }

            // Apply search filter
            if (this.clientsSearchQuery) {
                const query = this.clientsSearchQuery.toLowerCase();
                filtered = filtered.filter(client => {
                    return (
                        (client.agent_name && client.agent_name.toLowerCase().includes(query)) ||
                        (client.client && client.client.toLowerCase().includes(query)) ||
                        (client.queries && client.queries.toString().includes(query))
                    );
                });
            }

            // Apply sorting
            filtered.sort((a, b) => {
                let aVal = a[this.clientsSortKey];
                let bVal = b[this.clientsSortKey];

                // Handle null values
                if (aVal === null || aVal === undefined) aVal = '';
                if (bVal === null || bVal === undefined) bVal = '';

                // String comparison
                if (typeof aVal === 'string') {
                    aVal = aVal.toLowerCase();
                    bVal = bVal.toLowerCase();
                }

                if (aVal < bVal) return this.clientsSortOrder === 'asc' ? -1 : 1;
                if (aVal > bVal) return this.clientsSortOrder === 'asc' ? 1 : -1;
                return 0;
            });

            return filtered;
        },
        totalClientsPages() {
            return Math.ceil(this.filteredClients.length / this.clientsItemsPerPage);
        },
        paginatedClients() {
            const start = (this.clientsCurrentPage - 1) * this.clientsItemsPerPage;
            const end = start + this.clientsItemsPerPage;
            return this.filteredClients.slice(start, end);
        },
        filteredQueries() {
            let filtered = this.topQueries;

            // Apply agent filter
            if (this.selectedAgent) {
                filtered = filtered.filter(query => query.agent_name === this.selectedAgent);
            }

            // Apply search filter
            if (this.queriesSearchQuery) {
                const query = this.queriesSearchQuery.toLowerCase();
                filtered = filtered.filter(q => {
                    return (
                        (q.agent_name && q.agent_name.toLowerCase().includes(query)) ||
                        (q.query && q.query.toLowerCase().includes(query)) ||
                        (q.count && q.count.toString().includes(query))
                    );
                });
            }

            // Apply sorting
            filtered.sort((a, b) => {
                let aVal = a[this.queriesSortKey];
                let bVal = b[this.queriesSortKey];

                // Handle null values
                if (aVal === null || aVal === undefined) aVal = '';
                if (bVal === null || bVal === undefined) bVal = '';

                // String comparison
                if (typeof aVal === 'string') {
                    aVal = aVal.toLowerCase();
                    bVal = bVal.toLowerCase();
                }

                if (aVal < bVal) return this.queriesSortOrder === 'asc' ? -1 : 1;
                if (aVal > bVal) return this.queriesSortOrder === 'asc' ? 1 : -1;
                return 0;
            });

            return filtered;
        },
        totalQueriesPages() {
            return Math.ceil(this.filteredQueries.length / this.queriesItemsPerPage);
        },
        paginatedQueries() {
            const start = (this.queriesCurrentPage - 1) * this.queriesItemsPerPage;
            const end = start + this.queriesItemsPerPage;
            return this.filteredQueries.slice(start, end);
        }
    },
    methods: {
        async loadData() {
            this.loading = true;
            this.isRefreshing = true;
            try {
                // Load agents for the filter
                const agentsResponse = await fetch('/api/agents');
                const agentsData = await agentsResponse.json();
                if (agentsData.success) {
                    this.agents = agentsData.agents;
                }

                // Load top clients
                const clientsResponse = await fetch('/api/agents/topclients');
                const clientsData = await clientsResponse.json();
                if (clientsData.success) {
                    // Flatten the data structure
                    this.topClients = [];
                    clientsData.agents_topclients.forEach(agentData => {
                        agentData.topclients.forEach(client => {
                            this.topClients.push({
                                ...client,
                                agent_name: agentData.agent_name
                            });
                        });
                    });
                }

                // Load top queries
                const queriesResponse = await fetch('/api/agents/topqueries');
                const queriesData = await queriesResponse.json();
                if (queriesData.success) {
                    // Flatten the data structure
                    this.topQueries = [];
                    queriesData.agents_topqueries.forEach(agentData => {
                        agentData.topqueries.forEach(query => {
                            this.topQueries.push({
                                ...query,
                                agent_name: agentData.agent_name
                            });
                        });
                    });
                }
            } catch (error) {
                console.error('Error loading data:', error);
            } finally {
                this.loading = false;
                this.isRefreshing = false;
            }
        },
        sortClientsBy(key) {
            if (this.clientsSortKey === key) {
                this.clientsSortOrder = this.clientsSortOrder === 'asc' ? 'desc' : 'asc';
            } else {
                this.clientsSortKey = key;
                this.clientsSortOrder = 'asc';
            }
            this.clientsCurrentPage = 1;
        },
        getClientsSortIcon(key) {
            if (this.clientsSortKey !== key) return '↕';
            return this.clientsSortOrder === 'asc' ? '↑' : '↓';
        },
        sortQueriesBy(key) {
            if (this.queriesSortKey === key) {
                this.queriesSortOrder = this.queriesSortOrder === 'asc' ? 'desc' : 'asc';
            } else {
                this.queriesSortKey = key;
                this.queriesSortOrder = 'asc';
            }
            this.queriesCurrentPage = 1;
        },
        getQueriesSortIcon(key) {
            if (this.queriesSortKey !== key) return '↕';
            return this.queriesSortOrder === 'asc' ? '↑' : '↓';
        }
    },
    watch: {
        clientsSearchQuery() {
            this.clientsCurrentPage = 1;
        },
        queriesSearchQuery() {
            this.queriesCurrentPage = 1;
        },
        selectedAgent() {
            this.clientsCurrentPage = 1;
            this.queriesCurrentPage = 1;
        }
    },
    mounted() {
        this.loadData();
    }
}).mount('#app');

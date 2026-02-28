const { createApp } = Vue;

createApp({
    data() {
        return {
            rules: [],
            searchQuery: '',
            sortKey: 'id',
            sortOrder: 'asc',
            loading: false,
            isRefreshing: false,
            currentPage: 1,
            itemsPerPage: 50,
            showActiveOnly: true
        };
    },
    computed: {
        filteredRules() {
            let filtered = this.rules;
            if (this.showActiveOnly) {
                filtered = filtered.filter(rule => rule.agent_online === 1);
            }
            // Apply search filter
            if (this.searchQuery) {
                const query = this.searchQuery.toLowerCase();
                filtered = filtered.filter(rule => {
                    return (
                        (rule.agent_name && rule.agent_name.toLowerCase().includes(query)) ||
                        (rule.name && rule.name.toLowerCase().includes(query)) ||
                        (rule.uuid && rule.uuid.toLowerCase().includes(query)) ||
                        (rule.rule && rule.rule.toLowerCase().includes(query)) ||
                        (rule.action && rule.action.toLowerCase().includes(query)) ||
                        (rule.rule_id && rule.rule_id.toString().includes(query)) ||
                        (rule.id && rule.id.toString().includes(query))
                    );
                });
            }

            // Apply sorting
            filtered.sort((a, b) => {
                let aVal = a[this.sortKey];
                let bVal = b[this.sortKey];

                // Handle null values
                if (aVal === null || aVal === undefined) aVal = '';
                if (bVal === null || bVal === undefined) bVal = '';

                // String comparison
                if (typeof aVal === 'string') {
                    aVal = aVal.toLowerCase();
                    bVal = bVal.toLowerCase();
                }

                if (aVal < bVal) return this.sortOrder === 'asc' ? -1 : 1;
                if (aVal > bVal) return this.sortOrder === 'asc' ? 1 : -1;
                return 0;
            });

            return filtered;
        },
        totalPages() {
            return Math.ceil(this.filteredRules.length / this.itemsPerPage);
        },
        paginatedRules() {
            const start = (this.currentPage - 1) * this.itemsPerPage;
            const end = start + this.itemsPerPage;
            return this.filteredRules.slice(start, end);
        },
    },
    methods: {
        async loadData() {
            this.loading = true;
            this.isRefreshing = true;
            try {
                const pathParts = window.location.pathname.split('/').filter(Boolean);
                const uuidPattern = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;
                const url = (pathParts[0] === 'rules' && pathParts.length === 2 && uuidPattern.test(pathParts[1]))
                    ? `/api/rules/${pathParts[1]}`
                    : '/api/rules';
                const response = await fetch(url);
                const data = await response.json();
                if (data.success) {
                    this.rules = data.rules;


                }
            } catch (error) {
                console.error('Error loading rules:', error);
            } finally {
                this.loading = false;
                this.isRefreshing = false;
            }
        },
        sortBy(key) {
            if (this.sortKey === key) {
                // Toggle sort order
                this.sortOrder = this.sortOrder === 'asc' ? 'desc' : 'asc';
            } else {
                this.sortKey = key;
                this.sortOrder = 'asc';
            }
            // Reset to first page when sorting changes
            this.currentPage = 1;
        },
        getSortIcon(key) {
            if (this.sortKey !== key) return '↕';
            return this.sortOrder === 'asc' ? '↑' : '↓';
        },
        formatDate(dateString) {
            if (!dateString) return '-';
            const date = new Date(dateString);
            return date.toLocaleString();
        },
        async deleteRule(rule) {
            const displayName = rule.name || `Rule ID ${rule.rule_id}`;
            if (!confirm(`Are you sure you want to delete rule "${displayName}" from agent "${rule.agent_name}"?\nThis action cannot be undone.`)) {
                return;
            }

            try {
                const response = await fetch(`/api/rules/${rule.id}`, {
                    method: 'DELETE'
                });
                const data = await response.json();

                if (response.ok && data.success) {
                    this.rules = this.rules.filter(r => r.id !== rule.id);
                } else {
                    alert('Error: ' + data.error);
                }
            } catch (error) {
                console.error('Error deleting rule:', error);
                alert('Failed to delete rule. Please try again.');
            }
        }
    },
    watch: {
        searchQuery() {
            // Reset to first page when search changes
            this.currentPage = 1;
        }
    },
    mounted() {
        this.loadData();
    }
}).mount('#app');

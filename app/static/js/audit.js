const { createApp } = Vue;

createApp({
    data() {
        return {
            auditLogs: [],
            loading: true,
            clearing: false,
            pagination: {
                page: 1,
                per_page: 50,
                total_count: 0,
                total_pages: 0,
                has_next: false,
                has_prev: false
            }
        };
    },
    methods: {
        async loadAuditLogs(page = 1) {
            this.loading = true;
            try {
                const response = await fetch(`/api/audit?page=${page}&per_page=${this.pagination.per_page}`);
                const data = await response.json();

                if (data.success) {
                    this.auditLogs = data.audit_logs;
                    this.pagination = data.pagination;
                } else {
                    console.error('Failed to load audit logs:', data.error);
                }
            } catch (error) {
                console.error('Error loading audit logs:', error);
            } finally {
                this.loading = false;
            }
        },
        loadPage(page) {
            if (page >= 1 && page <= this.pagination.total_pages) {
                this.loadAuditLogs(page);
            }
        },
        async clearOldLogs() {
            // Show confirmation dialog
            if (!confirm('Are you sure you want to delete all audit logs older than 3 days? This action cannot be undone.')) {
                return;
            }

            this.clearing = true;
            try {
                const response = await fetch('/api/audit/cleanup', {
                    method: 'DELETE'
                });
                const data = await response.json();

                if (data.success) {
                    alert(`Successfully deleted ${data.deleted_count} old audit logs.`);
                    // Reload the current page to show updated data
                    this.loadAuditLogs(this.pagination.page);
                } else {
                    alert(`Error: ${data.error}`);
                }
            } catch (error) {
                console.error('Error clearing old logs:', error);
                alert('Failed to clear old logs. Please try again.');
            } finally {
                this.clearing = false;
            }
        },
        formatDateTime(dateStr) {
            if (!dateStr) return '-';
            const date = new Date(dateStr);
            return date.toLocaleString();
        }
    },
    mounted() {
        this.loadAuditLogs();
    }
}).mount('#app');

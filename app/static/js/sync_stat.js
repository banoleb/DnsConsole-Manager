
Vue.createApp({
    data() {
        return {

            currentPath: window.location.pathname,
            autoRefreshInterval: null,
            syncStatusInterval: null,
            backendHealthInterval: null,
            authEnabled: false,
            syncStatus: {
                last_sync_time: null,
                status: 'Never',
                synced_agents_count: 0,
                failed_agents_count: 0,
                error_message: null
            },
            
            backendHealth: {
                status: 'checking',
                lastCheck: null,
                error: null
            },
            isDarkTheme: true,
              
        };
    },

    methods: {
        isActivePage(path) {
            return window.location.pathname === path;
          },
        async fetchBackendHealth() {
            try {
                const response = await fetch('/api/backend-health');
                const data = await response.json();
                if (data.success) {
                    this.backendHealth.status = 'healthy';
                    this.backendHealth.error = null;
                } else {
                    this.backendHealth.status = 'unhealthy';
                    this.backendHealth.error = data.error || 'Unknown error';
                }
                this.backendHealth.lastCheck = new Date();
            } catch (error) {
                console.error('Error checking backend health:', error);
                this.backendHealth.status = 'unavailable';
                this.backendHealth.error = 'Backend server is unavailable';
                this.backendHealth.lastCheck = new Date();
            }
        },
        async fetchSyncStatus() {
            try {
                const response = await fetch('/api/sync-status');
                const data = await response.json();
                if (data.success && data.sync_status) {
                    this.syncStatus = data.sync_status;
                }
            } catch (error) {
                console.error('Error loading sync status:', error);
            }
        },
        formatSyncTime(timeString) {
            if (!timeString) return 'Never';
            const date = new Date(timeString);
            const hours = String(date.getHours()).padStart(2, '0');
            const minutes = String(date.getMinutes()).padStart(2, '0');
            const seconds = String(date.getSeconds()).padStart(2, '0');
            return `${hours}:${minutes}:${seconds}`;
        },
        getSyncStatusClass(status) {
            if (status === 'Success') {
                return 'sync-status-success';
            } else if (status === 'Partial') {
                return 'sync-status-partial';
            } else if (status === 'Failed') {
                return 'sync-status-failed';
            } else {
                return 'sync-status-never';
            }
        },
        getBackendStatusClass(status) {
            if (status === 'healthy') {
                return 'sync-status-success';
            } else if (status === 'checking') {
                return 'sync-status-never';
            } else {
                return 'sync-status-failed';
            }
        },
        getBackendStatusText(status) {
            if (status === 'healthy') {
                return '✓ Backend OK';
            } else if (status === 'checking') {
                return '⏳ Checking...';
            } else if (status === 'unavailable') {
                return '✗ Backend Unavailable';
            } else {
                return '✗ Backend Error';
            }
        },
        toggleTheme() {
            this.isDarkTheme = !this.isDarkTheme;
            if (this.isDarkTheme) {
                document.body.classList.remove('light-theme');
                localStorage.setItem('theme', 'dark');
            } else {
                document.body.classList.add('light-theme');
                localStorage.setItem('theme', 'light');
            }
        },
        loadTheme() {
            const savedTheme = localStorage.getItem('theme');
            if (savedTheme === 'light') {
                this.isDarkTheme = false;
                document.body.classList.add('light-theme');
            } else {
                this.isDarkTheme = true;
                document.body.classList.remove('light-theme');
            }
        },
        isActivePage(path) {
            if (path === '/') {
                return this.currentPath === '/';
            }
            return this.currentPath === path || this.currentPath.startsWith(path + '/');
        }
    },
    mounted() {
        // Load theme preference
        this.loadTheme();

 
        console.log('1. this.$el:', this.$el);
        console.log('2. this.$el.outerHTML:', this.$el.outerHTML);
        console.log('3. this.$el.dataset:', this.$el.dataset);
        console.log('4. Все data-атрибуты:', Object.keys(this.$el.dataset));
        console.log('5. Значение authEnabled:', this.$el.dataset.authEnabled);
        
        // Пробуем разные варианты доступа
        console.log('6. getAttribute:', this.$el.getAttribute('data-auth-enabled'));
        
        this.authEnabled = this.$el.dataset.authEnabled === 'true';
        console.log('7. Итоговое authEnabled:', this.authEnabled);
        // Fetch backend health immediately and every 10 seconds
        this.fetchBackendHealth();
        this.backendHealthInterval = setInterval(() => {
            this.fetchBackendHealth();
        }, 5000);

        this.fetchSyncStatus();
        // Fetch sync status every 5 seconds
        this.syncStatusInterval = setInterval(() => {
            this.fetchSyncStatus();
        }, 5000);
    },
    beforeUnmount() {
        if (this.autoRefreshInterval) {
            clearInterval(this.autoRefreshInterval);
        }
        if (this.syncStatusInterval) {
            clearInterval(this.syncStatusInterval);
        }
        if (this.backendHealthInterval) {
            clearInterval(this.backendHealthInterval);
        }
    }
    
}).mount('#app2');

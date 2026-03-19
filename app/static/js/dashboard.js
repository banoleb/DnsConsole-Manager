Vue.createApp({
    data() {
        return {
            agents: [],
            groups: [],
            agentsRules: [],
            agentsServers: [],
            dynblockRules: [],
            accessLists: [],
            showActiveOnly: true,
            loading: false
        };
    },
    computed: {
        totalAgents() {
            return this.agents.length;
        },
        onlineAgents() {
            return this.agents.filter(a => a.status === 'online').length;
        },
        offlineAgents() {
            return this.agents.filter(a => a.status !== 'online').length;
        },

        totalGroups() {
            return this.groups.length;
        },
        ungroupedAgents() {
            return this.agents.filter(a => !a.group_id).length;
        },
        ungroupedAgentsList() {
            return this.agents.filter(a => !a.group_id);
        },
        totalRules() {
            return this.agentsRules.reduce((sum, ar) => sum + (ar.rules_count || 0), 0);
        },

        totalServers() {
            let count = 0;
            this.agentsServers.forEach(as => {
                count += (as.servers ? as.servers.length : 0);
            });
            return count;
        },
        upServers() {
            let count = 0;
            this.agentsServers.forEach(as => {
                if (as.servers) {
                    count += as.servers.filter(s => s.state === 'up').length;
                }
            });
            return count;
        },
        downServers() {
            return this.totalServers - this.upServers;
        },
        totalDynblockRules() {
            return this.dynblockRules.length;
        },
        // totalAccessList() {
        //     return this.accessLists.filter(r => r.is_active).length;
        // },
        activeDynblockRules() {
            return this.dynblockRules.filter(r => r.is_active).length;
        },
        
    },
    methods: {
        async fetchAll() {
            this.loading = true;
            try {
                await Promise.all([
                    this.fetchAgents(),
                    this.fetchGroups(),
                    this.fetchAgentsRules(),
                    this.fetchAgentsServers(),
                    this.fetchDynblockRules(),
                    this.fetchAccessLists()
                ]);
            } finally {
                this.loading = false;
            }
        },
        async fetchAgents() {
            try {
                const res = await fetch('/api/agents');
                const data = await res.json();
                this.agents = Array.isArray(data) ? data : [];
                
            } catch (e) {
                console.error('Error fetching agents:', e);
            }
        },

        async fetchGroups() {
            try {
                const res = await fetch('/api/groups');
                const data = await res.json();
                this.groups = (data.success && Array.isArray(data.groups)) ? data.groups : [];
            } catch (e) {
                console.error('Error fetching groups:', e);
            }
        },
        async fetchAgentsRules() {
            try {
                const res = await fetch('/api/agents/rules');
                const data = await res.json();
                this.agentsRules = (data.success && Array.isArray(data.agents_rules)) ? data.agents_rules : [];
            } catch (e) {
                console.error('Error fetching agents rules:', e);
            }
        },
        async fetchAgentsServers() {
            try {
                const res = await fetch('/api/agents/servers');
                const data = await res.json();
                this.agentsServers = (data.success && Array.isArray(data.agents_servers)) ? data.agents_servers : [];
            } catch (e) {
                console.error('Error fetching agents servers:', e);
            }
        },
        async fetchDynblockRules() {
            try {
                const res = await fetch('/api/dynblock-rules');
                const data = await res.json();
                this.dynblockRules = (data.success && Array.isArray(data.rules)) ? data.rules : [];
            } catch (e) {
                console.error('Error fetching dynblock rules:', e);
            }
        },
        async fetchAccessLists() {
            try {
                const res = await fetch('/api/managerlist');
                const data = await res.json();
                this.accessLists = (data.success && Array.isArray(data.managerlist)) ? data.managerlist : [];
                // console.log(this.accessLists);
            } catch (e) {
                console.error('Error fetching accesslist:', e);
            }
        },
        
        getRulesCount(agentName) {
            const ar = this.agentsRules.find(r => r.agent_name === agentName);
          
            return ar ? (ar.rules_count || 0) : 0;
        },
        getAgentRules(agentName) {
            const ar = this.agentsRules.find(r => r.agent_name === agentName);
            return ar ? (ar.rules || []) : [];
        },
        getServersCount(agentName) {
            const as = this.agentsServers.find(s => s.agent_name === agentName);
            return as ? (as.servers ? as.servers.length : 0) : 0;
        },
        getServers(agentName) {
            const ar = this.agentsServers.find(r => r.agent_name === agentName);
            return ar ? (ar.servers || []) : [];
        },

        getGroupAgents(groupId) {

            let agents = this.agents.filter(a => a.group_id === groupId);
            

            if (this.showActiveOnly) {
                agents = agents.filter(a => a.is_active === true);
            }
            
            const statusPriority = {
                'online': 1,
                'offline': 2, 
                'disabled': 3
            };
            
            return agents.sort((a, b) => {
                const statusDiff = statusPriority[a.status] - statusPriority[b.status];
                if (statusDiff === 0) {
                    return a.name.localeCompare(b.name);
                }
                return statusDiff;
            });
        },
        getGroupDynblockRules(groupId) {
            return this.dynblockRules.filter(r => r.group_id === groupId);
        },
        getGroupDynblockRulesAll() {
            return this.dynblockRules.filter(r => !r.group_id);
        },
        getAccessListAll(agentName) {
            return this.accessLists.filter(s => s.agent_name === agentName);
        },
        getAccessListCount(agentName) {
            const ar = this.accessLists.filter(s => s.agent_name === agentName);
            // console.log(ar);
            // console.log(ar.length);
            return ar.length ;

        },
        getStatusClass(status) {
            if (status === 'online') return 'status-online';
            if (status === 'offline') return 'status-offline';
            return 'status-unknown';
        },
        getStatusIcon(status) {
            if (status === 'online') return '🟢 ';
            if (status === 'offline') return '⚪';
            if (status === 'disabled') return '🟡';
            return '◌';
        },
        getAgentNodeClass(agent) {
            if (agent.status === 'online') return 'agent-node-online';
            if (agent.status === 'offline') return 'agent-node-offline';
            return 'agent-node-unknown';
        }
    },
    mounted() {
        this.fetchAll();
    }
}).mount('#app');

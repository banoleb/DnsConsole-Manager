const { createApp } = Vue;

createApp({
    data() {
        return {
            activeTab: 'dynblock',
            agents: [],
            groups: [],
            newDynBlockRule: {
                name: 'api-rule1',
                rule_command: '',
                description: '',
                group_id: ''
            },
            dynBlockRulesList: [],
            selectedGroupFilter: '',
            loadingDynBlockRules: false,
            dynBlockRuleMessage: null,
            isRefreshing: false,
            showEditModal: false,
            editingRule: {
                id: null,
                name: '',
                rule_command: '',
                description: '',
                group_id: ''
            },
            editModalMessage: null,
            generatedUuid: '',
            ruleCommandTemplates: [],
            showTemplateDropdown: false,
            filteredTemplates: [],
            selectedTemplateIndex: -1,
            showTemplateManagerModal: false,
            editingTemplate: {
                id: null,
                name: '',
                template: '',
                description: ''
            },
            templateModalMessage: null,
            selectedAccessListName: '',
            // Access List state
            alEntries: [],
            alLoading: false,
            alSaving: false,
            alEditingEntry: null,
            alFormError: null,
            alFormSuccess: null,
            alFilterType: '',
            alFilterCategory: '',
            alFilterEnabled: '',
            alForm: {
                value: '',
                type: 'list',
                category: '',
                enabled: true,
                reason: '',
                source: 'manual',
                name: ''
            }
        };
    },
    computed: {
        filteredDynBlockRulesList() {
            if (!this.selectedGroupFilter) {
                return this.dynBlockRulesList;
            }
            return this.dynBlockRulesList.filter(rule => {
                return rule.group_id === parseInt(this.selectedGroupFilter);
            });
        },
        alNameSuggestions() {
            const names = this.alEntries
                .map(e => e.name)
                .filter(n => n && n.trim() !== '');
            return [...new Set(names)].sort();
        }
    },
    mounted() {
        // Activate the tab requested via ?tab= URL parameter.
        // tab1 → dynblock rules (default), tab2 → access-list
        const urlParams = new URLSearchParams(window.location.search);
        if (urlParams.get('tab') === 'access') {
            this.activeTab = 'accesslist';
        }
        if (urlParams.get('tab') === 'help') {
            this.activeTab = 'helptab';
        }
        if (urlParams.get('tab') === 'templates') {
            this.activeTab = 'templatetab';
        }
        this.generateUuid();
        this.loadDynBlockRules();
        this.loadAgents();
        this.loadGroups();
        this.loadRuleCommandTemplates();
        this.loadAccessListEntries();
    },
    methods: {
        async loadRuleCommandTemplates() {
            try {
                const response = await fetch('/api/rule-command-templates');
                const data = await response.json();
                if (data.success) {
                    this.ruleCommandTemplates = data.templates;
                }
            } catch (error) {
                console.error('Error loading rule command templates:', error);
            }
        },
        async loadGroups() {
            try {
                const response = await fetch('/api/groups');
                const data = await response.json();
                if (data.success) {
                    this.groups = data.groups;
                }
            } catch (error) {
                console.error('Error loading groups:', error);
            }
        },
        async loadAgents() {
            try {
                const response = await fetch('/api/agents');
                const data = await response.json();
                if (data.success) {
                    this.agents = data.agents;
                }
            } catch (error) {
                console.error('Error loading agents:', error);
            }
        },
        async loadDynBlockRules() {
            this.loadingDynBlockRules = true;
            this.isRefreshing = true;
            try {

                const pathParts = window.location.pathname.split('/').filter(Boolean);
                const uuidPattern = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;
                const url = (pathParts[0] === 'dynblock-rules' && pathParts.length === 2 && uuidPattern.test(pathParts[1]))
                    ? `/api/dynblock-rules/${pathParts[1]}`
                    : '/api/dynblock-rules';
                const response = await fetch(url);

                const data = await response.json();
                if (data.success) {
                    this.dynBlockRulesList = data.rules;
                }
            } catch (error) {
                console.error('Error loading DynBlock rules:', error);
            } finally {
                this.loadingDynBlockRules = false;
                this.isRefreshing = false;
            }
        },
        async addDynBlockRule() {
            try {
                const response = await fetch('/api/dynblock-rules', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json'
                    },
                    body: JSON.stringify({
                        name: this.newDynBlockRule.name,
                        rule_command: this.newDynBlockRule.rule_command,
                        description: this.newDynBlockRule.description,
                        group_id: this.newDynBlockRule.group_id
                    })
                });
                const data = await response.json();

                if (data.success) {
                    this.newDynBlockRule = { name: '', rule_command: '', description: '', group_id: '' };
                    this.loadDynBlockRules();
                    this.showDynBlockRuleMessage('Rule added successfully!', 'success');
                } else {
                    this.showDynBlockRuleMessage('Error: ' + data.error, 'danger');
                }
            } catch (error) {
                this.showDynBlockRuleMessage('API Error: ' + error.message, 'danger');
            }
        },
        async deleteDynBlockRule(rule) {
            // Sanitize the command for display in the confirmation dialog
            const displayCommand = rule.rule_command.length > 80
                ? rule.rule_command.substring(0, 80) + '...'
                : rule.rule_command;

            if (!confirm(`Deleting a rule does not remove it from agents.\nFirst, make sure you have deactivated this rule and check that it has been removed from the agents.\nAnd only after that you can delete it:\nCommand: ${displayCommand}`)) {
                return;
            }

            try {
                const response = await fetch(`/api/dynblock-rules/${rule.id}`, {
                    method: 'DELETE'
                });
                const data = await response.json();

                if (data.success) {
                    this.loadDynBlockRules();
                    this.showDynBlockRuleMessage('Rule deleted successfully', 'success');
                } else {
                    this.showDynBlockRuleMessage('Error: ' + data.error, 'danger');
                }
            } catch (error) {
                this.showDynBlockRuleMessage('Error: ' + error.message, 'danger');
            }
        },
        // async sendDynBlockRule(rule) {
        //     // Basic validation: ensure command starts with expected DynBlock functions
        //     const allowedPrefixes = ['addDynBlocks', 'setDynBlocksAction', 'clearDynBlocks', 'addDynBlockRule', 'addAction'];
        //     const isValid = allowedPrefixes.some(prefix => rule.rule_command.trim().startsWith(prefix));

        //     if (!isValid) {
        //         alert('Invalid DynBlock command. Must start with: ' + allowedPrefixes.join(', '));
        //         return;
        //     }

        //     // Confirmation dialog
        //     const displayCommand = rule.rule_command.length > 80
        //         ? rule.rule_command.substring(0, 80) + '...'
        //         : rule.rule_command;

        //     let confirmMessage = `Send this DynBlock rule`;
        //     if (rule.group_name) {
        //         confirmMessage += ` to group "${rule.group_name}"?`;
        //     } else {
        //         confirmMessage += ` to all agents?`;
        //     }
        //     confirmMessage += `\n\nCommand: ${displayCommand}`;

        //     if (!confirm(confirmMessage)) {
        //         return;
        //     }

        //     // Send the rule command as a broadcast to agents in the linked group (or all if no group)
        //     try {
        //         const requestBody = { command: rule.rule_command };

        //         // If rule has a group_id, include it in the broadcast request
        //         if (rule.group_id) {
        //             requestBody.group_id = rule.group_id;
        //         }

        //         const response = await fetch('/api/command/broadcast', {
        //             method: 'POST',
        //             headers: {
        //                 'Content-Type': 'application/json'
        //             },
        //             body: JSON.stringify(requestBody)
        //         });
        //         const data = await response.json();

        //         if (data.results && data.results.length > 0) {
        //             const successCount = data.results.filter(r => r.success).length;
        //             const failCount = data.results.length - successCount;

        //             let message = '';
        //             if (rule.group_name) {
        //                 message = `Rule sent to group "${rule.group_name}": `;
        //             } else {
        //                 message = 'Rule sent: ';
        //             }

        //             if (failCount === 0) {
        //                 message += `${successCount} agent${successCount !== 1 ? 's' : ''} succeeded`;
        //                 this.showDynBlockRuleMessage(message, 'success');
        //             } else {
        //                 message += `${successCount} succeeded, ${failCount} failed`;
        //                 this.showDynBlockRuleMessage(message, 'warning');
        //             }
        //         } else {
        //             this.showDynBlockRuleMessage('No agents available in the selected group', 'warning');
        //         }
        //     } catch (error) {
        //         this.showDynBlockRuleMessage('Error sending rule: ' + error.message, 'danger');
        //     }
        // },
        showDynBlockRuleMessage(text, type) {
            this.dynBlockRuleMessage = { text, type };
            setTimeout(() => {
                this.dynBlockRuleMessage = null;
            }, 5000);
        },
        async toggleRuleActive(rule) {
            try {
                const response = await fetch(`/api/dynblock-rules/${rule.id}`, {
                    method: 'PATCH',
                    headers: {
                        'Content-Type': 'application/json'
                    },
                    body: JSON.stringify({
                        is_active: !rule.is_active
                    })
                });
                const data = await response.json();

                if (data.success) {
                    // Update the rule in the list
                    const index = this.dynBlockRulesList.findIndex(r => r.id === rule.id);
                    if (index !== -1) {
                        this.dynBlockRulesList[index] = data.rule;
                    }
                    const status = data.rule.is_active ? 'activated' : 'deactivated';
                    this.showDynBlockRuleMessage(`Rule ${status} successfully`, 'success');
                } else {
                    this.showDynBlockRuleMessage('Error: ' + data.error, 'danger');
                }
            } catch (error) {
                this.showDynBlockRuleMessage('Error toggling rule: ' + error.message, 'danger');
            }
        },
        openEditModal(rule) {
            this.editingRule = {
                id: rule.id,
                name: rule.name || '',
                rule_command: rule.rule_command,
                description: rule.description || '',
                group_id: rule.group_id || ''
            };
            this.showEditModal = true;
            this.editModalMessage = null;
        },
        closeEditModal() {
            this.showEditModal = false;
            this.editingRule = {
                id: null,
                name: '',
                rule_command: '',
                description: '',
                group_id: ''
            };
            this.editModalMessage = null;
        },
        async saveEditedRule() {
            try {
                const response = await fetch(`/api/dynblock-rules/${this.editingRule.id}`, {
                    method: 'PATCH',
                    headers: {
                        'Content-Type': 'application/json'
                    },
                    body: JSON.stringify({
                        name: this.editingRule.name,
                        rule_command: this.editingRule.rule_command,
                        description: this.editingRule.description,
                        group_id: this.editingRule.group_id
                    })
                });
                const data = await response.json();

                if (data.success) {
                    // Update the rule in the list
                    const index = this.dynBlockRulesList.findIndex(r => r.id === this.editingRule.id);
                    if (index !== -1) {
                        this.dynBlockRulesList[index] = data.rule;
                    }
                    this.showDynBlockRuleMessage('Rule updated successfully!', 'success');
                    this.closeEditModal();
                } else {
                    this.editModalMessage = { text: 'Error: ' + data.error, type: 'danger' };
                }
            } catch (error) {
                this.editModalMessage = { text: 'Error: ' + error.message, type: 'danger' };
            }
        },
        onRuleCommandInput(event) {
            const input = event.target.value;
            const cursorPosition = event.target.selectionStart;

            // Check if the last character typed is a letter or if we're typing
            if (input.length > 0) {
                // Filter templates based on the current input
                const inputLower = input.toLowerCase();
                this.filteredTemplates = this.ruleCommandTemplates.filter(template => {
                    return template.name.toLowerCase().includes(inputLower) ||
                           template.template.toLowerCase().includes(inputLower);
                });

                if (this.filteredTemplates.length > 0) {
                    this.showTemplateDropdown = true;
                    this.selectedTemplateIndex = -1;
                } else {
                    this.showTemplateDropdown = false;
                }
            } else {
                this.showTemplateDropdown = false;
            }
        },
        onRuleCommandKeydown(event) {
            if (!this.showTemplateDropdown || this.filteredTemplates.length === 0) {
                return;
            }

            // Handle arrow key navigation
            if (event.key === 'ArrowDown') {
                event.preventDefault();
                this.selectedTemplateIndex = Math.min(
                    this.selectedTemplateIndex + 1,
                    this.filteredTemplates.length - 1
                );
            } else if (event.key === 'ArrowUp') {
                event.preventDefault();
                this.selectedTemplateIndex = Math.max(this.selectedTemplateIndex - 1, -1);
            } else if (event.key === 'Enter' && this.selectedTemplateIndex >= 0) {
                event.preventDefault();
                this.selectTemplate(this.filteredTemplates[this.selectedTemplateIndex]);
            } else if (event.key === 'Escape') {
                this.showTemplateDropdown = false;
                this.selectedTemplateIndex = -1;
            }
        },
        selectTemplate(template) {
            // Replace placeholders with actual values
            let filledTemplate = template.template;

            // Replace r_name placeholder
            if (this.newDynBlockRule.name) {
                filledTemplate = filledTemplate.replace(/\{\{r_name\}\}/g, this.newDynBlockRule.name);
            }

            // Replace r_uuid placeholder with generated UUID
            if (this.generatedUuid) {
                filledTemplate = filledTemplate.replace(/\{\{r_uuid\}\}/g, this.generatedUuid);
            }

            // Replace r_access_list placeholder with selected access list name
            if (this.selectedAccessListName) {
                filledTemplate = filledTemplate.replace(/\{\{r_access_list\}\}/g,'webconsole_lists.' + this.selectedAccessListName);
            }

            this.newDynBlockRule.rule_command = filledTemplate;
            this.showTemplateDropdown = false;
            this.selectedTemplateIndex = -1;

            // Set focus back to the input
            this.$nextTick(() => {
                const input = this.$refs.ruleCommandInput;
                if (input) {
                    input.focus();
                }
            });
        },
        hideTemplateDropdown() {
            // Delay hiding to allow click events to fire
            setTimeout(() => {
                this.showTemplateDropdown = false;
                this.selectedTemplateIndex = -1;
            }, 200);
        },
        generateUuid() {
            // Generate UUID v4 using Web Crypto API if available, fallback to Math.random
            if (typeof crypto !== 'undefined' && typeof crypto.randomUUID === 'function') {
                this.generatedUuid = crypto.randomUUID();
            } else {
                // Fallback for older browsers (not cryptographically secure)
                console.warn('crypto.randomUUID not available, using Math.random fallback (not cryptographically secure)');
                this.generatedUuid = 'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'.replace(/[xy]/g, function(c) {
                    const r = Math.random() * 16 | 0;
                    const v = c === 'x' ? r : (r & 0x3 | 0x8);
                    return v.toString(16);
                });
            }
        },
        // openTemplateManagerModal() {
        //     this.showTemplateManagerModal = true;
        //     this.templateModalMessage = null;
        //     this.editingTemplate = {
        //         id: null,
        //         name: '',
        //         template: '',
        //         description: ''
        //     };
        // },
        // closeTemplateManagerModal() {
        //     this.showTemplateManagerModal = false;
        //     this.templateModalMessage = null;
        //     this.editingTemplate = {
        //         id: null,
        //         name: '',
        //         template: '',
        //         description: ''
        //     };
        // },
        editTemplate(template) {
            this.editingTemplate = {
                id: template.id,
                name: template.name,
                template: template.template,
                description: template.description || ''
            };
            this.templateModalMessage = null;
        },
        cancelEditTemplate() {
            this.editingTemplate = {
                id: null,
                name: '',
                template: '',
                description: ''
            };
            this.templateModalMessage = null;
        },
        async saveTemplate() {
            try {
                const isEdit = !!this.editingTemplate.id;
                const url = isEdit
                    ? `/api/rule-command-templates/${this.editingTemplate.id}`
                    : '/api/rule-command-templates';
                const method = isEdit ? 'PATCH' : 'POST';

                const response = await fetch(url, {
                    method: method,
                    headers: {
                        'Content-Type': 'application/json'
                    },
                    body: JSON.stringify({
                        name: this.editingTemplate.name,
                        template: this.editingTemplate.template,
                        description: this.editingTemplate.description
                    })
                });
                const data = await response.json();

                if (data.success) {
                    // Reload templates
                    await this.loadRuleCommandTemplates();

                    // Reset form
                    this.editingTemplate = {
                        id: null,
                        name: '',
                        template: '',
                        description: ''
                    };

                    const action = isEdit ? 'updated' : 'added';
                    this.templateModalMessage = {
                        text: `Template ${action} successfully!`,
                        type: 'success'
                    };

                    // Clear success message after 3 seconds
                    setTimeout(() => {
                        this.templateModalMessage = null;
                    }, 3000);
                } else {
                    this.templateModalMessage = {
                        text: 'Error: ' + data.error,
                        type: 'danger'
                    };
                }
            } catch (error) {
                this.templateModalMessage = {
                    text: 'Error: ' + error.message,
                    type: 'danger'
                };
            }
        },
        async deleteTemplate(template) {
            if (!confirm(`Are you sure you want to delete the template "${template.name}"?`)) {
                return;
            }

            try {
                const response = await fetch(`/api/rule-command-templates/${template.id}`, {
                    method: 'DELETE'
                });
                const data = await response.json();

                if (data.success) {
                    // Reload templates
                    await this.loadRuleCommandTemplates();

                    this.templateModalMessage = {
                        text: 'Template deleted successfully!',
                        type: 'success'
                    };

                    // Clear success message after 3 seconds
                    setTimeout(() => {
                        this.templateModalMessage = null;
                    }, 3000);
                } else {
                    this.templateModalMessage = {
                        text: 'Error: ' + data.error,
                        type: 'danger'
                    };
                }
            } catch (error) {
                this.templateModalMessage = {
                    text: 'Error: ' + error.message,
                    type: 'danger'
                };
            }
        },

        // ---------------------------------------------------------------
        // Access List methods
        // ---------------------------------------------------------------
        async loadAccessListEntries() {
            this.alLoading = true;
            try {
                const params = new URLSearchParams();
                if (this.alFilterType) params.append('type', this.alFilterType);
                if (this.alFilterCategory) params.append('category', this.alFilterCategory);
                if (this.alFilterEnabled !== '') params.append('enabled', this.alFilterEnabled);
                const response = await fetch(`/api/access-list?${params.toString()}`);
                const data = await response.json();
                if (data.success) {
                    this.alEntries = data.entries;
                } else {
                    console.error('Failed to load access list entries:', data.error);
                }
            } catch (error) {
                console.error('Error loading access list entries:', error);
            } finally {
                this.alLoading = false;
            }
        },
        alResetFilters() {
            this.alFilterType = '';
            this.alFilterCategory = '';
            this.alFilterEnabled = '';
            this.loadAccessListEntries();
        },
        alStartEdit(entry) {
            this.alEditingEntry = entry;
            this.alForm = {
                value: entry.value,
                type: entry.type,
                category: entry.category || '',
                enabled: entry.enabled,
                reason: entry.reason || '',
                source: entry.source || '',
                name: entry.name || ''
            };
            this.alFormError = null;
            this.alFormSuccess = null;
            window.scrollTo({ top: 0, behavior: 'smooth' });
        },
        alCancelEdit() {
            this.alEditingEntry = null;
            this.alForm = { value: '', type: '', category: '', enabled: true, reason: '', source: '', name: '' };
            this.alFormError = null;
            this.alFormSuccess = null;
        },
        async alSubmitForm() {
            this.alFormError = null;
            this.alFormSuccess = null;
            this.alSaving = true;
            try {
                const payload = {
                    name: (this.alForm.name || '').trim(),
                    value: this.alForm.value.trim(),
                    type: this.alForm.type,
                    category: this.alForm.category || null,
                    enabled: this.alForm.enabled,
                    reason: this.alForm.reason || null,
                    source: this.alForm.source || null
                };
                let url = '/api/access-list';
                let method = 'POST';
                if (this.alEditingEntry) {
                    url = `/api/access-list/${this.alEditingEntry.id}`;
                    method = 'PATCH';
                }
                const response = await fetch(url, {
                    method,
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(payload)
                });
                const data = await response.json();
                if (data.success) {
                    this.alFormSuccess = this.alEditingEntry
                        ? `Entry "${data.entry.value}" updated successfully.`
                        : `Entry "${data.entry.value}" created successfully.`;
                    this.alCancelEdit();
                    await this.loadAccessListEntries();
                } else {
                    this.alFormError = data.error || 'An error occurred.';
                }
            } catch (error) {
                console.error('Error saving entry:', error);
                this.alFormError = 'Failed to save entry. Please try again.';
            } finally {
                this.alSaving = false;
            }
        },
        async alDeleteEntry(entry) {
            if (!confirm(`Are you sure you want to delete entry "${entry.value}"? This cannot be undone.`)) {
                return;
            }
            try {
                const response = await fetch(`/api/access-list/${entry.id}`, { method: 'DELETE' });
                const data = await response.json();
                if (data.success) {
                    await this.loadAccessListEntries();
                } else {
                    alert(`Error: ${data.error}`);
                }
            } catch (error) {
                console.error('Error deleting entry:', error);
                alert('Failed to delete entry. Please try again.');
            }
        },
        alFormatDateTime(dateStr) {
            if (!dateStr) return '-';
            return new Date(dateStr).toLocaleString();
        },
        alTruncate(str, len) {
            if (!str) return '-';
            return str.length > len ? str.substring(0, len) + '…' : str;
        }
    }
}).mount('#app');

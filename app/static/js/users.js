const { createApp } = Vue;

createApp({
    data() {
        return {
            users: [],
            loading: true,
            saving: false,
            editingUser: null,
            formError: null,
            formSuccess: null,
            currentUser: typeof CURRENT_USER !== 'undefined' ? CURRENT_USER : '',
            tokenVisible: {},
            form: {
                username: '',
                password: '',
                is_active: true
            }
        };
    },
    methods: {
        async loadUsers() {
            this.loading = true;
            try {
                const response = await fetch('/api/users');
                const data = await response.json();
                if (data.success) {
                    this.users = data.users;
                } else {
                    console.error('Failed to load users:', data.error);
                }
            } catch (error) {
                console.error('Error loading users:', error);
            } finally {
                this.loading = false;
            }
        },
        startEdit(user) {
            this.editingUser = user;
            this.form = {
                username: user.username,
                password: '',
                is_active: user.is_active
            };
            this.formError = null;
            this.formSuccess = null;
            window.scrollTo({ top: 0, behavior: 'smooth' });
        },
        cancelEdit() {
            this.editingUser = null;
            this.form = { username: '', password: '', is_active: true };
            this.formError = null;
            this.formSuccess = null;
        },
        async submitForm() {
            this.formError = null;
            this.formSuccess = null;
            this.saving = true;
            try {
                const payload = {
                    username: this.form.username.trim(),
                    is_active: this.form.is_active
                };
                if (this.form.password) {
                    payload.password = this.form.password;
                } else if (!this.editingUser) {
                    this.formError = 'Password is required for new users.';
                    return;
                }

                let url = '/api/users';
                let method = 'POST';
                if (this.editingUser) {
                    url = `/api/users/${this.editingUser.id}`;
                    method = 'PUT';
                }

                const response = await fetch(url, {
                    method,
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(payload)
                });
                const data = await response.json();

                if (data.success) {
                    this.formSuccess = this.editingUser
                        ? `User "${data.user.username}" updated successfully.`
                        : `User "${data.user.username}" created successfully.`;
                    this.cancelEdit();
                    await this.loadUsers();
                } else {
                    this.formError = data.error || 'An error occurred.';
                }
            } catch (error) {
                console.error('Error saving user:', error);
                this.formError = 'Failed to save user. Please try again.';
            } finally {
                this.saving = false;
            }
        },
        async deleteUser(user) {
            if (!confirm(`Are you sure you want to delete user "${user.username}"? This cannot be undone.`)) {
                return;
            }
            try {
                const response = await fetch(`/api/users/${user.id}`, { method: 'DELETE' });
                const data = await response.json();
                if (data.success) {
                    await this.loadUsers();
                } else {
                    alert(`Error: ${data.error}`);
                }
            } catch (error) {
                console.error('Error deleting user:', error);
                alert('Failed to delete user. Please try again.');
            }
        },
        async generateToken(user) {
            const regenerating = !!user.api_token;
            const confirmMsg = regenerating
                ? `Regenerate API token for "${user.username}"? The current token will be invalidated.`
                : `Generate API token for "${user.username}"?`;
            if (!confirm(confirmMsg)) {
                return;
            }
            try {
                const response = await fetch(`/api/users/${user.id}/token`, { method: 'POST' });
                const data = await response.json();
                if (data.success) {
                    await this.loadUsers();
                    // Show the new token immediately after the list is refreshed
                    this.tokenVisible = { ...this.tokenVisible, [user.id]: true };
                } else {
                    alert(`Error: ${data.error}`);
                }
            } catch (error) {
                console.error('Error generating token:', error);
                alert('Failed to generate token. Please try again.');
            }
        },
        async revokeToken(user) {
            if (!confirm(`Revoke API token for "${user.username}"? This cannot be undone.`)) {
                return;
            }
            try {
                const response = await fetch(`/api/users/${user.id}/token`, { method: 'DELETE' });
                const data = await response.json();
                if (data.success) {
                    delete this.tokenVisible[user.id];
                    await this.loadUsers();
                } else {
                    alert(`Error: ${data.error}`);
                }
            } catch (error) {
                console.error('Error revoking token:', error);
                alert('Failed to revoke token. Please try again.');
            }
        },
        toggleTokenVisibility(userId) {
            this.tokenVisible = { ...this.tokenVisible, [userId]: !this.tokenVisible[userId] };
        },
        maskToken(token) {
            if (!token) return '';
            return token.substring(0, 8) + '•'.repeat(token.length - 12) + token.substring(token.length - 4);
        },
        async copyToken(token) {
            try {
                await navigator.clipboard.writeText(token);
                alert('Token copied to clipboard.');
            } catch (error) {
                console.error('Failed to copy token:', error);
                alert('Failed to copy token. Please copy it manually.');
            }
        },
        formatDateTime(dateStr) {
            if (!dateStr) return '-';
            return new Date(dateStr).toLocaleString();
        }
    },
    mounted() {
        this.loadUsers();
        // console.log('1. currentUser:', this.currentUser);
    }
}).mount('#app');

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

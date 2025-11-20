'use client';

import { useState, useEffect } from 'react';
import { useSession } from 'next-auth/react';
import { UserPlus, Shield, Trash2, Building2 } from 'lucide-react';

interface User {
    _id: string;
    username: string;
    role: string;
    org_id?: string | null;
    org_role?: string | null;
}

interface Organization {
    _id: string;
    id: string;
    name: string;
}

export default function UserManagementClient() {
    const { data: session } = useSession();
    const [users, setUsers] = useState<User[]>([]);
    const [organizations, setOrganizations] = useState<Organization[]>([]);
    const [loading, setLoading] = useState(true);
    const [showCreateModal, setShowCreateModal] = useState(false);
    const [newUser, setNewUser] = useState({
        username: '',
        password: '',
        role: 'admin',
        org_id: '',
        org_role: 'developer'
    });

    const isPrimaryAdmin = session?.user?.role === 'primary_admin';

    useEffect(() => {
        fetchUsers();
        fetchOrganizations();
    }, []);

    const fetchUsers = async () => {
        try {
            const res = await fetch('/api/users');
            if (res.ok) {
                const data = await res.json();
                setUsers(data);
            }
        } catch (error) {
            console.error('Error fetching users:', error);
        } finally {
            setLoading(false);
        }
    };

    const fetchOrganizations = async () => {
        try {
            const res = await fetch('/api/organizations');
            if (res.ok) {
                const data = await res.json();
                setOrganizations(data);
            }
        } catch (error) {
            console.error('Error fetching organizations:', error);
        }
    };

    const getOrgName = (orgId?: string | null) => {
        if (!orgId) return 'No Organization';
        const org = organizations.find(o => o.id === orgId);
        return org?.name || 'Unknown';
    };

    const handleCreateUser = async (e: React.FormEvent) => {
        e.preventDefault();
        try {
            const res = await fetch('/api/users', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(newUser)
            });

            if (res.ok) {
                setShowCreateModal(false);
                setNewUser({ username: '', password: '', role: 'admin', org_id: '', org_role: 'developer' });
                fetchUsers();
            }
        } catch (error) {
            console.error('Error creating user:', error);
        }
    };

    const handleDeleteUser = async (id: string, username: string) => {
        if (username === 'admin') {
            alert('Cannot delete the primary admin user');
            return;
        }

        if (!confirm(`Are you sure you want to delete user ${username}?`)) return;

        try {
            const res = await fetch(`/api/users/${id}`, {
                method: 'DELETE'
            });

            if (res.ok) {
                fetchUsers();
            } else {
                const data = await res.json();
                alert(data.error || 'Failed to delete user');
            }
        } catch (error) {
            console.error('Error deleting user:', error);
        }
    };

    if (!isPrimaryAdmin) {
        return (
            <div className="glass-card p-12 text-center">
                <p className="text-slate-400">You don't have permission to access this page.</p>
            </div>
        );
    }

    if (loading) {
        return <div className="text-center text-slate-400">Loading...</div>;
    }

    return (
        <div className="space-y-8">
            <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
                <div>
                    <h1 className="text-3xl font-bold text-white mb-2">User Management</h1>
                    <p className="text-slate-400">Manage users and their permissions</p>
                </div>

                <button
                    onClick={() => setShowCreateModal(true)}
                    className="bg-indigo-600 hover:bg-indigo-500 text-white px-4 py-2 rounded-xl font-medium flex items-center transition-colors shadow-lg shadow-indigo-500/20"
                >
                    <UserPlus className="w-4 h-4 mr-2" />
                    Add User
                </button>
            </div>

            <div className="glass-card overflow-hidden">
                <div className="overflow-x-auto">
                    <table className="w-full">
                        <thead className="bg-slate-800/50 border-b border-white/5">
                            <tr>
                                <th className="px-6 py-4 text-left text-xs font-medium text-slate-400 uppercase tracking-wider">
                                    User
                                </th>
                                <th className="px-6 py-4 text-left text-xs font-medium text-slate-400 uppercase tracking-wider">
                                    Organization
                                </th>
                                <th className="px-6 py-4 text-left text-xs font-medium text-slate-400 uppercase tracking-wider">
                                    Role
                                </th>
                                <th className="px-6 py-4 text-left text-xs font-medium text-slate-400 uppercase tracking-wider">
                                    Status
                                </th>
                                <th className="px-6 py-4 text-right text-xs font-medium text-slate-400 uppercase tracking-wider">
                                    Actions
                                </th>
                            </tr>
                        </thead>
                        <tbody className="divide-y divide-white/5">
                            {users.map((user) => (
                                <tr key={user._id} className="hover:bg-white/5 transition-colors">
                                    <td className="px-6 py-4 whitespace-nowrap">
                                        <div className="flex items-center">
                                            <div className="w-10 h-10 rounded-full bg-indigo-500 flex items-center justify-center text-white font-bold">
                                                {user.username.charAt(0).toUpperCase()}
                                            </div>
                                            <div className="ml-4">
                                                <div className="text-sm font-medium text-white">{user.username}</div>
                                            </div>
                                        </div>
                                    </td>
                                    <td className="px-6 py-4 whitespace-nowrap">
                                        <div className="flex items-center text-sm text-slate-300">
                                            <Building2 className="w-4 h-4 mr-2 text-slate-400" />
                                            {getOrgName(user.org_id)}
                                        </div>
                                    </td>
                                    <td className="px-6 py-4 whitespace-nowrap">
                                        {user.role === 'primary_admin' ? (
                                            <span className="px-3 py-1 inline-flex items-center text-xs leading-5 font-semibold rounded-full bg-purple-500/20 text-purple-400 border border-purple-500/30">
                                                <Shield className="w-3 h-3 mr-1" />
                                                Primary Admin
                                            </span>
                                        ) : user.org_role ? (
                                            <span className={`px-3 py-1 inline-flex items-center text-xs leading-5 font-semibold rounded-full ${user.org_role === 'admin' ? 'bg-indigo-500/20 text-indigo-400 border border-indigo-500/30' :
                                                user.org_role === 'developer' ? 'bg-emerald-500/20 text-emerald-400 border border-emerald-500/30' :
                                                    'bg-cyan-500/20 text-cyan-400 border border-cyan-500/30'
                                                }`}>
                                                <Shield className="w-3 h-3 mr-1" />
                                                {user.org_role.charAt(0).toUpperCase() + user.org_role.slice(1)}
                                            </span>
                                        ) : (
                                            <span className="px-3 py-1 inline-flex items-center text-xs leading-5 font-semibold rounded-full bg-slate-500/20 text-slate-400 border border-slate-500/30">
                                                <Shield className="w-3 h-3 mr-1" />
                                                {user.role.charAt(0).toUpperCase() + user.role.slice(1)}
                                            </span>
                                        )}
                                    </td>
                                    <td className="px-6 py-4 whitespace-nowrap">
                                        <span className="px-3 py-1 inline-flex text-xs leading-5 font-semibold rounded-full bg-green-500/20 text-green-400 border border-green-500/30">
                                            Active
                                        </span>
                                    </td>
                                    <td className="px-6 py-4 whitespace-nowrap text-right text-sm font-medium">
                                        <div className="flex items-center justify-end space-x-2">
                                            {user.username !== 'admin' && user.role !== 'primary_admin' && (
                                                <button
                                                    onClick={() => handleDeleteUser(user._id, user.username)}
                                                    className="p-2 text-slate-400 hover:text-red-400 transition-colors"
                                                >
                                                    <Trash2 className="w-4 h-4" />
                                                </button>
                                            )}
                                            {(user.username === 'admin' || user.role === 'primary_admin') && (
                                                <span className="text-xs text-slate-500">Protected</span>
                                            )}
                                        </div>
                                    </td>
                                </tr>
                            ))}
                        </tbody>
                    </table>
                </div>
            </div>

            {/* Create Modal */}
            {showCreateModal && (
                <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4">
                    <div className="glass-card p-6 max-w-md w-full">
                        <h2 className="text-2xl font-bold text-white mb-6">Add New User</h2>
                        <form onSubmit={handleCreateUser} className="space-y-4">
                            <div>
                                <label className="block text-sm font-medium text-slate-300 mb-2">
                                    Username
                                </label>
                                <input
                                    type="text"
                                    value={newUser.username}
                                    onChange={(e) => setNewUser({ ...newUser, username: e.target.value })}
                                    className="w-full bg-slate-800 border border-white/10 rounded-lg px-4 py-2 text-white focus:outline-none focus:border-indigo-500"
                                    required
                                />
                            </div>
                            <div>
                                <label className="block text-sm font-medium text-slate-300 mb-2">
                                    Password
                                </label>
                                <input
                                    type="password"
                                    value={newUser.password}
                                    onChange={(e) => setNewUser({ ...newUser, password: e.target.value })}
                                    className="w-full bg-slate-800 border border-white/10 rounded-lg px-4 py-2 text-white focus:outline-none focus:border-indigo-500"
                                    required
                                />
                            </div>
                            <div>
                                <label className="block text-sm font-medium text-slate-300 mb-2">
                                    Organization
                                </label>
                                <select
                                    value={newUser.org_id}
                                    onChange={(e) => setNewUser({ ...newUser, org_id: e.target.value })}
                                    className="w-full bg-slate-800 border border-white/10 rounded-lg px-4 py-2 text-white focus:outline-none focus:border-indigo-500"
                                >
                                    <option value="">No Organization</option>
                                    {organizations.map((org) => (
                                        <option key={org._id} value={org.id}>{org.name}</option>
                                    ))}
                                </select>
                            </div>
                            <div>
                                <label className="block text-sm font-medium text-slate-300 mb-2">
                                    Role
                                </label>
                                <select
                                    value={newUser.org_role}
                                    onChange={(e) => setNewUser({ ...newUser, org_role: e.target.value })}
                                    className="w-full bg-slate-800 border border-white/10 rounded-lg px-4 py-2 text-white focus:outline-none focus:border-indigo-500"
                                >
                                    <option value="developer">Developer</option>
                                    <option value="tester">Tester</option>
                                    <option value="admin">Admin</option>
                                </select>
                            </div>
                            <div className="flex gap-3">
                                <button
                                    type="submit"
                                    className="flex-1 bg-indigo-600 hover:bg-indigo-500 text-white px-4 py-2 rounded-lg font-medium transition-colors"
                                >
                                    Create
                                </button>
                                <button
                                    type="button"
                                    onClick={() => setShowCreateModal(false)}
                                    className="flex-1 bg-slate-700 hover:bg-slate-600 text-white px-4 py-2 rounded-lg font-medium transition-colors"
                                >
                                    Cancel
                                </button>
                            </div>
                        </form>
                    </div>
                </div>
            )}
        </div>
    );
}

'use client';

import { useState, useEffect } from 'react';
import { useSession } from 'next-auth/react';
import { Building2, Users, Plus, Trash2, Edit, UserPlus, X, Shield } from 'lucide-react';

interface Organization {
    _id: string;
    id: string;
    name: string;
    description?: string;
    memberCount: number;
    created_at: string;
}

interface User {
    _id: string;
    username: string;
    role: string;
    org_id?: string | null;
    org_role?: string | null;
}

export default function OrganizationsClient() {
    const { data: session } = useSession();
    const [organizations, setOrganizations] = useState<Organization[]>([]);
    const [allUsers, setAllUsers] = useState<User[]>([]);
    const [loading, setLoading] = useState(true);
    const [showCreateModal, setShowCreateModal] = useState(false);
    const [showEditModal, setShowEditModal] = useState(false);
    const [selectedOrg, setSelectedOrg] = useState<Organization | null>(null);
    const [orgUsers, setOrgUsers] = useState<User[]>([]);
    const [newOrg, setNewOrg] = useState({ name: '', description: '' });
    const [editOrg, setEditOrg] = useState({ name: '', description: '' });

    const isPrimaryAdmin = session?.user?.role === 'primary_admin';

    useEffect(() => {
        fetchOrganizations();
        fetchAllUsers();
    }, []);

    const fetchOrganizations = async () => {
        try {
            const res = await fetch('/api/organizations');
            if (res.ok) {
                const data = await res.json();
                setOrganizations(data);
            }
        } catch (error) {
            console.error('Error fetching organizations:', error);
        } finally {
            setLoading(false);
        }
    };

    const fetchAllUsers = async () => {
        try {
            const res = await fetch('/api/users');
            if (res.ok) {
                const data = await res.json();
                setAllUsers(data);
            }
        } catch (error) {
            console.error('Error fetching users:', error);
        }
    };

    const handleCreateOrg = async (e: React.FormEvent) => {
        e.preventDefault();
        try {
            const res = await fetch('/api/organizations', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(newOrg)
            });

            if (res.ok) {
                setShowCreateModal(false);
                setNewOrg({ name: '', description: '' });
                fetchOrganizations();
            }
        } catch (error) {
            console.error('Error creating organization:', error);
        }
    };

    const handleEditOrg = async (e: React.FormEvent) => {
        e.preventDefault();
        if (!selectedOrg) return;

        try {
            const res = await fetch(`/api/organizations/${selectedOrg.id}`, {
                method: 'PATCH',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(editOrg)
            });

            if (res.ok) {
                setShowEditModal(false);
                setSelectedOrg(null);
                fetchOrganizations();
            }
        } catch (error) {
            console.error('Error updating organization:', error);
        }
    };

    const handleDeleteOrg = async (id: string) => {
        if (!confirm('Are you sure you want to delete this organization? All users will be removed from it.')) return;

        try {
            const res = await fetch(`/api/organizations/${id}`, {
                method: 'DELETE'
            });

            if (res.ok) {
                fetchOrganizations();
                fetchAllUsers();
            }
        } catch (error) {
            console.error('Error deleting organization:', error);
        }
    };

    const openEditModal = (org: Organization) => {
        setSelectedOrg(org);
        setEditOrg({ name: org.name, description: org.description || '' });
        setOrgUsers(allUsers.filter(u => u.org_id === org.id));
        setShowEditModal(true);
    };

    const handleAddUserToOrg = async (userId: string, role: string) => {
        if (!selectedOrg) return;

        try {
            const res = await fetch(`/api/users/${userId}`, {
                method: 'PATCH',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    org_id: selectedOrg.id,
                    org_role: role
                })
            });

            if (res.ok) {
                await fetchAllUsers();
                setOrgUsers(allUsers.filter(u => u.org_id === selectedOrg.id || u._id === userId));
                fetchOrganizations();
            }
        } catch (error) {
            console.error('Error adding user to organization:', error);
        }
    };

    const handleRemoveUserFromOrg = async (userId: string) => {
        if (!confirm('Remove this user from the organization?')) return;

        try {
            const res = await fetch(`/api/users/${userId}`, {
                method: 'PATCH',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    org_id: null,
                    org_role: null
                })
            });

            if (res.ok) {
                await fetchAllUsers();
                setOrgUsers(orgUsers.filter(u => u._id !== userId));
                fetchOrganizations();
            }
        } catch (error) {
            console.error('Error removing user from organization:', error);
        }
    };

    const handleChangeUserRole = async (userId: string, newRole: string) => {
        try {
            const res = await fetch(`/api/users/${userId}`, {
                method: 'PATCH',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    org_role: newRole
                })
            });

            if (res.ok) {
                await fetchAllUsers();
                setOrgUsers(orgUsers.map(u => u._id === userId ? { ...u, org_role: newRole } : u));
            }
        } catch (error) {
            console.error('Error changing user role:', error);
        }
    };

    const getAvailableUsers = () => {
        return allUsers.filter(u => !u.org_id || u.org_id !== selectedOrg?.id);
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
                    <h1 className="text-3xl font-bold text-white mb-2">Organizations</h1>
                    <p className="text-slate-400">Manage your organizations and teams</p>
                </div>

                <button
                    onClick={() => setShowCreateModal(true)}
                    className="bg-indigo-600 hover:bg-indigo-500 text-white px-4 py-2 rounded-xl font-medium flex items-center transition-colors shadow-lg shadow-indigo-500/20"
                >
                    <Plus className="w-4 h-4 mr-2" />
                    Create Organization
                </button>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
                {organizations.map((org) => (
                    <div key={org._id} className="glass-card p-6 hover:border-indigo-500/30 transition-all">
                        <div className="flex items-start justify-between mb-4">
                            <div className="w-12 h-12 bg-gradient-to-br from-indigo-500 to-purple-500 rounded-lg flex items-center justify-center">
                                <Building2 className="w-6 h-6 text-white" />
                            </div>
                            <div className="flex gap-2">
                                <button
                                    onClick={() => openEditModal(org)}
                                    className="p-2 text-slate-400 hover:text-indigo-400 transition-colors"
                                    title="Edit organization"
                                >
                                    <Edit className="w-4 h-4" />
                                </button>
                                <button
                                    onClick={() => handleDeleteOrg(org.id)}
                                    className="p-2 text-slate-400 hover:text-red-400 transition-colors"
                                    title="Delete organization"
                                >
                                    <Trash2 className="w-4 h-4" />
                                </button>
                            </div>
                        </div>
                        <h3 className="text-lg font-bold text-white mb-2">{org.name}</h3>
                        <p className="text-slate-400 text-sm mb-4">{org.description || 'No description'}</p>
                        <div className="flex items-center justify-between text-sm">
                            <div className="flex items-center text-slate-400">
                                <Users className="w-4 h-4 mr-1" />
                                <span>{org.memberCount} {org.memberCount === 1 ? 'member' : 'members'}</span>
                            </div>
                        </div>
                    </div>
                ))}
            </div>

            {/* Create Modal */}
            {showCreateModal && (
                <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4">
                    <div className="glass-card p-6 max-w-md w-full">
                        <h2 className="text-2xl font-bold text-white mb-6">Create Organization</h2>
                        <form onSubmit={handleCreateOrg} className="space-y-4">
                            <div>
                                <label className="block text-sm font-medium text-slate-300 mb-2">
                                    Organization Name
                                </label>
                                <input
                                    type="text"
                                    value={newOrg.name}
                                    onChange={(e) => setNewOrg({ ...newOrg, name: e.target.value })}
                                    className="w-full bg-slate-800 border border-white/10 rounded-lg px-4 py-2 text-white focus:outline-none focus:border-indigo-500"
                                    required
                                />
                            </div>
                            <div>
                                <label className="block text-sm font-medium text-slate-300 mb-2">
                                    Description (Optional)
                                </label>
                                <textarea
                                    value={newOrg.description}
                                    onChange={(e) => setNewOrg({ ...newOrg, description: e.target.value })}
                                    className="w-full bg-slate-800 border border-white/10 rounded-lg px-4 py-2 text-white focus:outline-none focus:border-indigo-500"
                                    rows={3}
                                />
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

            {/* Edit Modal with User Management */}
            {showEditModal && selectedOrg && (
                <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4 overflow-y-auto">
                    <div className="glass-card p-6 max-w-3xl w-full my-8">
                        <div className="flex items-center justify-between mb-6">
                            <h2 className="text-2xl font-bold text-white">Edit Organization</h2>
                            <button
                                onClick={() => setShowEditModal(false)}
                                className="p-2 text-slate-400 hover:text-white transition-colors"
                            >
                                <X className="w-5 h-5" />
                            </button>
                        </div>

                        {/* Organization Details */}
                        <form onSubmit={handleEditOrg} className="space-y-4 mb-8">
                            <div>
                                <label className="block text-sm font-medium text-slate-300 mb-2">
                                    Organization Name
                                </label>
                                <input
                                    type="text"
                                    value={editOrg.name}
                                    onChange={(e) => setEditOrg({ ...editOrg, name: e.target.value })}
                                    className="w-full bg-slate-800 border border-white/10 rounded-lg px-4 py-2 text-white focus:outline-none focus:border-indigo-500"
                                    required
                                />
                            </div>
                            <div>
                                <label className="block text-sm font-medium text-slate-300 mb-2">
                                    Description
                                </label>
                                <textarea
                                    value={editOrg.description}
                                    onChange={(e) => setEditOrg({ ...editOrg, description: e.target.value })}
                                    className="w-full bg-slate-800 border border-white/10 rounded-lg px-4 py-2 text-white focus:outline-none focus:border-indigo-500"
                                    rows={3}
                                />
                            </div>
                            <button
                                type="submit"
                                className="bg-indigo-600 hover:bg-indigo-500 text-white px-4 py-2 rounded-lg font-medium transition-colors"
                            >
                                Save Changes
                            </button>
                        </form>

                        {/* User Management Section */}
                        <div className="border-t border-white/10 pt-6">
                            <div className="flex items-center justify-between mb-4">
                                <h3 className="text-lg font-bold text-white">Members ({orgUsers.length})</h3>
                            </div>

                            {/* Current Members */}
                            <div className="space-y-3 mb-6">
                                {orgUsers.length > 0 ? (
                                    orgUsers.map((user) => (
                                        <div key={user._id} className="flex items-center justify-between bg-slate-800/50 rounded-lg p-3">
                                            <div className="flex items-center gap-3">
                                                <div className="w-10 h-10 rounded-full bg-indigo-500 flex items-center justify-center text-white font-bold">
                                                    {user.username.charAt(0).toUpperCase()}
                                                </div>
                                                <div>
                                                    <div className="text-white font-medium">{user.username}</div>
                                                    <div className="text-xs text-slate-400">
                                                        {user.org_role ? user.org_role.charAt(0).toUpperCase() + user.org_role.slice(1) : 'No role'}
                                                    </div>
                                                </div>
                                            </div>
                                            <div className="flex items-center gap-2">
                                                <select
                                                    value={user.org_role || 'developer'}
                                                    onChange={(e) => handleChangeUserRole(user._id, e.target.value)}
                                                    className="bg-slate-700 border border-white/10 rounded-lg px-3 py-1 text-sm text-white focus:outline-none focus:border-indigo-500"
                                                >
                                                    <option value="developer">Developer</option>
                                                    <option value="tester">Tester</option>
                                                    <option value="admin">Admin</option>
                                                </select>
                                                <button
                                                    onClick={() => handleRemoveUserFromOrg(user._id)}
                                                    className="p-2 text-slate-400 hover:text-red-400 transition-colors"
                                                    title="Remove from organization"
                                                >
                                                    <X className="w-4 h-4" />
                                                </button>
                                            </div>
                                        </div>
                                    ))
                                ) : (
                                    <p className="text-slate-400 text-sm text-center py-4">No members yet</p>
                                )}
                            </div>

                            {/* Add User Section */}
                            <div className="bg-slate-800/30 rounded-lg p-4">
                                <h4 className="text-sm font-medium text-slate-300 mb-3">Add User to Organization</h4>
                                <div className="space-y-2 max-h-60 overflow-y-auto">
                                    {getAvailableUsers().map((user) => (
                                        <div key={user._id} className="flex items-center justify-between bg-slate-800/50 rounded-lg p-2">
                                            <div className="flex items-center gap-2">
                                                <div className="w-8 h-8 rounded-full bg-slate-600 flex items-center justify-center text-white text-sm font-bold">
                                                    {user.username.charAt(0).toUpperCase()}
                                                </div>
                                                <span className="text-white text-sm">{user.username}</span>
                                            </div>
                                            <div className="flex items-center gap-2">
                                                <select
                                                    id={`role-${user._id}`}
                                                    defaultValue="developer"
                                                    className="bg-slate-700 border border-white/10 rounded px-2 py-1 text-xs text-white focus:outline-none focus:border-indigo-500"
                                                >
                                                    <option value="developer">Developer</option>
                                                    <option value="tester">Tester</option>
                                                    <option value="admin">Admin</option>
                                                </select>
                                                <button
                                                    onClick={() => {
                                                        const select = document.getElementById(`role-${user._id}`) as HTMLSelectElement;
                                                        handleAddUserToOrg(user._id, select.value);
                                                    }}
                                                    className="p-1 bg-indigo-600 hover:bg-indigo-500 text-white rounded transition-colors"
                                                    title="Add to organization"
                                                >
                                                    <UserPlus className="w-4 h-4" />
                                                </button>
                                            </div>
                                        </div>
                                    ))}
                                    {getAvailableUsers().length === 0 && (
                                        <p className="text-slate-400 text-sm text-center py-2">No available users</p>
                                    )}
                                </div>
                            </div>
                        </div>

                        <div className="mt-6 flex justify-end">
                            <button
                                onClick={() => setShowEditModal(false)}
                                className="bg-slate-700 hover:bg-slate-600 text-white px-4 py-2 rounded-lg font-medium transition-colors"
                            >
                                Close
                            </button>
                        </div>
                    </div>
                </div>
            )}
        </div>
    );
}

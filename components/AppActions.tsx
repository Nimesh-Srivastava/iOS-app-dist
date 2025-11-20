'use client';

import { useState } from 'react';
import { useRouter } from 'next/navigation';
import { Trash2, Edit } from 'lucide-react';

interface AppActionsProps {
    appId: string;
    appName: string;
}

export default function AppActions({ appId, appName }: AppActionsProps) {
    const router = useRouter();
    const [showEditModal, setShowEditModal] = useState(false);
    const [showDeleteModal, setShowDeleteModal] = useState(false);
    const [editData, setEditData] = useState({
        name: '',
        version: '',
        bundle_id: '',
        min_ios_version: ''
    });
    const [loading, setLoading] = useState(false);

    const handleEdit = () => {
        setShowEditModal(true);
    };

    const handleSaveEdit = async (e: React.FormEvent) => {
        e.preventDefault();
        setLoading(true);

        try {
            const res = await fetch(`/api/apps/${appId}`, {
                method: 'PATCH',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(editData)
            });

            if (res.ok) {
                setShowEditModal(false);
                router.refresh();
            } else {
                alert('Failed to update app');
            }
        } catch (error) {
            console.error('Error updating app:', error);
            alert('Error updating app');
        } finally {
            setLoading(false);
        }
    };

    const handleDelete = async () => {
        setLoading(true);

        try {
            const res = await fetch(`/api/apps/${appId}`, {
                method: 'DELETE'
            });

            if (res.ok) {
                router.push('/');
            } else {
                alert('Failed to delete app');
            }
        } catch (error) {
            console.error('Error deleting app:', error);
            alert('Error deleting app');
        } finally {
            setLoading(false);
        }
    };

    return (
        <>
            <button
                onClick={handleEdit}
                className="bg-slate-800 hover:bg-slate-700 text-white px-4 py-2 rounded-xl font-medium flex items-center transition-colors border border-white/10"
            >
                <Edit className="w-4 h-4 mr-2" />
                Edit
            </button>
            <button
                onClick={() => setShowDeleteModal(true)}
                className="bg-red-500/10 hover:bg-red-500/20 text-red-400 px-4 py-2 rounded-xl font-medium flex items-center transition-colors border border-red-500/30"
            >
                <Trash2 className="w-4 h-4 mr-2" />
                Delete
            </button>

            {/* Edit Modal */}
            {showEditModal && (
                <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4">
                    <div className="glass-card p-6 max-w-md w-full">
                        <h2 className="text-2xl font-bold text-white mb-6">Edit App</h2>
                        <form onSubmit={handleSaveEdit} className="space-y-4">
                            <div>
                                <label className="block text-sm font-medium text-slate-300 mb-2">
                                    App Name
                                </label>
                                <input
                                    type="text"
                                    value={editData.name}
                                    onChange={(e) => setEditData({ ...editData, name: e.target.value })}
                                    className="w-full bg-slate-800 border border-white/10 rounded-lg px-4 py-2 text-white focus:outline-none focus:border-indigo-500"
                                    placeholder="Leave empty to keep current"
                                />
                            </div>
                            <div>
                                <label className="block text-sm font-medium text-slate-300 mb-2">
                                    Version
                                </label>
                                <input
                                    type="text"
                                    value={editData.version}
                                    onChange={(e) => setEditData({ ...editData, version: e.target.value })}
                                    className="w-full bg-slate-800 border border-white/10 rounded-lg px-4 py-2 text-white focus:outline-none focus:border-indigo-500"
                                    placeholder="Leave empty to keep current"
                                />
                            </div>
                            <div>
                                <label className="block text-sm font-medium text-slate-300 mb-2">
                                    Bundle ID
                                </label>
                                <input
                                    type="text"
                                    value={editData.bundle_id}
                                    onChange={(e) => setEditData({ ...editData, bundle_id: e.target.value })}
                                    className="w-full bg-slate-800 border border-white/10 rounded-lg px-4 py-2 text-white focus:outline-none focus:border-indigo-500"
                                    placeholder="Leave empty to keep current"
                                />
                            </div>
                            <div>
                                <label className="block text-sm font-medium text-slate-300 mb-2">
                                    Min iOS Version
                                </label>
                                <input
                                    type="text"
                                    value={editData.min_ios_version}
                                    onChange={(e) => setEditData({ ...editData, min_ios_version: e.target.value })}
                                    className="w-full bg-slate-800 border border-white/10 rounded-lg px-4 py-2 text-white focus:outline-none focus:border-indigo-500"
                                    placeholder="Leave empty to keep current"
                                />
                            </div>
                            <div className="flex gap-3">
                                <button
                                    type="submit"
                                    disabled={loading}
                                    className="flex-1 bg-indigo-600 hover:bg-indigo-500 text-white px-4 py-2 rounded-lg font-medium transition-colors disabled:opacity-50"
                                >
                                    {loading ? 'Saving...' : 'Save'}
                                </button>
                                <button
                                    type="button"
                                    onClick={() => setShowEditModal(false)}
                                    disabled={loading}
                                    className="flex-1 bg-slate-700 hover:bg-slate-600 text-white px-4 py-2 rounded-lg font-medium transition-colors"
                                >
                                    Cancel
                                </button>
                            </div>
                        </form>
                    </div>
                </div>
            )}

            {/* Delete Confirmation Modal */}
            {showDeleteModal && (
                <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4">
                    <div className="glass-card p-6 max-w-md w-full">
                        <h2 className="text-2xl font-bold text-white mb-4">Delete App</h2>
                        <p className="text-slate-300 mb-6">
                            Are you sure you want to delete <span className="font-bold text-white">{appName}</span>? This action cannot be undone.
                        </p>
                        <div className="flex gap-3">
                            <button
                                onClick={handleDelete}
                                disabled={loading}
                                className="flex-1 bg-red-600 hover:bg-red-500 text-white px-4 py-2 rounded-lg font-medium transition-colors disabled:opacity-50"
                            >
                                {loading ? 'Deleting...' : 'Delete'}
                            </button>
                            <button
                                onClick={() => setShowDeleteModal(false)}
                                disabled={loading}
                                className="flex-1 bg-slate-700 hover:bg-slate-600 text-white px-4 py-2 rounded-lg font-medium transition-colors"
                            >
                                Cancel
                            </button>
                        </div>
                    </div>
                </div>
            )}
        </>
    );
}

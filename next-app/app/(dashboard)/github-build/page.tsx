'use client';

import { useState } from 'react';
import { motion } from 'framer-motion';
import { Github, Search, Play, Loader2 } from 'lucide-react';

export default function GitHubBuildPage() {
    const [repoUrl, setRepoUrl] = useState('');
    const [loading, setLoading] = useState(false);

    const handleSubmit = async (e: React.FormEvent) => {
        e.preventDefault();
        setLoading(true);
        // TODO: Implement GitHub build logic
        setTimeout(() => {
            setLoading(false);
            alert('GitHub build integration coming soon!');
        }, 1000);
    };

    return (
        <div className="max-w-2xl mx-auto">
            <div className="mb-8">
                <h1 className="text-3xl font-bold text-white mb-2">GitHub Build</h1>
                <p className="text-slate-400">Trigger iOS builds directly from your GitHub repositories</p>
            </div>

            <div className="glass-card p-8">
                <form onSubmit={handleSubmit}>
                    <div className="mb-6">
                        <label htmlFor="repo_url" className="block text-sm font-medium text-slate-300 mb-2">
                            Repository URL
                        </label>
                        <div className="relative">
                            <div className="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none">
                                <Github className="h-5 w-5 text-slate-500" />
                            </div>
                            <input
                                type="url"
                                id="repo_url"
                                className="w-full bg-slate-900/60 border border-white/10 text-white rounded-xl pl-10 pr-4 py-3 focus:border-indigo-500 focus:ring-1 focus:ring-indigo-500 outline-none transition-all"
                                placeholder="https://github.com/username/repo"
                                value={repoUrl}
                                onChange={(e) => setRepoUrl(e.target.value)}
                                required
                            />
                        </div>
                    </div>

                    <div className="flex justify-end">
                        <button
                            type="submit"
                            disabled={loading}
                            className="bg-slate-800 hover:bg-slate-700 text-white px-8 py-3 rounded-xl font-semibold border border-white/10 transition-all duration-300 flex items-center"
                        >
                            {loading ? (
                                <>
                                    <Loader2 className="w-5 h-5 mr-2 animate-spin" />
                                    Connecting...
                                </>
                            ) : (
                                <>
                                    Connect Repository
                                    <ArrowRight className="w-5 h-5 ml-2" />
                                </>
                            )}
                        </button>
                    </div>
                </form>
            </div>
        </div>
    );
}

import { ArrowRight } from 'lucide-react';

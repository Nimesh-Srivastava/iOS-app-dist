'use client';

import Link from 'next/link';
import { motion } from 'framer-motion';
import { Calendar, HardDrive, Github, ArrowRight, Download } from 'lucide-react';
import { IApp } from '@/models/App';

interface AppCardProps {
    app: IApp; // We'll use a simplified interface for the prop if needed, but IApp is fine for now
}

export default function AppCard({ app }: AppCardProps) {
    // Format date helper
    const formatDate = (dateString?: string) => {
        if (!dateString) return 'Unknown';
        try {
            const date = new Date(dateString);
            return new Intl.DateTimeFormat('en-GB', {
                day: '2-digit',
                month: 'short',
                year: 'numeric',
            }).format(date);
        } catch (e) {
            return dateString;
        }
    };

    // Format size helper
    const formatSize = (bytes?: number) => {
        if (!bytes) return 'Unknown';
        return (bytes / (1024 * 1024)).toFixed(2) + ' MB';
    };

    return (
        <motion.div
            whileHover={{ y: -5 }}
            className="glass-card flex flex-col h-full overflow-hidden group"
        >
            <div className="p-6 flex-grow flex flex-col items-center text-center relative">
                <div className="absolute top-3 right-3">
                    <span className="bg-indigo-500/20 text-indigo-300 text-xs font-bold px-2 py-1 rounded-full border border-indigo-500/20">
                        v{app.version}
                    </span>
                </div>

                <div className="w-20 h-20 mb-4 rounded-2xl overflow-hidden shadow-lg shadow-black/20 group-hover:shadow-indigo-500/20 transition-all duration-300">
                    {app.icon ? (
                        <img src={app.icon} alt={app.name} className="w-full h-full object-cover" />
                    ) : (
                        <div className="w-full h-full bg-slate-700 flex items-center justify-center">
                            <span className="text-2xl font-bold text-slate-500">{app.name.charAt(0)}</span>
                        </div>
                    )}
                </div>

                <h3 className="text-lg font-bold text-white mb-1">{app.name}</h3>
                {app.bundle_id && (
                    <p className="text-xs text-slate-400 mb-4 font-mono">{app.bundle_id}</p>
                )}

                <div className="w-full flex justify-between items-center text-xs text-slate-400 mt-auto pt-4 border-t border-white/5">
                    <div className="flex items-center">
                        <Calendar className="w-3 h-3 mr-1.5" />
                        {formatDate(app.upload_date || app.creation_date)}
                    </div>
                    <div className="flex items-center">
                        <HardDrive className="w-3 h-3 mr-1.5" />
                        {formatSize(app.size)}
                    </div>
                </div>

                {app.source === 'github' && (
                    <div className="mt-3">
                        <span className="inline-flex items-center px-2 py-1 rounded text-xs font-medium bg-slate-700/50 text-slate-300">
                            <Github className="w-3 h-3 mr-1" />
                            GitHub Build
                        </span>
                    </div>
                )}
            </div>

            <div className="p-4 bg-black/20 border-t border-white/5 flex gap-2">
                <Link
                    href={`/apps/${app.id}`}
                    className="flex-1 bg-indigo-500/10 hover:bg-indigo-500/20 text-indigo-300 text-sm font-medium py-2 rounded-lg flex items-center justify-center transition-colors"
                >
                    Details
                    <ArrowRight className="w-4 h-4 ml-1" />
                </Link>
                <Link
                    href={`/apps/${app.id}/install`} // We'll implement install route later or handle it
                    className="flex-1 bg-emerald-500/10 hover:bg-emerald-500/20 text-emerald-300 text-sm font-medium py-2 rounded-lg flex items-center justify-center transition-colors"
                >
                    Install
                    <Download className="w-4 h-4 ml-1" />
                </Link>
            </div>
        </motion.div>
    );
}

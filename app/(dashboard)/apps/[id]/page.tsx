import { getServerSession } from 'next-auth';
import { authOptions } from '@/lib/auth';
import { redirect, notFound } from 'next/navigation';
import dbConnect from '@/lib/db';
import App, { IApp } from '@/models/App';
import Link from 'next/link';
import { ArrowLeft, Calendar, HardDrive, Download, Share2, Edit, Trash2, Upload, History, FileText } from 'lucide-react';

// Force dynamic rendering
export const dynamic = 'force-dynamic';

async function getApp(id: string) {
    await dbConnect();
    const app = await App.findOne({ id }).lean();
    if (!app) return null;
    return JSON.parse(JSON.stringify(app));
}

export default async function AppDetailPage({ params }: { params: { id: string } }) {
    const session = await getServerSession(authOptions);
    if (!session) redirect('/login');

    const app = await getApp(params.id);
    if (!app) notFound();

    // Helper to format date
    const formatDate = (dateString?: string) => {
        if (!dateString) return 'Unknown';
        try {
            return new Intl.DateTimeFormat('en-GB', {
                day: '2-digit',
                month: 'short',
                year: 'numeric',
            }).format(new Date(dateString));
        } catch (e) {
            return dateString;
        }
    };

    // Helper to format size
    const formatSize = (bytes?: number) => {
        if (!bytes) return 'Unknown';
        return (bytes / (1024 * 1024)).toFixed(2) + ' MB';
    };

    return (
        <div className="max-w-5xl mx-auto">
            <div className="flex items-center mb-8">
                <Link
                    href="/"
                    className="flex items-center text-slate-400 hover:text-white transition-colors mr-4"
                >
                    <ArrowLeft className="w-5 h-5 mr-1" />
                    Back
                </Link>
                <h1 className="text-2xl font-bold text-white">{app.name}</h1>
                <span className="ml-4 bg-indigo-500/20 text-indigo-300 text-sm font-bold px-3 py-1 rounded-full border border-indigo-500/20">
                    v{app.version}
                </span>
            </div>

            <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
                {/* Left Column: App Info */}
                <div className="lg:col-span-1 space-y-6">
                    <div className="glass-card p-6 text-center">
                        <div className="w-32 h-32 mx-auto mb-6 rounded-3xl overflow-hidden shadow-2xl shadow-black/30">
                            {app.icon ? (
                                <img src={app.icon} alt={app.name} className="w-full h-full object-cover" />
                            ) : (
                                <div className="w-full h-full bg-slate-700 flex items-center justify-center">
                                    <span className="text-4xl font-bold text-slate-500">{app.name.charAt(0)}</span>
                                </div>
                            )}
                        </div>

                        {app.bundle_id && (
                            <p className="text-slate-400 font-mono text-sm mb-4 break-all">{app.bundle_id}</p>
                        )}

                        <div className="flex justify-between text-sm text-slate-400 mb-6 px-4">
                            <div className="flex items-center">
                                <Calendar className="w-4 h-4 mr-2" />
                                {formatDate(app.upload_date)}
                            </div>
                            <div className="flex items-center">
                                <HardDrive className="w-4 h-4 mr-2" />
                                {formatSize(app.size)}
                            </div>
                        </div>

                        <div className="space-y-3">
                            <button className="w-full bg-indigo-600 hover:bg-indigo-500 text-white py-3 rounded-xl font-medium flex items-center justify-center transition-colors shadow-lg shadow-indigo-500/20">
                                <Download className="w-5 h-5 mr-2" />
                                Install App
                            </button>
                            <button className="w-full bg-slate-700/50 hover:bg-slate-700 text-white py-3 rounded-xl font-medium flex items-center justify-center transition-colors border border-white/5">
                                <FileText className="w-5 h-5 mr-2" />
                                Direct Download
                            </button>
                        </div>

                        {/* Admin Actions */}
                        {(session.user.role === 'primary_admin' || session.user.org_role === 'admin') && (
                            <>
                                <div className="border-t border-white/10 my-6"></div>
                                <div className="space-y-3">
                                    <button className="w-full bg-cyan-500/10 hover:bg-cyan-500/20 text-cyan-400 py-2 rounded-lg text-sm font-medium flex items-center justify-center transition-colors">
                                        <Share2 className="w-4 h-4 mr-2" />
                                        Manage Sharing
                                    </button>
                                    <button className="w-full bg-slate-700/30 hover:bg-slate-700/50 text-slate-300 py-2 rounded-lg text-sm font-medium flex items-center justify-center transition-colors">
                                        <Edit className="w-4 h-4 mr-2" />
                                        Edit Details
                                    </button>
                                    <button className="w-full bg-red-500/10 hover:bg-red-500/20 text-red-400 py-2 rounded-lg text-sm font-medium flex items-center justify-center transition-colors">
                                        <Trash2 className="w-4 h-4 mr-2" />
                                        Delete App
                                    </button>
                                </div>
                            </>
                        )}
                    </div>
                </div>

                {/* Right Column: Version History & Details */}
                <div className="lg:col-span-2 space-y-6">
                    {/* Description */}
                    {app.description && (
                        <div className="glass-card p-6">
                            <h3 className="text-lg font-bold text-white mb-4">Description</h3>
                            <p className="text-slate-300 whitespace-pre-wrap">{app.description}</p>
                        </div>
                    )}

                    {/* Version History */}
                    <div className="glass-card overflow-hidden">
                        <div className="p-6 border-b border-white/5 flex justify-between items-center">
                            <h3 className="text-lg font-bold text-white flex items-center">
                                <History className="w-5 h-5 mr-2 text-indigo-400" />
                                Version History
                            </h3>
                            {(session.user.role === 'primary_admin' || session.user.org_role === 'admin') && (
                                <button className="bg-emerald-500/10 hover:bg-emerald-500/20 text-emerald-400 px-3 py-1.5 rounded-lg text-sm font-medium flex items-center transition-colors">
                                    <Upload className="w-4 h-4 mr-2" />
                                    Upload New Version
                                </button>
                            )}
                        </div>

                        <div className="divide-y divide-white/5">
                            {app.versions?.sort((a: any, b: any) => new Date(b.upload_date).getTime() - new Date(a.upload_date).getTime()).map((version: any, index: number) => (
                                <div
                                    key={index}
                                    className="p-6 hover:bg-white/5 transition-colors animate-in fade-in slide-in-from-bottom-2 duration-500"
                                    style={{ animationDelay: `${index * 100}ms` }}
                                >
                                    <div className="flex justify-between items-start mb-4">
                                        <div>
                                            <div className="flex items-center gap-3 mb-1">
                                                <h4 className="text-lg font-bold text-white">v{version.version}</h4>
                                                {index === 0 && (
                                                    <span className="bg-emerald-500/20 text-emerald-300 text-xs font-bold px-2 py-0.5 rounded-full border border-emerald-500/20">
                                                        Latest
                                                    </span>
                                                )}
                                            </div>
                                            <div className="flex items-center text-sm text-slate-400 gap-4">
                                                <span className="flex items-center">
                                                    <Calendar className="w-3 h-3 mr-1.5" />
                                                    {formatDate(version.upload_date)}
                                                </span>
                                                <span className="flex items-center">
                                                    <HardDrive className="w-3 h-3 mr-1.5" />
                                                    {formatSize(version.size)}
                                                </span>
                                            </div>
                                        </div>
                                        <div className="flex gap-2">
                                            {version.release_notes && (
                                                <button className="p-2 text-slate-400 hover:text-white hover:bg-white/10 rounded-lg transition-colors" title="Release Notes">
                                                    <FileText className="w-5 h-5" />
                                                </button>
                                            )}
                                            <button className="bg-indigo-600 hover:bg-indigo-500 text-white px-4 py-2 rounded-lg text-sm font-medium flex items-center transition-colors shadow-lg shadow-indigo-500/20">
                                                <Download className="w-4 h-4 mr-2" />
                                                Download
                                            </button>
                                        </div>
                                    </div>

                                    {version.release_notes && (
                                        <div className="bg-slate-900/50 rounded-xl p-4 text-sm text-slate-300 whitespace-pre-wrap border border-white/5">
                                            {version.release_notes}
                                        </div>
                                    )}
                                </div>
                            ))}
                        </div>
                    </div>
                </div>
            </div>
        </div>
    );
}

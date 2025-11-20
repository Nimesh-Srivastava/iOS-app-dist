import { getServerSession } from 'next-auth';
import { authOptions } from '@/lib/auth';
import { redirect, notFound } from 'next/navigation';
import dbConnect from '@/lib/db';
import App from '@/models/App';
import { Calendar, HardDrive, Package, Download, QrCode, Github } from 'lucide-react';
import Link from 'next/link';
import AppActions from '@/components/AppActions';

export const dynamic = 'force-dynamic';

async function getApp(id: string) {
    try {
        console.log('[APP DETAILS] Fetching app with ID:', id);
        await dbConnect();
        const app = await App.findById(id).lean();

        if (!app) {
            console.log('[APP DETAILS] App not found');
            return null;
        }

        console.log('[APP DETAILS] App found:', app.name);
        return JSON.parse(JSON.stringify(app));
    } catch (error) {
        console.error('[APP DETAILS] Error fetching app:', error);
        return null;
    }
}

export default async function AppDetailsPage({ params }: { params: Promise<{ id: string }> }) {
    // Await params in Next.js 15
    const { id } = await params;
    console.log('[APP DETAILS] Page loaded with id:', id);

    const session = await getServerSession(authOptions);

    if (!session) {
        redirect('/login');
    }

    const app = await getApp(id);

    if (!app) {
        console.log('[APP DETAILS] Calling notFound()');
        notFound();
    }

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
        <div className="space-y-8">
            {/* Header */}
            <div className="flex flex-col md:flex-row md:items-start justify-between gap-6">
                <div className="flex items-start gap-6">
                    <div className="w-24 h-24 rounded-2xl overflow-hidden shadow-lg bg-slate-700 flex-shrink-0">
                        {app.icon ? (
                            <img src={app.icon} alt={app.name} className="w-full h-full object-cover" />
                        ) : (
                            <div className="w-full h-full flex items-center justify-center">
                                <span className="text-3xl font-bold text-slate-500">{app.name.charAt(0)}</span>
                            </div>
                        )}
                    </div>
                    <div>
                        <h1 className="text-3xl font-bold text-white mb-2">{app.name}</h1>
                        <p className="text-slate-400 mb-2">Version {app.version}</p>
                        {app.bundle_id && (
                            <p className="text-sm text-slate-500 font-mono">{app.bundle_id}</p>
                        )}
                    </div>
                </div>

                <div className="flex gap-3">
                    <Link
                        href={`/apps/${id}/install`}
                        className="bg-indigo-600 hover:bg-indigo-500 text-white px-6 py-2 rounded-xl font-medium flex items-center transition-colors shadow-lg shadow-indigo-500/20"
                    >
                        <Download className="w-4 h-4 mr-2" />
                        Install
                    </Link>
                    <AppActions appId={id} appName={app.name} />
                </div>
            </div>

            {/* App Info Grid */}
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
                <div className="glass-card p-6">
                    <div className="flex items-center justify-between mb-2">
                        <Calendar className="w-5 h-5 text-indigo-400" />
                    </div>
                    <p className="text-sm text-slate-400 mb-1">Upload Date</p>
                    <p className="text-lg font-bold text-white">{formatDate(app.upload_date || app.creation_date)}</p>
                </div>

                <div className="glass-card p-6">
                    <div className="flex items-center justify-between mb-2">
                        <HardDrive className="w-5 h-5 text-purple-400" />
                    </div>
                    <p className="text-sm text-slate-400 mb-1">File Size</p>
                    <p className="text-lg font-bold text-white">{formatSize(app.size)}</p>
                </div>

                <div className="glass-card p-6">
                    <div className="flex items-center justify-between mb-2">
                        <Package className="w-5 h-5 text-emerald-400" />
                    </div>
                    <p className="text-sm text-slate-400 mb-1">Build Number</p>
                    <p className="text-lg font-bold text-white">{app.build_number || 'N/A'}</p>
                </div>

                <div className="glass-card p-6">
                    <div className="flex items-center justify-between mb-2">
                        <Download className="w-5 h-5 text-cyan-400" />
                    </div>
                    <p className="text-sm text-slate-400 mb-1">Downloads</p>
                    <p className="text-lg font-bold text-white">{app.download_count || 0}</p>
                </div>
            </div>

            {/* Details Section */}
            <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
                {/* Main Details */}
                <div className="lg:col-span-2 glass-card p-6">
                    <h3 className="text-lg font-bold text-white mb-6">App Information</h3>
                    <div className="space-y-4">
                        <div className="flex items-start border-b border-white/5 pb-4">
                            <div className="flex-1">
                                <p className="text-sm text-slate-400 mb-1">Bundle Identifier</p>
                                <p className="text-white font-mono text-sm">{app.bundle_id || 'N/A'}</p>
                            </div>
                        </div>
                        <div className="flex items-start border-b border-white/5 pb-4">
                            <div className="flex-1">
                                <p className="text-sm text-slate-400 mb-1">Minimum iOS Version</p>
                                <p className="text-white">{app.min_ios_version || 'N/A'}</p>
                            </div>
                        </div>
                        <div className="flex items-start border-b border-white/5 pb-4">
                            <div className="flex-1">
                                <p className="text-sm text-slate-400 mb-1">Source</p>
                                <div className="flex items-center">
                                    {app.source === 'github' && <Github className="w-4 h-4 mr-2 text-slate-400" />}
                                    <p className="text-white capitalize">{app.source || 'Upload'}</p>
                                </div>
                            </div>
                        </div>
                        {app.github_repo && (
                            <div className="flex items-start pb-4">
                                <div className="flex-1">
                                    <p className="text-sm text-slate-400 mb-1">GitHub Repository</p>
                                    <a href={app.github_repo} target="_blank" rel="noopener noreferrer" className="text-indigo-400 hover:text-indigo-300 transition-colors">
                                        {app.github_repo}
                                    </a>
                                </div>
                            </div>
                        )}
                    </div>
                </div>

                {/* QR Code & Install */}
                <div className="glass-card p-6">
                    <h3 className="text-lg font-bold text-white mb-6">Quick Install</h3>
                    <div className="flex flex-col items-center">
                        <div className="w-48 h-48 bg-white rounded-xl p-4 mb-4 flex items-center justify-center">
                            <QrCode className="w-32 h-32 text-slate-800" />
                        </div>
                        <p className="text-sm text-slate-400 text-center mb-4">
                            Scan this QR code with your iOS device to install
                        </p>
                        <Link
                            href={`/apps/${id}/install`}
                            className="w-full bg-indigo-600 hover:bg-indigo-500 text-white px-4 py-2 rounded-xl font-medium flex items-center justify-center transition-colors"
                        >
                            <Download className="w-4 h-4 mr-2" />
                            Install Now
                        </Link>
                    </div>
                </div>
            </div>
        </div>
    );
}

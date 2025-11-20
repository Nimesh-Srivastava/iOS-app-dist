import { getServerSession } from 'next-auth';
import { authOptions } from '@/lib/auth';
import { redirect } from 'next/navigation';
import dbConnect from '@/lib/db';
import App, { IApp } from '@/models/App';
import AppCard from '@/components/AppCard';
import { Rocket, Upload, Github } from 'lucide-react';
import Link from 'next/link';

// Force dynamic rendering since we fetch data
export const dynamic = 'force-dynamic';

async function getApps() {
    await dbConnect();
    // In a real app, we would filter by user permissions here
    // For now, we'll fetch all apps (admin view) or filter if needed
    const apps = await App.find({}).sort({ upload_date: -1 }).lean();

    // Convert _id and other non-serializable fields
    return JSON.parse(JSON.stringify(apps));
}

export default async function DashboardPage() {
    const session = await getServerSession(authOptions);

    if (!session) {
        redirect('/login');
    }

    const apps = await getApps();

    return (
        <div className="space-y-8">
            <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
                <div>
                    <h1 className="text-3xl font-bold text-white mb-2">App Library</h1>
                    <p className="text-slate-400">Manage and distribute your iOS applications</p>
                </div>

                <div className="flex gap-3">
                    <Link
                        href="/upload"
                        className="bg-indigo-600 hover:bg-indigo-500 text-white px-4 py-2 rounded-xl font-medium flex items-center transition-colors shadow-lg shadow-indigo-500/20"
                    >
                        <Upload className="w-4 h-4 mr-2" />
                        Upload App
                    </Link>
                    <Link
                        href="/github-build"
                        className="bg-slate-800 hover:bg-slate-700 text-white px-4 py-2 rounded-xl font-medium flex items-center transition-colors border border-white/10"
                    >
                        <Github className="w-4 h-4 mr-2" />
                        GitHub Build
                    </Link>
                </div>
            </div>

            {apps.length > 0 ? (
                <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
                    {apps.map((app: IApp, index: number) => (
                        <div
                            key={app.id}
                            className="animate-in fade-in slide-in-from-bottom-4 duration-500"
                            style={{ animationDelay: `${index * 100}ms` }}
                        >
                            <AppCard app={app} />
                        </div>
                    ))}
                </div>
            ) : (
                <div className="glass-card p-12 text-center">
                    <div className="w-20 h-20 bg-slate-800/50 rounded-full flex items-center justify-center mx-auto mb-6">
                        <Rocket className="w-10 h-10 text-slate-600" />
                    </div>
                    <h3 className="text-xl font-bold text-white mb-2">No apps available</h3>
                    <p className="text-slate-400 mb-8 max-w-md mx-auto">
                        Get started by uploading your first iOS application or connecting a GitHub repository.
                    </p>
                    <Link
                        href="/upload"
                        className="inline-flex items-center bg-indigo-600 hover:bg-indigo-500 text-white px-6 py-3 rounded-xl font-medium transition-colors"
                    >
                        <Upload className="w-5 h-5 mr-2" />
                        Upload First App
                    </Link>
                </div>
            )}
        </div>
    );
}

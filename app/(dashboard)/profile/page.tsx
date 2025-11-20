import { getServerSession } from 'next-auth';
import { authOptions } from '@/lib/auth';
import { redirect } from 'next/navigation';
import { User, Mail, Building2, Calendar, Edit } from 'lucide-react';

export const dynamic = 'force-dynamic';

export default async function ProfilePage() {
    const session = await getServerSession(authOptions);

    if (!session) {
        redirect('/login');
    }

    return (
        <div className="space-y-8">
            <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
                <div>
                    <h1 className="text-3xl font-bold text-white mb-2">Profile</h1>
                    <p className="text-slate-400">Manage your personal information</p>
                </div>

                <button className="bg-indigo-600 hover:bg-indigo-500 text-white px-4 py-2 rounded-xl font-medium flex items-center transition-colors shadow-lg shadow-indigo-500/20">
                    <Edit className="w-4 h-4 mr-2" />
                    Edit Profile
                </button>
            </div>

            <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
                {/* Profile Card */}
                <div className="glass-card p-6">
                    <div className="flex flex-col items-center text-center">
                        <div className="w-24 h-24 rounded-full bg-gradient-to-br from-indigo-500 to-purple-500 flex items-center justify-center text-white text-3xl font-bold mb-4">
                            {session.user?.name?.charAt(0).toUpperCase()}
                        </div>
                        <h2 className="text-xl font-bold text-white mb-1">{session.user?.name}</h2>
                        <p className="text-slate-400 text-sm mb-4">{session.user?.email}</p>
                        <span className="px-3 py-1 inline-flex text-xs leading-5 font-semibold rounded-full bg-indigo-500/20 text-indigo-400 border border-indigo-500/30">
                            Admin
                        </span>
                    </div>
                </div>

                {/* Profile Details */}
                <div className="lg:col-span-2 glass-card p-6">
                    <h3 className="text-lg font-bold text-white mb-6">Personal Information</h3>
                    <div className="space-y-4">
                        <div className="flex items-start">
                            <User className="w-5 h-5 text-slate-400 mr-3 mt-0.5" />
                            <div className="flex-1">
                                <p className="text-sm text-slate-400">Full Name</p>
                                <p className="text-white font-medium">{session.user?.name}</p>
                            </div>
                        </div>
                        <div className="flex items-start">
                            <Mail className="w-5 h-5 text-slate-400 mr-3 mt-0.5" />
                            <div className="flex-1">
                                <p className="text-sm text-slate-400">Email Address</p>
                                <p className="text-white font-medium">{session.user?.email}</p>
                            </div>
                        </div>
                        <div className="flex items-start">
                            <Building2 className="w-5 h-5 text-slate-400 mr-3 mt-0.5" />
                            <div className="flex-1">
                                <p className="text-sm text-slate-400">Organization</p>
                                <p className="text-white font-medium">Default Organization</p>
                            </div>
                        </div>
                        <div className="flex items-start">
                            <Calendar className="w-5 h-5 text-slate-400 mr-3 mt-0.5" />
                            <div className="flex-1">
                                <p className="text-sm text-slate-400">Member Since</p>
                                <p className="text-white font-medium">November 2025</p>
                            </div>
                        </div>
                    </div>
                </div>
            </div>
        </div>
    );
}

import { getServerSession } from 'next-auth';
import { authOptions } from '@/lib/auth';
import { redirect } from 'next/navigation';
import { Bell, Lock, Palette, Globe, Shield, Save } from 'lucide-react';

export const dynamic = 'force-dynamic';

export default async function SettingsPage() {
    const session = await getServerSession(authOptions);

    if (!session) {
        redirect('/login');
    }

    return (
        <div className="space-y-8">
            <div>
                <h1 className="text-3xl font-bold text-white mb-2">Settings</h1>
                <p className="text-slate-400">Manage your account settings and preferences</p>
            </div>

            <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
                {/* Settings Navigation */}
                <div className="glass-card p-4">
                    <nav className="space-y-1">
                        <button className="w-full flex items-center px-4 py-3 text-sm font-medium rounded-lg bg-indigo-500/20 text-indigo-400 border border-indigo-500/30">
                            <Bell className="w-4 h-4 mr-3" />
                            Notifications
                        </button>
                        <button className="w-full flex items-center px-4 py-3 text-sm font-medium rounded-lg text-slate-300 hover:bg-white/5 transition-colors">
                            <Lock className="w-4 h-4 mr-3" />
                            Security
                        </button>
                        <button className="w-full flex items-center px-4 py-3 text-sm font-medium rounded-lg text-slate-300 hover:bg-white/5 transition-colors">
                            <Palette className="w-4 h-4 mr-3" />
                            Appearance
                        </button>
                        <button className="w-full flex items-center px-4 py-3 text-sm font-medium rounded-lg text-slate-300 hover:bg-white/5 transition-colors">
                            <Globe className="w-4 h-4 mr-3" />
                            Language
                        </button>
                        <button className="w-full flex items-center px-4 py-3 text-sm font-medium rounded-lg text-slate-300 hover:bg-white/5 transition-colors">
                            <Shield className="w-4 h-4 mr-3" />
                            Privacy
                        </button>
                    </nav>
                </div>

                {/* Settings Content */}
                <div className="lg:col-span-2 glass-card p-6">
                    <div className="flex items-center justify-between mb-6">
                        <div>
                            <h3 className="text-lg font-bold text-white mb-1">Notification Preferences</h3>
                            <p className="text-sm text-slate-400">Manage how you receive notifications</p>
                        </div>
                    </div>

                    <div className="space-y-6">
                        {/* Email Notifications */}
                        <div className="flex items-center justify-between py-4 border-b border-white/5">
                            <div>
                                <p className="text-white font-medium">Email Notifications</p>
                                <p className="text-sm text-slate-400">Receive email updates about your apps</p>
                            </div>
                            <label className="relative inline-flex items-center cursor-pointer">
                                <input type="checkbox" className="sr-only peer" defaultChecked />
                                <div className="w-11 h-6 bg-slate-700 peer-focus:outline-none peer-focus:ring-4 peer-focus:ring-indigo-500/20 rounded-full peer peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border-gray-300 after:border after:rounded-full after:h-5 after:w-5 after:transition-all peer-checked:bg-indigo-600"></div>
                            </label>
                        </div>

                        {/* Push Notifications */}
                        <div className="flex items-center justify-between py-4 border-b border-white/5">
                            <div>
                                <p className="text-white font-medium">Push Notifications</p>
                                <p className="text-sm text-slate-400">Receive push notifications in your browser</p>
                            </div>
                            <label className="relative inline-flex items-center cursor-pointer">
                                <input type="checkbox" className="sr-only peer" />
                                <div className="w-11 h-6 bg-slate-700 peer-focus:outline-none peer-focus:ring-4 peer-focus:ring-indigo-500/20 rounded-full peer peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border-gray-300 after:border after:rounded-full after:h-5 after:w-5 after:transition-all peer-checked:bg-indigo-600"></div>
                            </label>
                        </div>

                        {/* App Updates */}
                        <div className="flex items-center justify-between py-4 border-b border-white/5">
                            <div>
                                <p className="text-white font-medium">App Updates</p>
                                <p className="text-sm text-slate-400">Get notified when apps are updated</p>
                            </div>
                            <label className="relative inline-flex items-center cursor-pointer">
                                <input type="checkbox" className="sr-only peer" defaultChecked />
                                <div className="w-11 h-6 bg-slate-700 peer-focus:outline-none peer-focus:ring-4 peer-focus:ring-indigo-500/20 rounded-full peer peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border-gray-300 after:border after:rounded-full after:h-5 after:w-5 after:transition-all peer-checked:bg-indigo-600"></div>
                            </label>
                        </div>

                        {/* Weekly Reports */}
                        <div className="flex items-center justify-between py-4">
                            <div>
                                <p className="text-white font-medium">Weekly Reports</p>
                                <p className="text-sm text-slate-400">Receive weekly summary of app downloads</p>
                            </div>
                            <label className="relative inline-flex items-center cursor-pointer">
                                <input type="checkbox" className="sr-only peer" defaultChecked />
                                <div className="w-11 h-6 bg-slate-700 peer-focus:outline-none peer-focus:ring-4 peer-focus:ring-indigo-500/20 rounded-full peer peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border-gray-300 after:border after:rounded-full after:h-5 after:w-5 after:transition-all peer-checked:bg-indigo-600"></div>
                            </label>
                        </div>
                    </div>

                    <div className="mt-8 pt-6 border-t border-white/5">
                        <button className="bg-indigo-600 hover:bg-indigo-500 text-white px-6 py-2 rounded-xl font-medium flex items-center transition-colors shadow-lg shadow-indigo-500/20">
                            <Save className="w-4 h-4 mr-2" />
                            Save Changes
                        </button>
                    </div>
                </div>
            </div>
        </div>
    );
}

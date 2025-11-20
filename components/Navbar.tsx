'use client';

import Link from 'next/link';
import { useSession, signOut } from 'next-auth/react';
import { Rocket, LogOut, User, Settings, Bell, Building2, Users } from 'lucide-react';
import { motion } from 'framer-motion';

export default function Navbar() {
    const { data: session } = useSession();

    return (
        <nav className="glass-navbar">
            <div className="container mx-auto px-4 sm:px-6 lg:px-8">
                <div className="flex items-center justify-between h-16">
                    <div className="flex items-center space-x-8">
                        <Link href="/" className="flex items-center space-x-2 group">
                            <div className="w-8 h-8 bg-gradient-to-br from-indigo-500 to-purple-500 rounded-lg flex items-center justify-center shadow-lg shadow-indigo-500/20 group-hover:shadow-indigo-500/40 transition-all duration-300">
                                <Rocket className="w-5 h-5 text-white" />
                            </div>
                            <span className="text-xl font-bold bg-clip-text text-transparent bg-gradient-to-r from-white to-slate-400">
                                AppCenter
                            </span>
                        </Link>

                        {/* Main Navigation Links */}
                        {session && (
                            <div className="hidden md:flex items-center space-x-1">
                                <Link
                                    href="/organizations"
                                    className="flex items-center space-x-2 px-3 py-2 rounded-lg text-slate-300 hover:text-white hover:bg-white/5 transition-all"
                                >
                                    <Building2 className="w-4 h-4" />
                                    <span className="text-sm font-medium">Organizations</span>
                                </Link>
                                <Link
                                    href="/user-management"
                                    className="flex items-center space-x-2 px-3 py-2 rounded-lg text-slate-300 hover:text-white hover:bg-white/5 transition-all"
                                >
                                    <Users className="w-4 h-4" />
                                    <span className="text-sm font-medium">User Management</span>
                                </Link>
                            </div>
                        )}
                    </div>

                    <div className="flex items-center space-x-4">
                        {session ? (
                            <>
                                <button className="p-2 text-slate-400 hover:text-white transition-colors relative">
                                    <Bell className="w-5 h-5" />
                                    <span className="absolute top-1.5 right-1.5 w-2 h-2 bg-red-500 rounded-full"></span>
                                </button>

                                <div className="relative group">
                                    <button className="flex items-center space-x-3 p-1 rounded-full hover:bg-white/5 transition-colors">
                                        <div className="w-8 h-8 rounded-full bg-slate-700 border border-white/10 overflow-hidden">
                                            {/* Placeholder for profile pic */}
                                            <div className="w-full h-full flex items-center justify-center text-xs font-bold text-white">
                                                {session.user?.name?.charAt(0).toUpperCase()}
                                            </div>
                                        </div>
                                        <span className="hidden md:block text-sm font-medium text-slate-200">
                                            {session.user?.name}
                                        </span>
                                    </button>

                                    {/* Dropdown */}
                                    <div className="absolute right-0 mt-2 w-48 bg-[#1e293b] border border-white/10 rounded-xl shadow-xl opacity-0 invisible group-hover:opacity-100 group-hover:visible transition-all duration-200 transform origin-top-right z-50">
                                        <div className="py-1">
                                            <Link href="/profile" className="flex items-center px-4 py-2 text-sm text-slate-300 hover:bg-white/5 hover:text-white">
                                                <User className="w-4 h-4 mr-2" />
                                                Profile
                                            </Link>
                                            <Link href="/settings" className="flex items-center px-4 py-2 text-sm text-slate-300 hover:bg-white/5 hover:text-white">
                                                <Settings className="w-4 h-4 mr-2" />
                                                Settings
                                            </Link>
                                            <div className="border-t border-white/5 my-1"></div>
                                            <button
                                                onClick={() => signOut({ callbackUrl: '/login' })}
                                                className="flex w-full items-center px-4 py-2 text-sm text-red-400 hover:bg-red-500/10"
                                            >
                                                <LogOut className="w-4 h-4 mr-2" />
                                                Sign Out
                                            </button>
                                        </div>
                                    </div>
                                </div>
                            </>
                        ) : (
                            <Link
                                href="/login"
                                className="px-4 py-2 rounded-lg bg-indigo-600 hover:bg-indigo-500 text-white text-sm font-medium transition-colors"
                            >
                                Sign In
                            </Link>
                        )}
                    </div>
                </div>
            </div>
        </nav>
    );
}

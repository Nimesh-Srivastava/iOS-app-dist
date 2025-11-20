import { getServerSession } from 'next-auth';
import { authOptions } from '@/lib/auth';
import { redirect, notFound } from 'next/navigation';
import dbConnect from '@/lib/db';
import App from '@/models/App';
import { Download, Smartphone, AlertCircle, QrCode } from 'lucide-react';

export const dynamic = 'force-dynamic';

async function getApp(id: string) {
    await dbConnect();
    const app = await App.findById(id).lean();

    if (!app) {
        return null;
    }

    return JSON.parse(JSON.stringify(app));
}

export default async function InstallPage({ params }: { params: Promise<{ id: string }> }) {
    // Await params in Next.js 15
    const { id } = await params;

    const session = await getServerSession(authOptions);

    if (!session) {
        redirect('/login');
    }

    const app = await getApp(id);

    if (!app) {
        notFound();
    }

    const installUrl = `itms - services://?action=download-manifest&url=${process.env.NEXT_PUBLIC_BASE_URL}/api/manifest/${app._id}`;

    return (
        <div className="max-w-4xl mx-auto space-y-8">
            {/* Header */}
            <div className="text-center">
                <div className="w-32 h-32 mx-auto rounded-2xl overflow-hidden shadow-lg bg-slate-700 mb-6">
                    {app.icon ? (
                        <img src={app.icon} alt={app.name} className="w-full h-full object-cover" />
                    ) : (
                        <div className="w-full h-full flex items-center justify-center">
                            <span className="text-4xl font-bold text-slate-500">{app.name.charAt(0)}</span>
                        </div>
                    )}
                </div>
                <h1 className="text-3xl font-bold text-white mb-2">{app.name}</h1>
                <p className="text-slate-400">Version {app.version}</p>
            </div>

            {/* Installation Instructions */}
            <div className="glass-card p-8">
                <div className="flex items-center justify-center mb-6">
                    <div className="w-16 h-16 bg-indigo-500/20 rounded-full flex items-center justify-center">
                        <Smartphone className="w-8 h-8 text-indigo-400" />
                    </div>
                </div>
                <h2 className="text-2xl font-bold text-white text-center mb-6">Install on iOS Device</h2>

                <div className="space-y-6">
                    {/* Step 1 */}
                    <div className="flex gap-4">
                        <div className="flex-shrink-0 w-8 h-8 bg-indigo-500 rounded-full flex items-center justify-center text-white font-bold">
                            1
                        </div>
                        <div className="flex-1">
                            <h3 className="text-lg font-bold text-white mb-2">Open on iOS Device</h3>
                            <p className="text-slate-400">
                                Make sure you're viewing this page on your iOS device (iPhone or iPad). If you're on a computer, scan the QR code below with your device.
                            </p>
                        </div>
                    </div>

                    {/* Step 2 */}
                    <div className="flex gap-4">
                        <div className="flex-shrink-0 w-8 h-8 bg-indigo-500 rounded-full flex items-center justify-center text-white font-bold">
                            2
                        </div>
                        <div className="flex-1">
                            <h3 className="text-lg font-bold text-white mb-2">Tap Install Button</h3>
                            <p className="text-slate-400 mb-4">
                                Click the install button below. You'll be prompted to install the app.
                            </p>
                            <a
                                href={installUrl}
                                className="inline-flex items-center bg-indigo-600 hover:bg-indigo-500 text-white px-6 py-3 rounded-xl font-medium transition-colors shadow-lg shadow-indigo-500/20"
                            >
                                <Download className="w-5 h-5 mr-2" />
                                Install {app.name}
                            </a>
                        </div>
                    </div>

                    {/* Step 3 */}
                    <div className="flex gap-4">
                        <div className="flex-shrink-0 w-8 h-8 bg-indigo-500 rounded-full flex items-center justify-center text-white font-bold">
                            3
                        </div>
                        <div className="flex-1">
                            <h3 className="text-lg font-bold text-white mb-2">Trust the Certificate</h3>
                            <p className="text-slate-400">
                                After installation, go to <span className="text-white font-medium">Settings → General → VPN & Device Management</span> and trust the developer certificate.
                            </p>
                        </div>
                    </div>

                    {/* Step 4 */}
                    <div className="flex gap-4">
                        <div className="flex-shrink-0 w-8 h-8 bg-indigo-500 rounded-full flex items-center justify-center text-white font-bold">
                            4
                        </div>
                        <div className="flex-1">
                            <h3 className="text-lg font-bold text-white mb-2">Launch the App</h3>
                            <p className="text-slate-400">
                                Once trusted, you can launch the app from your home screen.
                            </p>
                        </div>
                    </div>
                </div>
            </div>

            {/* QR Code Section */}
            <div className="glass-card p-8">
                <h3 className="text-xl font-bold text-white text-center mb-6">Install via QR Code</h3>
                <div className="flex flex-col items-center">
                    <div className="w-64 h-64 bg-white rounded-xl p-4 mb-4 flex items-center justify-center">
                        <QrCode className="w-48 h-48 text-slate-800" />
                    </div>
                    <p className="text-sm text-slate-400 text-center max-w-md">
                        Scan this QR code with your iOS device's camera to open this installation page
                    </p>
                </div>
            </div>

            {/* Important Notes */}
            <div className="glass-card p-6">
                <div className="flex items-start gap-3 mb-4">
                    <AlertCircle className="w-5 h-5 text-yellow-400 flex-shrink-0 mt-0.5" />
                    <div>
                        <h3 className="text-lg font-bold text-white mb-2">Important Notes</h3>
                        <ul className="space-y-2 text-slate-400 text-sm">
                            <li>• This app is distributed for testing purposes only</li>
                            <li>• Make sure your device is registered with the provisioning profile</li>
                            <li>• The certificate must be trusted before the app can be launched</li>
                            <li>• Installation requires iOS {app.min_ios_version || '12.0'} or later</li>
                        </ul>
                    </div>
                </div>
            </div>
        </div>
    );
}

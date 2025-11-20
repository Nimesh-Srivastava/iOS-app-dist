import Navbar from '@/components/Navbar';

export default function DashboardLayout({
    children,
}: {
    children: React.ReactNode;
}) {
    return (
        <div className="min-h-screen flex flex-col">
            <Navbar />
            <main className="flex-grow container mx-auto px-4 sm:px-6 lg:px-8 py-8">
                {children}
            </main>
            <footer className="py-6 text-center text-slate-500 text-sm">
                <p>© 2025 AppCenter. Securely distribute your iOS applications.</p>
            </footer>
        </div>
    );
}

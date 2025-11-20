import { getServerSession } from 'next-auth';
import { authOptions } from '@/lib/auth';
import { redirect } from 'next/navigation';
import UserManagementClient from '@/components/UserManagementClient';

export const dynamic = 'force-dynamic';

export default async function UserManagementPage() {
    const session = await getServerSession(authOptions);

    if (!session) {
        redirect('/login');
    }

    return <UserManagementClient />;
}

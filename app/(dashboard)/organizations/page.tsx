import { getServerSession } from 'next-auth';
import { authOptions } from '@/lib/auth';
import { redirect } from 'next/navigation';
import OrganizationsClient from '@/components/OrganizationsClient';

export const dynamic = 'force-dynamic';

export default async function OrganizationsPage() {
    const session = await getServerSession(authOptions);

    if (!session) {
        redirect('/login');
    }

    return <OrganizationsClient />;
}
